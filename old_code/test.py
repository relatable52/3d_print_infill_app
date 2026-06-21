import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import math
import fullcontrol as fc

from unitcell import snake_unit_cell, honeycomb_unit_cell, reentrant_unit_cell

# ==========================================
# 1. GRAPH TRANSFORMATION (The "Pacman" Logic)
# ==========================================
def create_periodic_multigraph(original_graph, width, height, tolerance=1e-5):
    """
    Collapses boundary nodes of the unit cell into a periodic MultiGraph.
    Preserves original edge metadata for later plotting.
    """
    # Helper to find if two nodes are periodic pairs
    merge_logic = nx.Graph()
    merge_logic.add_nodes_from(original_graph.nodes())
    nodes = list(original_graph.nodes(data=True))
    
    for i in range(len(nodes)):
        u, data_u = nodes[i]
        for j in range(i + 1, len(nodes)):
            v, data_v = nodes[j]
            dx = abs(data_u['pos'][0] - data_v['pos'][0])
            dy = abs(data_u['pos'][1] - data_v['pos'][1])
            
            # Check Geometric Wrap (Left-Right or Top-Bottom)
            is_wrap = (
                ((abs(dx - width) < tolerance or dx < tolerance) and 
                 (abs(dy - height) < tolerance or dy < tolerance)) and
                not (dx < tolerance and dy < tolerance) # Avoid self-loops
            )
            if is_wrap:
                merge_logic.add_edge(u, v)

    # Build Mapping: Old ID -> New Group ID
    mapping = {} 
    for component in nx.connected_components(merge_logic):
        sorted_ids = sorted(list(component))
        new_id = "_".join(map(str, sorted_ids))
        for old_id in sorted_ids:
            mapping[old_id] = new_id
            
    # Map remaining nodes that didn't merge
    for n in original_graph.nodes():
        if n not in mapping:
            mapping[n] = str(n)

    # Create the Periodic MultiGraph
    P_G = nx.MultiGraph()
    # Add nodes (we don't strictly need pos here for the solver, but good for debug)
    for old_id, new_id in mapping.items():
        if new_id not in P_G:
            P_G.add_node(new_id)

    # Add edges with TRACKING info
    for u, v, data in original_graph.edges(data=True):
        new_u, new_v = mapping[u], mapping[v]
        edge_key = f"{u}-{v}"
        # Store original_u and original_v so we can plot them later!
        P_G.add_edge(new_u, new_v, key=edge_key, 
                     original_u=u, original_v=v, **data)
        
    return P_G, mapping

# ==========================================
# 2. THE SOLVER (Finds 2-Factors)
# ==========================================
class UnitCellSolver:
    def __init__(self, periodic_graph):
        self.graph = periodic_graph
        self.solutions = [] # Stores lists of selected edges
        
    def solve(self):
        self.solutions = []
        all_edges = list(self.graph.edges(keys=True, data=True))
        self._backtrack(0, [], all_edges)
        return self.solutions

    def _backtrack(self, idx, selected_edges, all_edges):
        # 1. Pruning: Check if we violated degree constraint (>2)
        if not self._is_valid_partial(selected_edges): return

        # 2. Base Case: Checked all edges
        if idx == len(all_edges):
            if self._is_complete(selected_edges):
                self.solutions.append(list(selected_edges))
            return

        # 3. Recursion
        edge = all_edges[idx]
        
        # Branch A: Include this edge
        self._backtrack(idx + 1, selected_edges + [edge], all_edges)
        
        # Branch B: Skip this edge
        self._backtrack(idx + 1, selected_edges, all_edges)

    def _is_valid_partial(self, edges):
        deg = {}
        for u, v, k, d in edges:
            deg[u] = deg.get(u, 0) + 1
            deg[v] = deg.get(v, 0) + 1
            if deg[u] > 2 or deg[v] > 2: return False
        return True

    def _is_complete(self, edges):
        # Ensure EVERY node in the periodic graph has exactly degree 2
        deg = {n: 0 for n in self.graph.nodes()}
        for u, v, k, d in edges:
            deg[u] += 1
            deg[v] += 1
        return all(d == 2 for d in deg.values())

