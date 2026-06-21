import networkx as nx
import numpy as np
import fullcontrol as fc
import matplotlib.pyplot as plt
from matplotlib import animation
from unitcell import snake_unit_cell, honeycomb_unit_cell, diamond_unit_cell, create_super_unit_cell

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
    print("Circuit edges in periodic graph:", circuit_edges)
    for u_merge, v_merge, key in circuit_edges:
        data = periodic_graph[u_merge][v_merge][key]
        print(f"Processing edge {u_merge} -> {v_merge} | Original: {data['original_u']} -> {data['original_v']}")
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
        plt.plot([0, width, width, 0, 0], [0, 0, height, height, 0], 'k--', alpha=0.5)
    nx.draw_networkx(G, pos, node_size=500, node_color='skyblue', font_weight='bold')
    plt.title(title)
    plt.axis('equal')
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
        plt.title(f"Component {i+1}", fontsize=10, fontweight='bold')
        plt.gca().set_aspect('equal')
        plt.axis('off')
        
        # Add boundary box for context
        plt.plot([0, width*cols, width*cols, 0, 0], [0, 0, height*rows, height*rows, 0], 'k--', alpha=0.2)
        
        plt.tight_layout()
        plt.show()

# ==========================================
# 3. ROBUST CONNECTOR (Greedy Top-Left)
# ==========================================

def get_node_pos(G, n):
    """Returns position as tuple (x, y)."""
    p = G.nodes[n]['pos']
    return (p[0], p[1])

def get_top_left_score(pos_tuple):
    """
    Sorting Key for 'Top-Left'.
    Primary: Y (Descending) -> Maximize Y
    Secondary: X (Ascending) -> Minimize X
    
    Returns a tuple that sorts correctly with standard Python sort (min).
    To maximize Y, we use -Y.
    """
    x, y = pos_tuple
    return (-y, x)

def connect_boundaries_robust(grid_graph):
    """
    Stitches components using a Top-Left Greedy strategy.
    
    Robustness Update:
    1. Tries to find the closest NON-INTERSECTING path.
    2. If that fails, FALLS BACK to the closest INTERSECTING path.
    """
    pos_attr = nx.get_node_attributes(grid_graph, 'pos')
    
    # 1. Pre-compute Component Data (Ports & Internal Geometry)
    components = []
    raw_comps = list(nx.connected_components(grid_graph))
    
    for i, comp_nodes in enumerate(raw_comps):
        subgraph = grid_graph.subgraph(comp_nodes)
        comp_ports = [n for n, d in subgraph.degree() if d == 1]
        
        if len(comp_ports) == 0: continue 
        
        internal_pos = set()
        for n in comp_nodes:
            if grid_graph.degree(n) > 1:
                p = get_node_pos(grid_graph, n)
                internal_pos.add((round(p[0], 4), round(p[1], 4)))
                
        components.append({
            'id': i,
            'ports': comp_ports,
            'internal_pos': internal_pos,
            'connected': False
        })

    print(f"Identified {len(components)} components.")
    if not components: return grid_graph, []

    new_edges = []
    
    # 2. Find Global Start (Top-Leftmost Port)
    best_score = (float('inf'), float('inf'))
    curr_comp_idx = -1
    best_start_port = None
    
    for i, comp in enumerate(components):
        for port in comp['ports']:
            score = get_top_left_score(get_node_pos(grid_graph, port))
            if score < best_score:
                best_score = score
                curr_comp_idx = i
                best_start_port = port
                
    # 3. Initialize Chain
    components[curr_comp_idx]['connected'] = True
    
    # Determine initial exit port
    if len(components[curr_comp_idx]['ports']) == 1:
        curr_exit_port = best_start_port
    else:
        p1, p2 = components[curr_comp_idx]['ports'][:2]
        curr_exit_port = p2 if p1 == best_start_port else p1
    
    blob_internal_pos = components[curr_comp_idx]['internal_pos'].copy()
    
    # 4. Greedy Loop with Fallback
    while True:
        candidates = []
        p_exit = np.array(pos_attr[curr_exit_port])
        
        # Collect ALL valid next steps (unvisited components)
        for i, comp in enumerate(components):
            if comp['connected']: continue
            
            for port in comp['ports']:
                p_target = np.array(pos_attr[port])
                dist = np.linalg.norm(p_exit - p_target)
                tl_score = get_top_left_score((p_target[0], p_target[1]))
                
                candidates.append({
                    'dist': dist,
                    'tl_score': tl_score,
                    'comp_idx': i,
                    'entry_port': port
                })
        
        if not candidates:
            break
            
        # Sort: 1. Closest Distance, 2. Top-Left Priority
        candidates.sort(key=lambda x: (x['dist'], x['tl_score']))
        
        selected_cand = None
        
        # --- PASS 1: Strict Check (Non-Intersecting) ---
        for cand in candidates:
            cand_idx = cand['comp_idx']
            cand_comp = components[cand_idx]
            
            # Check overlap
            is_intersecting = not blob_internal_pos.isdisjoint(cand_comp['internal_pos'])
            
            if not is_intersecting:
                selected_cand = cand
                break
        
        # --- PASS 2: Fallback (Allow Intersection) ---
        if not selected_cand:
            print("  Warning: No clean path. Forcing overlapping connection.")
            # Pick the closest one regardless of intersection
            selected_cand = candidates[0]
            
        # Execute Connection
        cand_idx = selected_cand['comp_idx']
        cand_comp = components[cand_idx]
        target_port = selected_cand['entry_port']
        
        # 1. Add Edge
        grid_graph.add_edge(curr_exit_port, target_port)
        new_edges.append((curr_exit_port, target_port))
        
        # 2. Update Geometry
        blob_internal_pos.update(cand_comp['internal_pos'])
        
        # 3. Mark Visited
        components[cand_idx]['connected'] = True
        
        # 4. Advance Exit Port
        # Logic: Enter at target_port -> Exit at the *other* port
        c_ports = cand_comp['ports']
        if len(c_ports) == 1:
            curr_exit_port = target_port 
        else:
            # If standard 2-port line, pick the one we didn't enter
            if target_port == c_ports[0]:
                curr_exit_port = c_ports[1]
            else:
                curr_exit_port = c_ports[0]

    print(f"Stitching complete. Added {len(new_edges)} connections.")
    return grid_graph, new_edges

