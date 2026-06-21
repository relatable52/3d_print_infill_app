import networkx as nx
import numpy as np
import fullcontrol as fc
import matplotlib.pyplot as plt
from matplotlib import animation
# ==========================================
# 1. GRAPH SETUP
# ==========================================
def create_periodic_multigraph(original_graph, width, height, tolerance=1e-5):
    """Wraps the unit cell into a periodic Pacman graph."""
    # 1. Detect Merges
    merge_logic = nx.Graph()
    merge_logic.add_nodes_from(original_graph.nodes())
    nodes = list(original_graph.nodes(data=True))
    
    for i in range(len(nodes)):
        u, data_u = nodes[i]
        for j in range(i + 1, len(nodes)):
            v, data_v = nodes[j]
            dx = abs(data_u['pos'][0] - data_v['pos'][0])
            dy = abs(data_u['pos'][1] - data_v['pos'][1])
            
            # Check wraps (Left-Right OR Top-Bottom)
            is_wrap = (
                ((abs(dx - width) < tolerance or dx < tolerance) and 
                 (abs(dy - height) < tolerance or dy < tolerance)) and
                not (dx < tolerance and dy < tolerance)
            )
            if is_wrap:
                merge_logic.add_edge(u, v)

    # 2. Build Mapping
    mapping = {} 
    for component in nx.connected_components(merge_logic):
        sorted_ids = sorted(list(component))
        new_id = "_".join(map(str, sorted_ids))
        for old_id in sorted_ids:
            mapping[old_id] = new_id
    for n in original_graph.nodes():
        if n not in mapping: mapping[n] = str(n)

    # 3. Build MultiGraph
    P_G = nx.MultiGraph()
    for u, v, data in original_graph.edges(data=True):
        new_u, new_v = mapping[u], mapping[v]
        edge_key = f"{u}-{v}"
        P_G.add_edge(new_u, new_v, key=edge_key, original_u=u, original_v=v, **data)
        
    return P_G, mapping

# ==========================================
# 2. ROBUST SOLVER (Find ALL Eulerian Circuits)
# ==========================================
def find_all_eulerian_circuits(graph):
    """
    Generator that yields ALL distinct Eulerian circuits.
    Uses backtracking to handle nodes with degree > 2.
    """
    if not nx.is_eulerian(graph):
        return

    total_edges = graph.number_of_edges()
    start_node = list(graph.nodes())[0]

    # Recursive Backtracker
    def backtrack(current_node, current_path, remaining_graph):
        # Base Case: All edges used
        if len(current_path) == total_edges:
            yield list(current_path)
            return

        # Iterate over available edges from current_node
        # Note: list() is needed to create a copy for iteration while modifying
        available = list(remaining_graph.edges(current_node, keys=True, data=True))
        
        for u, v, key, data in available:
            # Remove edge
            remaining_graph.remove_edge(u, v, key=key)
            
            # Recurse (v is the neighbor)
            yield from backtrack(v, current_path + [(u, v, key)], remaining_graph)
            
            # Backtrack (Restore edge)
            remaining_graph.add_edge(u, v, key=key, **data)

    yield from backtrack(start_node, [], graph.copy())

def calculate_path_winding(circuit_edges, periodic_graph, original_graph, mapping):
    """
    Converts a list of periodic edges into physical points and calculates winding.
    """
    wind_x, wind_y = 0, 0
    ordered_physical_edges = []

    # 1. Reconstruct Physical Flow
    for u_merge, v_merge, key in circuit_edges:
        data = periodic_graph[u_merge][v_merge][key]
        u_orig = data['original_u']
        v_orig = data['original_v']
        
        # Determine direction: u_merge -> v_merge
        if mapping[u_orig] == u_merge:
            start, end = u_orig, v_orig
        else:
            start, end = v_orig, u_orig
            
        ordered_physical_edges.append((start, end))

    # 2. Calculate Winding & Coordinates
    for i in range(len(ordered_physical_edges)):
        curr_s, curr_e = ordered_physical_edges[i]
        prev_s, prev_e = ordered_physical_edges[(i-1)%len(ordered_physical_edges)]
        
        p_start = np.array(original_graph.nodes[curr_s]['pos'])
        p_end = np.array(original_graph.nodes[curr_e]['pos'])
        
        # Check Jump
        p_prev_end = np.array(original_graph.nodes[prev_e]['pos'])
        tol = 1e-4
        
        if p_start[0] > p_prev_end[0] + tol: wind_x += 1
        elif p_start[0] < p_prev_end[0] - tol: wind_x -= 1
        
        if p_start[1] > p_prev_end[1] + tol: wind_y += 1
        elif p_start[1] < p_prev_end[1] - tol: wind_y -= 1
        
        
        
    return ordered_physical_edges, (wind_x, wind_y)