# ==========================================
# 3. VISUALIZATION (Plotting on Original Graph)
# ==========================================
def plot_all_solutions(original_graph, solutions, width, height):
    """
    Iterates through all found solutions and plots them using 
    the ORIGINAL positions.
    """
    if not solutions:
        print("No solutions found to plot.")
        return

    num_sols = len(solutions)
    
    # 1. Determine Grid Layout (e.g., max 4 columns)
    cols = 4 if num_sols >= 4 else num_sols
    rows = math.ceil(num_sols / cols)
    
    # 2. Create the Figure
    # Adjust figsize to make sure each subplot is readable (approx 4x4 inches per plot)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    
    # Handle the case where there is only 1 solution (axes is not a list)
    if num_sols == 1:
        axes_list = [axes]
    else:
        axes_list = axes.flatten()

    pos = nx.get_node_attributes(original_graph, 'pos')

    # 3. Iterate through axes
    for i, ax in enumerate(axes_list):
        if i < num_sols:
            solution_edges = solutions[i]
            
            # --- DRAWING ON SUBPLOT (using ax=ax) ---
            
            # A. Draw Unit Cell Box
            ax.plot([0, width, width, 0, 0], [0, 0, height, height, 0], 'k--', alpha=0.3)
            
            # B. Draw Faint Background Graph
            nx.draw_networkx_nodes(original_graph, pos, node_size=30, node_color='lightgray', ax=ax)
            nx.draw_networkx_edges(original_graph, pos, edge_color='lightgray', width=1, style=':', ax=ax)
            
            # C. Draw The Solution Path
            active_edgelist = []
            for u_pe, v_pe, key, data in solution_edges:
                active_edgelist.append((data['original_u'], data['original_v']))

            # Draw Edges
            nx.draw_networkx_edges(original_graph, pos, edgelist=active_edgelist, 
                                   width=3, edge_color='tab:blue', ax=ax)
            
            # Draw Nodes involved
            active_nodes = set()
            for u, v in active_edgelist:
                active_nodes.add(u)
                active_nodes.add(v)
                
            nx.draw_networkx_nodes(original_graph, pos, nodelist=list(active_nodes),
                                   node_size=80, node_color='tab:blue', ax=ax)
            
            ax.set_title(f"Solution {i+1}", fontsize=10, fontweight='bold')
            ax.set_aspect('equal')
            ax.axis('off') # Clean look
            
        else:
            # Hide unused subplots if the grid is larger than N solutions
            ax.axis('off')

    plt.tight_layout()
    plt.show()