# ==========================================
# 5. ANIMATION OF PRINTING PROCESS
# ==========================================

def extract_printing_path(connected_graph):
    """
    Extract ordered path from the connected graph.
    Returns list of (x, y) coordinates.
    """
    # Extract Ordered Path (DFS)
    deg1 = [n for n, d in connected_graph.degree() if d == 1]
    start_node = deg1[0] if deg1 else list(connected_graph.nodes())[0]
    path_nodes = list(nx.dfs_preorder_nodes(connected_graph, source=start_node))
    
    pos = nx.get_node_attributes(connected_graph, 'pos')
    # Convert path to coordinates
    path_coords = [(pos[n][0], pos[n][1]) for n in path_nodes]
    
    return path_coords, path_nodes

def export_to_gcode_fullcontrol(connected_graph, filename="output.gcode", 
                                 num_layers=1, layer_height=0.2, extrusion_width=0.4,
                                 nozzle_temp=210, bed_temp=60, print_speed=1000,
                                 scale_xy=1.0):
    """
    Export the printing path to G-code using FullControl.
    
    Parameters:
    - connected_graph: The graph containing the printing path
    - filename: Output G-code filename
    - num_layers: Number of layers to print (default 1)
    - layer_height: Layer height in mm (default 0.2)
    - extrusion_width: Extrusion width in mm (default 0.4)
    - nozzle_temp: Nozzle temperature in Celsius (default 210)
    - bed_temp: Bed temperature in Celsius (default 60)
    - print_speed: Print speed in mm/min (default 1000)
    - scale_xy: XY scaling factor (default 1.0)
    """
    
    # Extract path
    path_coords, path_nodes = extract_printing_path(connected_graph)
    
    print(f"Generating G-code for {len(path_coords)} points per layer x {num_layers} layers...")
    print(f"Scale: {scale_xy}x, Total height: {num_layers * layer_height}mm")
    
    # Create FullControl steps
    steps = []
    
    # Generate path for each layer
    for layer in range(num_layers):
        z = (layer + 1) * layer_height
        
        # For each layer, traverse the entire path
        for i, (x, y) in enumerate(path_coords):
            # Apply scaling
            x_scaled = x * scale_xy
            y_scaled = y * scale_xy
            
            if layer == 0 and i == 0:
                # First point - move without extrusion
                steps.append(fc.Point(x=x_scaled, y=y_scaled, z=z))
            else:
                # All other points with extrusion
                steps.append(fc.Point(x=x_scaled, y=y_scaled, z=z))

    # Visualize (Optional)
    fc.transform(steps, 'plot')
    
    # Generate G-code
    gcode = fc.transform(steps, 'gcode', fc.GcodeControls(
        printer_name='generic',  # Use generic printer
        initialization_data={
            'nozzle_temp': nozzle_temp,
            'bed_temp': bed_temp,
            'print_speed': print_speed,
            'extrusion_width': extrusion_width,
            'layer_height': layer_height
        }
    ))
    
    # Save to file
    with open(filename, 'w') as f:
        f.write(gcode)
    
    print(f"G-code saved to {filename}")
    return gcode