def create_threaded_visit_graph(ordered_physical_edges, mapping):
    """
    Converts a raw edge list into a 'Threaded' graph where every node 
    has a Visit ID (0, 1, 2...).
    
    Example: [(1,3), (4,1)...] -> [('1_0', '3_0'), ('4_0', '1_1')...]
    """
    # Track current visit index for each merged group
    # Initialize with 0
    group_counters = {g: 0 for g in set(mapping.values())}
    
    # Store the assigned label for the "End of the previous edge"
    # to handle the jump logic (inheritance).
    prev_end_label = None
    prev_end_group = None
    
    threaded_edges = []
    
    num_edges = len(ordered_physical_edges)
    
    for i in range(num_edges):
        u, v = ordered_physical_edges[i]
        
        group_u = mapping[u]
        group_v = mapping[v]
        
        # --- 1. DETERMINE START NODE LABEL (u) ---
        if i == 0:
            # First node of the entire loop starts at 0
            idx_u = 0
        else:
            # JUMP LOGIC: Look at previous edge's end
            # If u is in the same group as prev_end, inherit the index
            if group_u == prev_end_group:
                idx_u = prev_end_label
            else:
                # This implies a discontinuous jump or logic error in path finding
                # But assuming Eulerian continuity, we stick to the counter
                idx_u = group_counters[group_u]

        # --- 2. DETERMINE END NODE LABEL (v) ---
        if i == num_edges - 1:
            # LOOP CLOSURE: The very last node must connect to the very first node
            # The first node was 'u' of edge 0. 
            # We need 'v' (current) to match that first node's Visit ID
            # IF they are in the same group.
            first_u, _ = ordered_physical_edges[0]
            first_group = mapping[first_u]
            
            if group_v == first_group:
                idx_v = 0 # Force closure to 0
            else:
                idx_v = group_counters[group_v] + 1
        else:
            # Normal Traversal: Increment the counter for the destination group
            # (Because we are arriving at this group 'again')
            
            # Note: We simply increment the global counter for this group
            # So the next time anyone starts from this group, they use the new number
            group_counters[group_v] += 1
            idx_v = group_counters[group_v]

        # Store for next iteration
        prev_end_label = idx_v
        prev_end_group = group_v
        
        # Add to list
        u_str = f"{u}_{idx_u}"
        v_str = f"{v}_{idx_v}"
        threaded_edges.append((u_str, v_str))
        
    return threaded_edges