def plot_tiled_layer(original_graph, solution_edges, width, height, grid_size=(3, 3), layer_name="Layer"):
    """
    Tiles a specific solution across a grid to visualize the full layer pattern.
    
    Args:
        original_graph: The original unit cell graph with 'pos'.
        solution_edges: The list of edges (from the solver) for this layer.
        width, height: Dimensions of the unit cell.
        grid_size: Tuple (rows, cols) for the grid (e.g., (3, 3)).
        layer_name: Title for the plot.
    """
    rows, cols = grid_size
    pos = nx.get_node_attributes(original_graph, 'pos')
    
    # Create a new figure
    # Scale figure size based on grid dimensions
    plt.figure(figsize=(4 * cols, 4 * rows))
    
    # 1. Iterate through every cell in the grid
    for r in range(rows):
        for c in range(cols):
            # Calculate the offset for this specific cell
            offset_x = c * width
            offset_y = r * height
            offset = np.array([offset_x, offset_y])
            
            # Draw the Unit Cell Boundary (Dashed Box)
            # Box corners: (0,0), (W,0), (W,H), (0,H), (0,0) + Offset
            box_x = np.array([0, width, width, 0, 0]) + offset_x
            box_y = np.array([0, 0, height, height, 0]) + offset_y
            plt.plot(box_x, box_y, 'k:', alpha=0.2) # Very faint boundary
            
            # 2. Draw the Edges of the Solution
            for u_pe, v_pe, key, data in solution_edges:
                # Get original node IDs
                u_orig = data['original_u']
                v_orig = data['original_v']
                
                # Get original positions
                p1 = np.array(pos[u_orig])
                p2 = np.array(pos[v_orig])
                
                # Apply Offset
                p1_shifted = p1 + offset
                p2_shifted = p2 + offset
                
                # Plot the segment
                plt.plot([p1_shifted[0], p2_shifted[0]], 
                         [p1_shifted[1], p2_shifted[1]], 
                         color='tab:blue', linewidth=3)
                
                # Optional: Plot 'dots' at the nodes to visualize connections
                plt.scatter([p1_shifted[0], p2_shifted[0]], 
                            [p1_shifted[1], p2_shifted[1]], 
                            color='tab:blue', s=20, zorder=5)

    plt.title(f"{layer_name} Tiling ({rows}x{cols})", fontsize=15)
    plt.axis('equal')
    plt.axis('off') # Turn off axis numbers for cleaner look
    plt.tight_layout()
    plt.show()

def plot_graph(G, title="Graph Plot", width=None, height=None):
    """
    Plots a networkx graph using its 'pos' node attributes.
    Optionally draws a unit cell boundary if width/height are provided.
    """
    # 1. Extract positions
    pos = nx.get_node_attributes(G, 'pos')
    
    if not pos:
        print("Error: Graph nodes do not have 'pos' attributes.")
        return

    plt.figure(figsize=(8, 8))
    
    # 2. Draw Unit Cell Boundary (if dimensions provided)
    if width is not None and height is not None:
        boundary_x = [0, width, width, 0, 0]
        boundary_y = [0, 0, height, height, 0]
        plt.plot(boundary_x, boundary_y, 'k--', alpha=0.5, label='Unit Cell')
        plt.legend()

    # 3. Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color='skyblue', edgecolors='black')
    
    # 4. Draw Edges
    # Check if it's a MultiGraph (multiple edges between nodes) to handle curvature
    if isinstance(G, nx.MultiGraph):
        # Draw edges with curvature so parallel edges are visible
        ax = plt.gca()
        for u, v, key, data in G.edges(keys=True, data=True):
            # Generate a connection style based on the key to separate edges visually
            rad = 0.1 * (key + 1) if isinstance(key, int) else 0.1
            nx.draw_networkx_edges(
                G, pos, edgelist=[(u, v)], 
                connectionstyle=f'arc3, rad={rad}', 
                edge_color='black'
            )
    else:
        nx.draw_networkx_edges(G, pos, width=2, edge_color='black')

    # 5. Draw Labels
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')

    # 6. Formatting
    plt.title(title)
    plt.axis('equal')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.show()