def animate_printing_process(connected_graph, width, height, rows, cols, interval=50):
    """
    Creates an animation of the printing path.
    """
    # 1. Extract Ordered Path
    path_coords, path_nodes = extract_printing_path(connected_graph)
    path_x = [p[0] for p in path_coords]
    path_y = [p[1] for p in path_coords]
    
    # 2. Setup Plot
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(-width*0.2, width*cols*1.2)
    ax.set_ylim(-height*0.2, height*rows*1.2)
    ax.set_aspect('equal')
    ax.set_title("G-code Printing Simulation")
    
    # Draw Background (Faint grid)
    # nx.draw_networkx_edges(connected_graph, pos, edge_color='#f0f0f0', width=1, ax=ax)
    
    # Draw Bounding Box
    ax.plot([0, width*cols, width*cols, 0, 0], [0, 0, height*rows, height*rows, 0], 'k--', alpha=0.3)

    # Plot Elements (Line and Nozzle Head)
    line, = ax.plot([], [], 'b-', linewidth=2, label='Extruded Material')
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

# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == "__main__":
    # Define unit cell to use
    unit_cell = create_super_unit_cell(diamond_unit_cell, rows=1, cols=1)
    G = unit_cell.graph
    W = unit_cell.W
    H = unit_cell.H

    plot_graph(G, title="Original Graph", width=W, height=H)

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
            example_points, example_winding = valid_solutions[1]
            print(f"   Example Winding: {example_winding}")
            
            threaded_edges = create_threaded_visit_graph(example_points, mapping)
            full_graph = tile_and_stitch_threads(G, threaded_edges, mapping, W, H, rows=10, cols=30)

            print(len([n for n in nx.connected_components(full_graph)]), "connected components in the full graph.")
            
            
            # plot_graph(full_graph, title="Tiled and Stitched Printable Graph", width=W*75, height=H*25)
            # plot_components_separately(full_graph, W, H, rows=25, cols=75)
            
            connected_graph , new_edges = connect_boundaries_robust(full_graph)
            print(f"Added {len(new_edges)} stitching edges to connect loose ends.")
            print(len([n for n in nx.connected_components(connected_graph)]), "connected components after stitching.")

            # Export to G-code using FullControl
            print("\nExporting to G-code...")
            
            # Configuration parameters
            DESIRED_HEIGHT = 3.0  # mm
            NUM_LAYERS = 30  # Number of layers to print
            LAYER_HEIGHT = 0.2  # mm per layer
            SCALE_XY = DESIRED_HEIGHT / H   # Scaling factor (1.0 = no scaling, 2.0 = double size)
            
            gcode = export_to_gcode_fullcontrol(
                connected_graph, 
                filename=f"output_print_{DESIRED_HEIGHT}.gcode",
                num_layers=NUM_LAYERS,
                layer_height=LAYER_HEIGHT,
                extrusion_width=0.4,
                nozzle_temp=210,
                bed_temp=60,
                print_speed=1000,
                scale_xy=SCALE_XY
            )

            print("Animating Printing Process...")
            ani = animate_printing_process(connected_graph, W, H, rows=10, cols=30, interval=100)
            # ani.save('printing_simulation_2.gif', writer='pillow', dpi=150, fps=30)
            plt.show()