def tile_and_stitch_threads(original_graph, threaded_edges, mapping, width, height, rows, cols):
    """
    Tiles the threaded graph. Connects boundaries ONLY if Visit IDs match.
    """
    full_graph = nx.Graph()
    pos = nx.get_node_attributes(original_graph, 'pos')
    
    # 1. Instantiate Nodes/Edges
    def get_id(node_str, r, c):
        return f"{node_str}_r{r}_c{c}"
    
    for r in range(rows):
        for c in range(cols):
            ox = c * width
            oy = r * height
            
            for u_str, v_str in threaded_edges:
                # Parse original IDs for positions (u_str is "1_0")
                u_orig = int(u_str.split('_')[0])
                v_orig = int(v_str.split('_')[0])
                
                # New Grid IDs
                n1 = get_id(u_str, r, c)
                n2 = get_id(v_str, r, c)
                
                # Add
                p1 = np.array(pos[u_orig])
                p2 = np.array(pos[v_orig])
                full_graph.add_node(n1, pos=(p1[0]+ox, p1[1]+oy))
                full_graph.add_node(n2, pos=(p2[0]+ox, p2[1]+oy))
                full_graph.add_edge(n1, n2)

    # 2. Stitch Boundaries (The "Same a/b" Logic)
    # We find boundary pairs (e.g. 1 and 7)
    # We connect 1_0 to 7_0, 1_1 to 7_1, etc.
    
    orig_pos = pos
    
    # Identify Geometric Pairs
    h_pairs = [] # Left-Right
    v_pairs = [] # Bot-Top
    
    nodes = list(original_graph.nodes())
    for i in range(len(nodes)):
        u = nodes[i]
        pu = orig_pos[u]
        for j in range(i+1, len(nodes)):
            v = nodes[j]
            pv = orig_pos[v]
            
            # Check Horizontal Pair
            if abs(pu[1] - pv[1]) < 1e-4: # Same Y
                if (abs(pu[0]) < 1e-4 and abs(pv[0]-width) < 1e-4):
                    h_pairs.append((u, v)) # u is Left, v is Right
                elif (abs(pv[0]) < 1e-4 and abs(pu[0]-width) < 1e-4):
                    h_pairs.append((v, u)) # v is Left, u is Right

            # Check Vertical Pair
            if abs(pu[0] - pv[0]) < 1e-4: # Same X
                if (abs(pu[1]) < 1e-4 and abs(pv[1]-height) < 1e-4):
                    v_pairs.append((u, v)) # u is Bot, v is Top
                elif (abs(pv[1]) < 1e-4 and abs(pu[1]-height) < 1e-4):
                    v_pairs.append((v, u))

    # Perform Stitching
    # We iterate over the *Threaded Edges* to know which Visit IDs exist
    # Extract all unique node labels "1_0", "7_0", etc.
    unique_labels = set()
    for u, v in threaded_edges:
        unique_labels.add(u)
        unique_labels.add(v)
        
    for r in range(rows):
        for c in range(cols):
            # Horizontal Stitch (Right of current to Left of next)
            if c < cols - 1:
                for l_orig, r_orig in h_pairs:
                    # Try all possible visit IDs 'k'
                    # We assume max 10 visits just to be safe, or parse unique_labels
                    # Better: Scan unique_labels
                    for label in unique_labels:
                        node_id, visit_id = label.split('_')
                        node_id = int(node_id)
                        
                        if node_id == r_orig:
                            # We found a Right Node "7_k". Look for Left Node "1_k"
                            partner_label = f"{l_orig}_{visit_id}"
                            
                            n_right = get_id(label, r, c)           # 7_k in col 0
                            n_left  = get_id(partner_label, r, c+1) # 1_k in col 1
                            
                            if full_graph.has_node(n_right) and full_graph.has_node(n_left):
                                full_graph.add_edge(n_right, n_left)

            # Vertical Stitch (Top of current to Bot of next)
            if r < rows - 1:
                for b_orig, t_orig in v_pairs:
                    for label in unique_labels:
                        node_id, visit_id = label.split('_')
                        node_id = int(node_id)
                        
                        if node_id == t_orig:
                            # We found Top Node "5_k". Look for Bot Node "2_k"
                            partner_label = f"{b_orig}_{visit_id}"
                            
                            n_top = get_id(label, r, c)
                            n_bot = get_id(partner_label, r+1, c)
                            
                            if full_graph.has_node(n_top) and full_graph.has_node(n_bot):
                                full_graph.add_edge(n_top, n_bot)
                                
    return full_graph

def plot_graph(G, title="Graph Plot", width=None, height=None):
    pos = nx.get_node_attributes(G, 'pos')
    plt.figure(figsize=(6, 6))
    if width and height:
        plt.plot([0, width, width, 0, 0], [0, 0, height, height, 0], 'k--', alpha=0.5, linewidth=1.5)
    nx.draw_networkx(G, pos, node_size=50, node_color='skyblue', font_weight='normal')
    plt.title(title, fontsize=12)
    plt.axis('equal')
    plt.show()