# ==========================================
# 4. INTEGER WINDING CHECK
# ==========================================
def analyze_solution_validity(solution_edges, original_graph, mapping, width, height):
    """
    Validates the solution using Integer Winding Logic.
    """
    sol_graph = nx.MultiGraph()
    edge_db = {}
    
    # Rebuild graph
    for u_merge, v_merge, key, data in solution_edges:
        sol_graph.add_edge(u_merge, v_merge, key=key)
        edge_db[(u_merge, v_merge, key)] = data
        edge_db[(v_merge, u_merge, key)] = data

    loops = list(nx.connected_components(sol_graph))
    loop_results = []
    
    for loop_nodes in loops:
        subgraph = sol_graph.subgraph(loop_nodes).copy()
        try:
            ordered_edges = list(nx.eulerian_circuit(subgraph, keys=True))
        except nx.NetworkXError:
            return False, ["Invalid Topology"]

        # --- A. Build Physical Path Sequence ---
        path_sequence = []
        
        for u_merge, v_merge, key in ordered_edges:
            data = edge_db[(u_merge, v_merge, key)]
            u_orig = data['original_u']
            v_orig = data['original_v']
            
            # Determine physical direction based on mapping
            # We traverse u_merge -> v_merge
            if mapping[u_orig] == u_merge and mapping[v_orig] == v_merge:
                phys_start = u_orig
                phys_end = v_orig
            elif mapping[v_orig] == u_merge and mapping[u_orig] == v_merge:
                phys_start = v_orig
                phys_end = u_orig
            else:
                # Fallback for self-loops (should typically not happen in valid 2-factor)
                phys_start = u_orig
                phys_end = v_orig

            path_sequence.append((phys_start, phys_end))

        # --- B. Calculate Integer Winding ---
        wind_x = 0
        wind_y = 0
        
        for i in range(len(path_sequence)):
            curr_start, curr_end = path_sequence[i]
            
            # Previous edge info
            prev_idx = (i - 1) % len(path_sequence)
            prev_start, prev_end = path_sequence[prev_idx]
            
            # Check for Jump (Connectivity Break)
            if curr_start == prev_end:
                # Continuous path, no winding change
                continue
            
            # If we are here, we jumped!
            pos_prev_end = np.array(original_graph.nodes[prev_end]['pos'])
            pos_curr_start = np.array(original_graph.nodes[curr_start]['pos'])
            
            # Use small tolerance for float comparison
            tol = 1e-5
            
            # X-Direction Logic
            if pos_curr_start[0] > pos_prev_end[0] + tol:
                wind_x += 1  # Jumped to Right
            elif pos_curr_start[0] < pos_prev_end[0] - tol:
                wind_x -= 1  # Jumped to Left
                
            # Y-Direction Logic
            if pos_curr_start[1] > pos_prev_end[1] + tol:
                wind_y += 1  # Jumped Up
            elif pos_curr_start[1] < pos_prev_end[1] - tol:
                wind_y -= 1  # Jumped Down

        # --- C. Check Result ---
        if wind_x == 0 and wind_y == 0:
            loop_results.append("ISLAND")
        else:
            loop_results.append(f"CROSSING ({wind_x}, {wind_y})")

    return not any("ISLAND" in res for res in loop_results), loop_results

