import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from unitcell import diamond_unit_cell, snake_unit_cell, create_super_unit_cell

# ==========================================
# 1. YOUR EXISTING GRAPH LOGIC (Kept Unchanged)
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

def find_all_eulerian_circuits(graph):
    """
    Generator that yields ALL distinct Eulerian circuits.
    """
    if not nx.is_eulerian(graph):
        return

    total_edges = graph.number_of_edges()
    start_node = list(graph.nodes())[0]

    def backtrack(current_node, current_path, remaining_graph):
        if len(current_path) == total_edges:
            yield list(current_path)
            return

        available = list(remaining_graph.edges(current_node, keys=True, data=True))
        
        for u, v, key, data in available:
            remaining_graph.remove_edge(u, v, key=key)
            yield from backtrack(v, current_path + [(u, v, key)], remaining_graph)
            remaining_graph.add_edge(u, v, key=key, **data)

    yield from backtrack(start_node, [], graph.copy())

def calculate_path_winding(circuit_edges, periodic_graph, original_graph, mapping):
    """
    Converts periodic edges to physical points and calculates winding.
    """
    wind_x, wind_y = 0, 0
    ordered_physical_edges = []

    for u_merge, v_merge, key in circuit_edges:
        data = periodic_graph[u_merge][v_merge][key]
        u_orig = data['original_u']
        v_orig = data['original_v']
        
        if mapping[u_orig] == u_merge:
            start, end = u_orig, v_orig
        else:
            start, end = v_orig, u_orig
            
        ordered_physical_edges.append((start, end))

    # Calculate Winding logic is implied by the graph structure for this vis
    # We just need the ordered list of coordinates
    path_coords = []
    
    # Add first point
    first_node = ordered_physical_edges[0][0]
    path_coords.append(original_graph.nodes[first_node]['pos'])
    
    for i in range(len(ordered_physical_edges)):
        curr_s, curr_e = ordered_physical_edges[i]
        
        # Add the END point of this edge
        # (The start point is implicitly the end of the previous one)
        p_end = original_graph.nodes[curr_e]['pos']
        path_coords.append(p_end)
        
        # Simple winding check for the label
        # (This logic is simplified for visualization, relying on your main code for robust math)
        prev_s, prev_e = ordered_physical_edges[(i-1)%len(ordered_physical_edges)]
        p_start = np.array(original_graph.nodes[curr_s]['pos'])
        p_prev_end = np.array(original_graph.nodes[prev_e]['pos'])
        
        if p_start[0] > p_prev_end[0] + 1e-4: wind_x += 1
        elif p_start[0] < p_prev_end[0] - 1e-4: wind_x -= 1
        if p_start[1] > p_prev_end[1] + 1e-4: wind_y += 1
        elif p_start[1] < p_prev_end[1] - 1e-4: wind_y -= 1

    return path_coords, (wind_x, wind_y)

# ==========================================
# 2. NEW VISUALIZATION FUNCTION
# ==========================================
def plot_gradient_path_with_wrapping(path_coords, width, height, title_prefix=""):
    """
    path_coords: List of (x,y) tuples from the eulerian circuit.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Generate continuous color map
    num_points = len(path_coords)
    colors = plt.cm.turbo(np.linspace(0, 1, num_points)) 

    # --- LEFT PLOT: Unit Cell View ---
    ax1 = axes[0]
    ax1.set_title(f"{title_prefix} Unit Cell View\n(Color = Sequence)", fontsize=12)
    ax1.set_xlim(-0.1 * width, 1.1 * width)
    ax1.set_ylim(-0.1 * height, 1.1 * height)
    ax1.set_aspect('equal')
    
    # Draw Boundary Box
    ax1.plot([0, width, width, 0, 0], [0, 0, height, height, 0], 'k--', lw=1, alpha=0.3)
    
    # Draw Segments
    for i in range(num_points - 1):
        p1 = np.array(path_coords[i])
        p2 = np.array(path_coords[i+1])
        
        # Detect Jump (Wrap)
        dist = np.linalg.norm(p1 - p2)
        if dist < min(width, height) / 2:
            ax1.plot([p1[0], p2[0]], [p1[1], p2[1]], color=colors[i], lw=2.5)

    # --- RIGHT PLOT: 3x3 Tiled View ---
    ax2 = axes[1]
    ax2.set_title(f"{title_prefix} 3x3 Tiled View\n(Proof of Continuity)", fontsize=12)
    ax2.set_xlim(-0.5 * width, 2.5 * width)
    ax2.set_ylim(-0.5 * height, 2.5 * height)
    ax2.set_aspect('equal')
    
    # Draw Grid
    for x in [-width, 0, width, 2*width, 3*width]:
        ax2.axvline(x, color='gray', linestyle=':', alpha=0.3)
    for y in [-height, 0, height, 2*height, 3*height]:
        ax2.axhline(y, color='gray', linestyle=':', alpha=0.3)

    # Logic to "unfold"
    virtual_pos = np.array(path_coords[0]) + np.array([width, height]) # Start in middle
    virtual_path = [virtual_pos]
    
    for i in range(num_points - 1):
        p1 = np.array(path_coords[i])
        p2 = np.array(path_coords[i+1])
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        
        shift_x = 0; shift_y = 0
        if dx < -width/2: shift_x = width   
        elif dx > width/2: shift_x = -width 
        if dy < -height/2: shift_y = height
        elif dy > height/2: shift_y = -height
        
        new_virtual_pos = virtual_pos + np.array([dx + shift_x, dy + shift_y])
        virtual_path.append(new_virtual_pos)
        virtual_pos = new_virtual_pos

    # Plot Collection
    points = np.array(virtual_path).reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    lc = LineCollection(segments, colors=colors, linewidths=2)
    ax2.add_collection(lc)
    ax2.autoscale()
    
    plt.tight_layout()
    plt.show()

# ==========================================
# 3. EXECUTION
# ==========================================
if __name__ == "__main__":
    # 1. Setup
    unit_cell = diamond_unit_cell # Or snake_unit_cell
    G = unit_cell.graph
    W = unit_cell.W
    H = unit_cell.H

    # 2. Find Path
    p_G, mapping = create_periodic_multigraph(G, W, H)
    circuit_gen = find_all_eulerian_circuits(p_G)
    
    valid_path_coords = None
    invalid_path_coords = None

    print("Searching for circuits to visualize...")
    for circuit in circuit_gen:
        coords, winding = calculate_path_winding(circuit, p_G, G, mapping)
        if winding != (0, 0):
            print(f"-> Found VALID path (W={winding})")
            if valid_path_coords is None: valid_path_coords = coords
        else:
            print(f"-> Found INVALID path (W={winding})")
            if invalid_path_coords is None: invalid_path_coords = coords
            
        if valid_path_coords and invalid_path_coords:
            break # Found one of each, stop searching

    # 3. Plot
    if valid_path_coords:
        plot_gradient_path_with_wrapping(valid_path_coords, W, H, "Valid Lattice")
    
    if invalid_path_coords:
        plot_gradient_path_with_wrapping(invalid_path_coords, W, H, "Invalid Island")