def plot_all_components_colored(graph, width, height, rows, cols):
    """
    Plots all connected components in one graph, each with a distinct color.
    """
    components = list(nx.connected_components(graph))
    num_comps = len(components)
    
    print(f"Plotting {num_comps} components in one graph...")
    
    pos = nx.get_node_attributes(graph, 'pos')
    
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Generate distinct colors for each component
    # Use tab20 for up to 20 colors, or rainbow for more
    if num_comps <= 3:
        colors = plt.cm.tab20(np.linspace(0, 1, num_comps))
    else:
        colors = plt.cm.rainbow(np.linspace(0, 1, num_comps))
    
    # Plot each component with a different color
    for i, comp_nodes in enumerate(components):
        subgraph = graph.subgraph(comp_nodes)
        color = colors[i]
        
        nx.draw_networkx_edges(subgraph, pos, edge_color=[color], width=4, ax=ax)
        # nx.draw_networkx_nodes(subgraph, pos, node_size=0, node_color=[color], ax=ax)
    
    # Add boundary box for context
    ax.plot([0, width*cols, width*cols, 0, 0], [0, 0, height*rows, height*rows, 0], 'k--', alpha=0.3, linewidth=1.5)
    
    ax.set_aspect('equal')
    ax.set_title(f"All {num_comps} Connected Components (Before Stitching)", fontsize=12)
    ax.axis('off')
    
    plt.tight_layout()
    plt.show()

def plot_components_separately(full_graph, width, height, rows, cols):
    """
    Plots each connected component in its own subplot, highlighted against the full graph.
    """
    components = list(nx.connected_components(full_graph))
    num_comps = len(components)
    
    print(f"Plotting {num_comps} components...")
    
    pos = nx.get_node_attributes(full_graph, 'pos')
    
    # Iterate through components
    for i, comp_nodes in enumerate(components):
        fig = plt.figure(figsize=(8, 8))
        
        # 1. Draw Full Graph (Faint Background)
        nx.draw_networkx_edges(full_graph, pos, edge_color='#e0e0e0', width=1)
        
        # 2. Draw This Component (Bold)
        subgraph = full_graph.subgraph(comp_nodes)
        
        # Use a distinct color for the active component
        nx.draw_networkx_edges(subgraph, pos, edge_color='tab:blue', width=2.5)
        nx.draw_networkx_nodes(subgraph, pos, node_size=30, node_color='tab:blue')
        
        # Formatting
        plt.title(f"Component {i+1}", fontsize=12)
        plt.gca().set_aspect('equal')
        plt.axis('off')
        
        # Add boundary box for context
        plt.plot([0, width*cols, width*cols, 0, 0], [0, 0, height*rows, height*rows, 0], 'k--', alpha=0.2, linewidth=1.5)
        
        plt.tight_layout()
        plt.show()

def connect_boundaries_robust(grid_graph):
    """
    Connects disjoint print paths by greedily stitching the closest 
    endpoints that belong to different components.
    
    Works for Diagonal, Horizontal, and Vertical stripes.
    """
    # 1. Find all 'Ports' (Degree 1 nodes)
    ports = [n for n, d in grid_graph.degree() if d == 1]
    pos = nx.get_node_attributes(grid_graph, 'pos')
    
    print(f"Found {len(ports)} loose ends. Stitching...")

    # 2. Generate all possible pairs and their distances
    # Format: (distance, u, v)
    candidates = []
    for i in range(len(ports)):
        u = ports[i]
        p1 = np.array(pos[u])
        for j in range(i + 1, len(ports)):
            v = ports[j]
            p2 = np.array(pos[v])
            dist = np.linalg.norm(p1 - p2)
            candidates.append((dist, u, v))
            
    # 3. Sort by shortest distance (Greedy)
    candidates.sort(key=lambda x: x[0])
    
    # 4. Stitch
    # We use Union-Find logic (via NetworkX connected components) to avoid self-loops
    edges_added = []
    
    # Track which ports have been used
    used_ports = set()
    
    for dist, u, v in candidates:
        # If either port is already connected, skip
        if u in used_ports or v in used_ports:
            continue
            
        # Check connectivity: Are they already in the same component?
        # (Connecting them would form a closed loop, which we usually avoid 
        #  until the very end so we have a Start/End point)
        if not nx.has_path(grid_graph, u, v):
            grid_graph.add_edge(u, v)
            edges_added.append((u, v))
            used_ports.add(u)
            used_ports.add(v)
            
            # Optimization: If we have connected everything into 1 component, stop.
            # (But checking number of components is slow, so we just run greedy)

    return grid_graph, edges_added