def create_tiled_layer_graph(original_graph, solution_edges, width, height, grid_rows, grid_cols):
    """
    Creates a single connected graph representing a grid of unit cells,
    stitching them together at the boundaries.
    """
    full_graph = nx.Graph()
    
    # 1. TILE: Create all nodes and edges with offset positions
    # We use a naming convention: "nodeID_rX_cY"
    
    # Helper to generate ID
    def get_id(u, r, c):
        return f"{u}_r{r}_c{c}"

    for r in range(grid_rows):
        for c in range(grid_cols):
            offset_x = c * width
            offset_y = r * height
            
            # Add nodes/edges for this cell
            for u_pe, v_pe, key, data in solution_edges:
                u_orig = data['original_u']
                v_orig = data['original_v']
                
                # Original positions
                pos_u = np.array(original_graph.nodes[u_orig]['pos'])
                pos_v = np.array(original_graph.nodes[v_orig]['pos'])
                
                # New IDs
                node_u_new = get_id(u_orig, r, c)
                node_v_new = get_id(v_orig, r, c)
                
                # Add nodes with transformed positions
                full_graph.add_node(node_u_new, pos=(pos_u[0] + offset_x, pos_u[1] + offset_y))
                full_graph.add_node(node_v_new, pos=(pos_v[0] + offset_x, pos_v[1] + offset_y))
                
                # Add edge
                full_graph.add_edge(node_u_new, node_v_new)

    # 2. STITCH: Merge boundary nodes
    # We use nx.contracted_nodes to merge, but that can be slow on large graphs.
    # Faster way: Relabel edges to point to the "merged" ID.
    # Let's use a mapping dictionary to handle merges.
    
    # Dictionary: mapping[node_id] -> parent_node_id
    # Initialize pointing to self
    uf_map = {n: n for n in full_graph.nodes()}
    
    def find(n):
        if uf_map[n] != n:
            uf_map[n] = find(uf_map[n])
        return uf_map[n]

    def union(n1, n2):
        root1 = find(n1)
        root2 = find(n2)
        if root1 != root2:
            uf_map[root2] = root1

    # A. Horizontal Stitching (Col c to c+1)
    # We need to know which pairs in the original graph are "Periodic Horizontal Pairs"
    # We can re-derive this or pass it in. Let's do a quick geometric check on the original graph.
    left_nodes = []
    right_nodes = []
    top_nodes = []
    bot_nodes = []
    
    orig_pos = nx.get_node_attributes(original_graph, 'pos')
    tol = 1e-4
    
    for n, p in orig_pos.items():
        if abs(p[0]) < tol: left_nodes.append(n)
        if abs(p[0] - width) < tol: right_nodes.append(n)
        if abs(p[1]) < tol: bot_nodes.append(n)
        if abs(p[1] - height) < tol: top_nodes.append(n)

    # Match Left/Right pairs
    # Pair format: (LeftNode, RightNode)
    horiz_pairs = []
    for l in left_nodes:
        p_l = orig_pos[l]
        for r_n in right_nodes:
            p_r = orig_pos[r_n]
            if abs(p_l[1] - p_r[1]) < tol: # Same Y
                horiz_pairs.append((l, r_n))
                
    # Match Top/Bottom pairs
    vert_pairs = []
    for b in bot_nodes:
        p_b = orig_pos[b]
        for t in top_nodes:
            p_t = orig_pos[t]
            if abs(p_b[0] - p_t[0]) < tol: # Same X
                vert_pairs.append((b, t))

    # Perform Stitching
    for r in range(grid_rows):
        for c in range(grid_cols):
            # Horizontal (Stitch Right of current to Left of next)
            if c < grid_cols - 1:
                for l_orig, r_orig in horiz_pairs:
                    # Node on Right of current cell
                    n1 = get_id(r_orig, r, c) 
                    # Node on Left of next cell
                    n2 = get_id(l_orig, r, c + 1)
                    
                    if full_graph.has_node(n1) and full_graph.has_node(n2):
                        union(n1, n2)

            # Vertical (Stitch Top of current to Bottom of next)
            if r < grid_rows - 1:
                for b_orig, t_orig in vert_pairs:
                    # Node on Top of current cell
                    n1 = get_id(t_orig, r, c)
                    # Node on Bottom of next cell
                    n2 = get_id(b_orig, r + 1, c)
                    
                    if full_graph.has_node(n1) and full_graph.has_node(n2):
                        union(n1, n2)

    # 3. REBUILD GRAPH
    # Create the final graph using the representative IDs from the union-find
    stitched_graph = nx.Graph()
    
    # Copy node positions (using the position of the root)
    for n in full_graph.nodes():
        root = find(n)
        if root not in stitched_graph:
            stitched_graph.add_node(root, pos=full_graph.nodes[n]['pos'])
            
    # Copy edges (remapped)
    for u, v in full_graph.edges():
        root_u = find(u)
        root_v = find(v)
        if root_u != root_v:
            stitched_graph.add_edge(root_u, root_v)
            
    return stitched_graph

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