def plot_gradient_print_path(connected_graph, width, height, rows, cols):
    """
    Plots the final print path with gradient colors from start (purple) to end (yellow) using plasma colormap.
    """
    from matplotlib.collections import LineCollection
    
    # 1. Extract Ordered Path (DFS)
    deg1 = [n for n, d in connected_graph.degree() if d == 1]
    start_node = deg1[0] if deg1 else list(connected_graph.nodes())[0]
    path_nodes = list(nx.dfs_preorder_nodes(connected_graph, source=start_node))
    
    pos = nx.get_node_attributes(connected_graph, 'pos')
    
    # Convert path to coordinates
    path_coords = np.array([[pos[n][0], pos[n][1]] for n in path_nodes])
    
    # 2. Setup Plot
    fig, ax = plt.subplots(figsize=(14, 14))
    ax.set_xlim(-width*0.2, width*cols*1.2)
    ax.set_ylim(-height*0.2, height*rows*1.2)
    ax.set_aspect('equal')
    ax.set_title("Final Print Path (Start: Purple → End: Yellow)", fontsize=12)
    
    # Draw Bounding Box
    ax.plot([0, width*cols, width*cols, 0, 0], [0, 0, height*rows, height*rows, 0], 'k--', alpha=0.3, linewidth=1.5)
    
    # 3. Create line segments for gradient coloring
    # Each segment connects consecutive points
    segments = np.array([path_coords[i:i+2] for i in range(len(path_coords)-1)])
    
    # 4. Create color array (gradient using plasma colormap)
    n_segments = len(segments)
    colors = plt.cm.plasma(np.linspace(0, 1, n_segments))  # Purple to Yellow gradient
    
    # 5. Create LineCollection with gradient colors
    # lc = LineCollection(segments, colors=colors, linewidths=8, capstyle='round')
    # ax.add_collection(lc)
    
    # 6. Add directional arrows along the path
    # Place arrows at regular intervals (every ~5% of the path)
    # arrow_interval = max(len(path_coords) // 50, 1)  # Approximately 20 arrows
    for i in range(0, len(path_coords)-1):
        # Get two points to define arrow direction
        x1, y1 = path_coords[i]
        x2, y2 = path_coords[i+1]
        x3, y3 = (x1 + x2) / 2, (y1 + y2) / 2  # Midpoint for arrow placement
        
        # Calculate arrow direction
        dx = x2 - x1
        dy = y2 - y1
        
        # Get color from plasma colormap for this position
        color_idx = i / len(path_coords)
        arrow_color = plt.cm.plasma(color_idx)
        
        # Add arrow (centered on line)
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                   arrowprops=dict(arrowstyle='->', lw=1.5, color=arrow_color, 
                                 mutation_scale=8, shrinkA=0, shrinkB=0),
                   zorder=i)
        ax.plot([x1, x2], [y1, y2], color=arrow_color, linewidth=1.5, solid_capstyle='round', zorder=i)
    
    # 7. Mark start and end points
    ax.plot(path_coords[0, 0], path_coords[0, 1], 'o', color='#0d0887', 
            markersize=5, label='Start', zorder=10, markeredgecolor='black', markeredgewidth=1)
    ax.plot(path_coords[-1, 0], path_coords[-1, 1], 's', color='#f0f921', 
            markersize=5, label='End', zorder=10, markeredgecolor='black', markeredgewidth=1)
    
    ax.legend(loc='upper right')
    ax.axis('off')
    plt.tight_layout()
    plt.show()