# ==========================================
# 1. GRAPH TRAVERSAL (Graph -> Ordered Points)
# ==========================================
def graph_to_ordered_paths(grid_graph):
    """
    Converts a networkx graph (representing a toolpath) into a list of 
    ordered coordinate lists. 
    
    Returns: [[(x,y), (x,y), ...], [(x,y), ...]]
    (Multiple lists returned if the graph has disconnected islands)
    """
    paths = []
    
    # 1. Decompose into connected components
    # (Ideally, your 'robust stitch' made this 1 component, but we handle islands just in case)
    components = [grid_graph.subgraph(c).copy() for c in nx.connected_components(grid_graph)]
    
    for comp in components:
        # 2. Find Start Node (Degree 1)
        # If it's a closed loop (all degree 2), pick any node.
        # If it's a line (two degree 1s), pick one.
        odd_degree_nodes = [n for n, d in comp.degree() if d % 2 == 1]
        
        start_node = None
        if odd_degree_nodes:
            # Pick the one with smallest Y or X (consistent starting logic)
            # odd_degree_nodes.sort(key=lambda n: comp.nodes[n]['pos'][1])
            start_node = odd_degree_nodes[0]
        else:
            # Closed loop, pick arbitrary
            start_node = list(comp.nodes())[0]
            
        # 3. Walk the graph (Eulerian Path or DFS)
        # Since we enforced max degree 2 in unit cell and stitched end-to-end,
        # this is essentially a simple line walk.
        
        ordered_nodes = list(nx.dfs_preorder_nodes(comp, source=start_node))
        
        # Extract coordinates
        pos_dict = nx.get_node_attributes(comp, 'pos')
        path_coords = [tuple(pos_dict[n]) for n in ordered_nodes]
        paths.append(path_coords)
        
    return paths

# ==========================================
# 2. FULLCONTROL G-CODE GENERATOR
# ==========================================
def generate_lattice_gcode(
    original_graph, 
    valid_solutions, 
    layer_sequence, # e.g., [0, 1, 0, 1, 2]
    unit_cell_size, # (W, H)
    grid_size,      # (Rows, Cols)
    print_settings
):
    """
    Generates G-code using FullControl.
    """
    W, H = unit_cell_size
    rows, cols = grid_size
    layer_h = print_settings.get('layer_height', 0.2)
    nozzle_temp = print_settings.get('nozzle_temp', 200)
    bed_temp = print_settings.get('bed_temp', 60)
    speed = print_settings.get('speed', 1000) # mm/min
    
    print(f"Generating G-code for {len(layer_sequence)} layers...")
    
    # --- Pre-compute Geometries for unique solutions ---
    # We don't want to re-stitch the graph for every single layer if patterns repeat.
    unique_indices = set(layer_sequence)
    path_cache = {}
    
    for idx in unique_indices:
        print(f"  Pre-processing topology for Solution {idx}...")
        # 1. Tile
        tiled_G = create_tiled_layer_graph(
            original_graph, valid_solutions[idx], W, H, rows, cols
        )
        # 2. Stitch
        stitched_G, _ = connect_boundaries_robust(tiled_G)
        # 3. Convert to Path
        path_cache[idx] = graph_to_ordered_paths(stitched_G)

    # --- Build FullControl Steps ---
    steps = []
    
    # Startup Sequence (Home, Heat, Prime)
    # FC allows manual gcode insertion
    steps.append(fc.ManualGcode(text=f"M140 S{bed_temp} ; Set Bed Temp"))
    steps.append(fc.ManualGcode(text=f"M104 S{nozzle_temp} ; Set Nozzle Temp"))
    steps.append(fc.ManualGcode(text="G28 ; Home all axes"))
    steps.append(fc.ManualGcode(text=f"M190 S{bed_temp} ; Wait for Bed"))
    steps.append(fc.ManualGcode(text=f"M109 S{nozzle_temp} ; Wait for Nozzle"))
    steps.append(fc.ManualGcode(text="G92 E0 ; Reset Extruder"))
    
    # Loop Layers
    for i, sol_idx in enumerate(layer_sequence):
        z_height = (i + 1) * layer_h
        paths = path_cache[sol_idx]
        
        # Iterate through components (if graph was disjoint)
        for path_points in paths:
            # 1. Travel to Start (Extrusion Off)
            start_x, start_y = path_points[0]
            steps.append(fc.Point(x=start_x, y=start_y, z=z_height)) # Move to start
            
            # 2. Print Path (Extrusion On)
            steps.append(fc.Extruder(on=True))
            for x, y in path_points[1:]:
                steps.append(fc.Point(x=x, y=y, z=z_height))
            
            # 3. End Path (Extrusion Off)
            steps.append(fc.Extruder(on=False))
            
            # Optional: Z-hop or Retraction could be added here
            
    # End Gcode
    steps.append(fc.ManualGcode(text="M104 S0 ; Turn off nozzle"))
    steps.append(fc.ManualGcode(text="M140 S0 ; Turn off bed"))
    steps.append(fc.ManualGcode(text="G28 X0 Y0 ; Home X Y"))
    
    return steps