def animate_printing_process(connected_graph, width, height, rows, cols, interval=50):
    """
    Creates an animation of the printing path.
    """
    # 1. Extract Ordered Path (DFS)
    deg1 = [n for n, d in connected_graph.degree() if d == 1]
    start_node = deg1[0] if deg1 else list(connected_graph.nodes())[0]
    path_nodes = list(nx.dfs_preorder_nodes(connected_graph, source=start_node))
    
    pos = nx.get_node_attributes(connected_graph, 'pos')
    # Convert path to coordinates
    path_x = [pos[n][0] for n in path_nodes]
    path_y = [pos[n][1] for n in path_nodes]
    
    # 2. Setup Plot
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(-width*0.2, width*cols*1.2)
    ax.set_ylim(-height*0.2, height*rows*1.2)
    ax.set_aspect('equal')
    ax.set_title("Printing Simulation", fontsize=12)
    
    # Draw Bounding Box
    ax.plot([0, width*cols, width*cols, 0, 0], [0, 0, height*rows, height*rows, 0], 'k--', alpha=0.3, linewidth=1.5)

    # Plot Elements (Line and Nozzle Head)
    line, = ax.plot([], [], 'b-', linewidth=1.5, label='Extruded Material')
    head, = ax.plot([], [], 'ro', markersize=8, label='Nozzle')
    
    # 3. Animation Logic
    def init():
        line.set_data([], [])
        head.set_data([], [])
        return line, head
    
    def update(frame):
        # frame goes from 0 to len(path_x)
        # Draw everything up to frame
        current_x = path_x[:frame+1]
        current_y = path_y[:frame+1]
        
        line.set_data(current_x, current_y)
        
        if len(current_x) > 0:
            head.set_data([current_x[-1]], [current_y[-1]])
            
        return line, head

    # Create Animation
    ani = animation.FuncAnimation(
        fig, 
        update, 
        frames=len(path_x), 
        init_func=init, 
        interval=interval, 
        blit=True,
        repeat=False
    )
    
    plt.legend(loc='upper right')
    return ani

def generate_gcode_from_graph(connected_graph, z_height=0.2, nozzle_temp=200, bed_temp=60, speed=1200):
    """
    Generates FullControl steps from the connected graph.
    
    Args:
        connected_graph: The connected print path graph
        z_height: Z-height for extrusion (mm)
        nozzle_temp: Nozzle temperature (°C)
        bed_temp: Bed temperature (°C)
        speed: Print speed (mm/min)
    
    Returns:
        list: List of FullControl step objects
    """
    import fullcontrol as fc
    
    # Extract ordered path
    deg1 = [n for n, d in connected_graph.degree() if d == 1]
    start_node = deg1[0] if deg1 else list(connected_graph.nodes())[0]
    path_nodes = list(nx.dfs_preorder_nodes(connected_graph, source=start_node))
    
    pos = nx.get_node_attributes(connected_graph, 'pos')
    
    # Build FullControl steps
    steps = []
    
    # Startup sequence
    steps.append(fc.ManualGcode(text=f"M140 S{bed_temp} ; Set Bed Temp"))
    steps.append(fc.ManualGcode(text=f"M104 S{nozzle_temp} ; Set Nozzle Temp"))
    steps.append(fc.ManualGcode(text="G28 ; Home all axes"))
    steps.append(fc.ManualGcode(text=f"M190 S{bed_temp} ; Wait for Bed"))
    steps.append(fc.ManualGcode(text=f"M109 S{nozzle_temp} ; Wait for Nozzle"))
    steps.append(fc.ManualGcode(text="G92 E0 ; Reset Extruder"))
    
    # Travel to start
    first_pos = pos[path_nodes[0]]
    steps.append(fc.Point(x=first_pos[0], y=first_pos[1], z=z_height))
    
    # Enable extrusion
    steps.append(fc.Extruder(on=True))
    
    # Add path points
    for node in path_nodes[1:]:
        node_pos = pos[node]
        steps.append(fc.Point(x=node_pos[0], y=node_pos[1], z=z_height))
    
    # Disable extrusion
    steps.append(fc.Extruder(on=False))
    
    # End sequence
    steps.append(fc.ManualGcode(text="M104 S0 ; Turn off nozzle"))
    steps.append(fc.ManualGcode(text="M140 S0 ; Turn off bed"))
    steps.append(fc.ManualGcode(text="G28 X0 Y0 ; Home X Y"))
    
    return steps

def plot_gcode_path(connected_graph, width, height, rows, cols, title="G-code Path"):
    """
    Plots the G-code path from the connected graph.
    """
    # Extract ordered path
    deg1 = [n for n, d in connected_graph.degree() if d == 1]
    start_node = deg1[0] if deg1 else list(connected_graph.nodes())[0]
    path_nodes = list(nx.dfs_preorder_nodes(connected_graph, source=start_node))
    
    pos = nx.get_node_attributes(connected_graph, 'pos')
    coords = np.array([[pos[n][0], pos[n][1]] for n in path_nodes])
    
    if len(coords) == 0:
        print("No valid coordinates to plot")
        return
    
    fig, ax = plt.subplots(figsize=(14, 14))
    ax.set_xlim(-width*0.2, width*cols*1.2)
    ax.set_ylim(-height*0.2, height*rows*1.2)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=12)
    
    # Draw bounding box
    ax.plot([0, width*cols, width*cols, 0, 0], [0, 0, height*rows, height*rows, 0], 'k--', alpha=0.3, linewidth=1.5)
    
    # Plot path with gradient colors
    segments = np.array([coords[i:i+2] for i in range(len(coords)-1)])
    n_segments = len(segments)
    colors = plt.cm.plasma(np.linspace(0, 1, n_segments))
    
    for i, segment in enumerate(segments):
        ax.plot(segment[:, 0], segment[:, 1], color=colors[i], linewidth=1.5, solid_capstyle='round')
    
    # Mark start and end
    ax.plot(coords[0, 0], coords[0, 1], 'o', color='#0d0887', markersize=12, label='Start', zorder=10)
    ax.plot(coords[-1, 0], coords[-1, 1], 's', color='#f0f921', markersize=12, label='End', zorder=10)
    
    ax.legend(loc='upper right', fontsize=12)
    ax.axis('off')
    plt.tight_layout()
    plt.show()

def generate_multilayer_gcode(connected_graph, num_layers=10, layer_height=0.2, nozzle_temp=200, bed_temp=60, speed=1200):
    """
    Generates FullControl steps for multiple layers of the same print path.
    
    Args:
        connected_graph: The connected print path graph
        num_layers: Number of layers to generate
        layer_height: Z-height per layer (mm)
        nozzle_temp: Nozzle temperature (°C)
        bed_temp: Bed temperature (°C)
        speed: Print speed (mm/min)
    
    Returns:
        list: List of FullControl step objects for all layers
    """
    import fullcontrol as fc
    
    # Extract ordered path once (reuse for all layers)
    deg1 = [n for n, d in connected_graph.degree() if d == 1]
    start_node = deg1[0] if deg1 else list(connected_graph.nodes())[0]
    path_nodes = list(nx.dfs_preorder_nodes(connected_graph, source=start_node))
    
    pos = nx.get_node_attributes(connected_graph, 'pos')
    
    # Build FullControl steps
    steps = []
    
    # Startup sequence (once)
    steps.append(fc.ManualGcode(text=f"M140 S{bed_temp} ; Set Bed Temp"))
    steps.append(fc.ManualGcode(text=f"M104 S{nozzle_temp} ; Set Nozzle Temp"))
    steps.append(fc.ManualGcode(text="G28 ; Home all axes"))
    steps.append(fc.ManualGcode(text=f"M190 S{bed_temp} ; Wait for Bed"))
    steps.append(fc.ManualGcode(text=f"M109 S{nozzle_temp} ; Wait for Nozzle"))
    steps.append(fc.ManualGcode(text="G92 E0 ; Reset Extruder"))
    
    # Generate multiple layers
    for layer_idx in range(num_layers):
        z_height = (layer_idx + 1) * layer_height
        
        print(f"  Layer {layer_idx + 1}/{num_layers} at Z={z_height:.2f}mm")
        
        # Travel to start
        first_pos = pos[path_nodes[0]]
        steps.append(fc.Point(x=first_pos[0], y=first_pos[1], z=z_height))
        
        # Enable extrusion
        steps.append(fc.Extruder(on=True))
        
        # Add path points
        for node in path_nodes[1:]:
            node_pos = pos[node]
            steps.append(fc.Point(x=node_pos[0], y=node_pos[1], z=z_height))
        
        # Disable extrusion
        steps.append(fc.Extruder(on=False))
    
    # End sequence
    steps.append(fc.ManualGcode(text="M104 S0 ; Turn off nozzle"))
    steps.append(fc.ManualGcode(text="M140 S0 ; Turn off bed"))
    steps.append(fc.ManualGcode(text="G28 X0 Y0 ; Home X Y"))
    
    return steps