# ==========================================
# 5. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # --- A. Define the Unit Cell Graph (Honeycomb-ish Example) ---

    W = reentrant_unit_cell.W
    H = reentrant_unit_cell.H
    G = reentrant_unit_cell.graph

    # --- B. Process & Solve ---
    print("1. Creating Periodic Graph...")
    periodic_G, mapping = create_periodic_multigraph(G, W, H)
    print(f"   Collapsed {len(G.nodes())} nodes -> {len(periodic_G.nodes())} periodic nodes.")
    # print(periodic_G.edges(data=True))
    # print("kkkkkk", mapping)


    print("2. Solving for 2-Factors...")
    solver = UnitCellSolver(periodic_G)
    solutions = solver.solve()
    print(f"   Found {len(solutions)} valid path configurations.")
    # print(solutions)
    
    valid_soltions = []
    for solution in solutions:
        is_valid, loop_info = analyze_solution_validity(solution, G, mapping, W, H)
        validity_str = "Valid" if is_valid else "Invalid"
        print(f"   Solution Validity: {validity_str} | Loop Info: {loop_info}")
        if is_valid:
            valid_soltions.append(solution)

    # --- C. Plot ---
    print("3. Plotting Results...")
    plot_all_solutions(G, solutions, W, H)

    grid_G = create_tiled_layer_graph(G, valid_soltions[1], W, H, grid_rows=6, grid_cols=6)
    plot_graph(grid_G, title="Tiled Layer Graph (5x5)", width=W*6, height=H*6)

    final_graph, stitched_edges = connect_boundaries_robust(grid_G)
    plot_graph(final_graph, title="Final Connected Layer Graph", width=W*6, height=H*6)
    
    GRID_ROWS, GRID_COLS = 6, 6
    LAYER_SEQ = [0, 3, 0, 3] * 5 # 30 Layers total
    
    SETTINGS = {
        'layer_height': 0.2,
        'nozzle_temp': 210,
        'bed_temp': 60,
        'speed': 1500
    }

    offset_x = 100
    offset_y = 100
    
    fc_steps = generate_lattice_gcode(
        original_graph=G,
        valid_solutions=valid_soltions, # List of edge-lists
        layer_sequence=LAYER_SEQ,
        unit_cell_size=(W, H),
        grid_size=(GRID_ROWS, GRID_COLS),
        print_settings=SETTINGS
    )
    
    # --- Transform to Bed Center ---
    # Move the whole design to the middle of the bed
    # fc_steps = fc.transform(fc_steps, 'translate', {'x': offset_x, 'y': offset_y})

    # --- Export ---
    # 1. Visualize (Optional, requires Plotly usually)
    fc.transform(fc_steps, 'plot') 

    # 2. Save G-code
    gcode = fc.transform(fc_steps, 'gcode')
    
    filename = "lattice_structure.gcode"
    with open(filename, "w") as f:
        f.write(gcode)
    print(fc_steps[:10])
        
    print(f"\nSUCCESS! G-code saved to: {filename}")
    print(f"Print Details: {GRID_ROWS}x{GRID_COLS} Grid, {len(LAYER_SEQ)} Layers.")