def save_gcode_to_file(gcode, filename="output/print_path.gcode"):
    """
    Saves the G-code string to a file.
    """
    import os
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
    
    with open(filename, 'w') as f:
        f.write(gcode)
    
    print(f"G-code saved to {filename}")

# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == "__main__":
    # 1. Define Diamond Graph
    from unitcell import diamond_unit_cell, snake_unit_cell
    data = snake_unit_cell
    G = data.graph
    W, H = data.W, data.H

    plot_graph(G, title="Original Diamond Graph", width=W, height=H)

    print("1. Creating Periodic Graph...")
    p_G, mapping = create_periodic_multigraph(G, W, H)
    
    print("2. Finding ALL Eulerian Circuits...")
    # Get generator
    circuit_gen = find_all_eulerian_circuits(p_G)

    if not circuit_gen:
        print("   Graph is not Eulerian (cannot be printed continuously).")
    else:
        valid_solutions = []
        
        # Iterate through all found circuits
        for i, circuit in enumerate(circuit_gen):
            points, winding = calculate_path_winding(circuit, p_G, G, mapping)

            # Filter Logic: We want NON-ZERO winding (Crossing)
            if winding != (0, 0):
                valid_solutions.append((points, winding))
                print(f"   Circuit {i}: VALID Crossing {winding}")
            else:
                # Optional: Comment this out to reduce noise
                print(f"   Circuit {i}: Invalid Island {winding}")

        print(f"\n3. Found {len(valid_solutions)} valid printable paths.")
        
        if valid_solutions:
            # Example: Take the first valid solution
            example_points, example_winding = valid_solutions[12]
            print(f"   Example Winding: {example_winding}")
            
            threaded_edges = create_threaded_visit_graph(example_points, mapping)
            full_graph = tile_and_stitch_threads(G, threaded_edges, mapping, W, H, rows=3, cols=6)

            print(len([n for n in nx.connected_components(full_graph)]), "connected components in the full graph.")
            
            # Visualize all components in one graph with different colors
            plot_all_components_colored(full_graph, W, H, rows=3, cols=6)
            
            # plot_graph(full_graph, title="Tiled and Stitched Printable Graph", width=W*8, height=H*3)
            # plot_components_separately(full_graph, W, H, rows=3, cols=8)
            
            connected_graph , new_edges = connect_boundaries_robust(full_graph)
            print(f"Added {len(new_edges)} stitching edges to connect loose ends.")
            print(len([n for n in nx.connected_components(connected_graph)]), "connected components after stitching.")

            print("Plotting final print path with gradient colors...")
            plot_gradient_print_path(connected_graph, W, H, rows=3, cols=6)

            print("Generating multi-layer G-code with FullControl...")
            NUM_LAYERS = 20  # Generate 20 layers
            LAYER_HEIGHT = 0.2
            
            fc_steps = generate_multilayer_gcode(
                connected_graph, 
                num_layers=NUM_LAYERS,
                layer_height=LAYER_HEIGHT,
                nozzle_temp=200,
                bed_temp=60,
                speed=1200
            )
            
            print("Plotting G-code visualization...")
            try:
                import fullcontrol as fc
                fc.transform(fc_steps, 'plot')
            except Exception as e:
                print(f"Note: Could not plot with Plotly: {e}")
            
            print("Saving G-code to file...")
            import fullcontrol as fc
            gcode = fc.transform(fc_steps, 'gcode')
            save_gcode_to_file(gcode, filename="output/print_path.gcode")
            
            print(f"\nSUCCESS! G-code saved to: output/print_path.gcode")
            print(f"Print Details: {NUM_LAYERS} layers × {LAYER_HEIGHT}mm = {NUM_LAYERS * LAYER_HEIGHT}mm total height")

            print("Animating Printing Process...")
            ani = animate_printing_process(connected_graph, W, H, rows=3, cols=6, interval=100)
            plt.show()