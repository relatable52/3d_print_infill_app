import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

def create_periodic_multigraph(original_graph, width, height, tolerance=1e-5):
    """
    Collapses a 2D unit cell graph into a periodic MultiGraph by merging
    nodes on opposing boundaries (Pacman logic).
    """
    
    # 1. Identify which nodes should be merged
    # We use a temporary graph to find connected components of merged nodes
    merge_logic = nx.Graph()
    merge_logic.add_nodes_from(original_graph.nodes())
    
    nodes = list(original_graph.nodes(data=True))
    
    # Compare every pair of nodes to see if they are periodic pairs
    # (This is O(N^2), but unit cells are usually small, so it's fast enough)
    for i in range(len(nodes)):
        u_id, u_data = nodes[i]
        x1, y1 = u_data['pos']
        
        for j in range(i + 1, len(nodes)):
            v_id, v_data = nodes[j]
            x2, y2 = v_data['pos']
            
            dx = abs(x1 - x2)
            dy = abs(y1 - y2)
            
            # Check Horizontal Wrap (Left edge touches Right edge)
            is_horizontal_wrap = (abs(dx - width) < tolerance) and (dy < tolerance)
            
            # Check Vertical Wrap (Bottom edge touches Top edge)
            is_vertical_wrap = (abs(dy - height) < tolerance) and (dx < tolerance)
            
            # Check Corner Wrap (Top-Left touches Bottom-Right, etc.)
            is_corner_wrap = (abs(dx - width) < tolerance) and (abs(dy - height) < tolerance)
            
            if is_horizontal_wrap or is_vertical_wrap or is_corner_wrap:
                merge_logic.add_edge(u_id, v_id)

    # 2. Create the Mapping: Old Node ID -> New Merged ID
    # connected_components handles the transitive logic (A=B and B=C means A=C)
    mapping = {}
    new_node_data = {}
    
    for component in nx.connected_components(merge_logic):
        # Sort to make the ID deterministic (e.g., "1_7" instead of "7_1")
        sorted_ids = sorted(list(component))
        # Create a new string ID representing the group
        new_id = "_".join(map(str, sorted_ids))
        
        for old_id in sorted_ids:
            mapping[old_id] = new_id
            
        # Optional: Store the new centroid position (just for visualization)
        # We just take the position of the first node in the group (or average)
        new_node_data[new_id] = original_graph.nodes[sorted_ids[0]]['pos']

    # 3. Build the New MultiGraph
    # A MultiGraph allows multiple edges between the same two nodes
    new_graph = nx.MultiGraph()
    
    # Add nodes
    for new_id, pos in new_node_data.items():
        new_graph.add_node(new_id, pos=pos)
        
    # Add edges (preserving original identity)
    for u, v, data in original_graph.edges(data=True):
        new_u = mapping[u]
        new_v = mapping[v]
        
        # We store the 'original_edge' tuple so you can trace it back later
        # We also generate a unique key for the edge
        edge_name = f"{u}-{v}"
        
        new_graph.add_edge(new_u, new_v, key=edge_name, original_u=u, original_v=v, **data)
        
    return new_graph, mapping

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

# --- EXAMPLE USAGE ---

# 1. Setup a dummy graph (Like your description)
# Imagine a 10x10 square unit cell
W, H = 10.0, 10.0
G = nx.Graph()

# Add nodes with positions (id, {pos: (x,y)})
# Points 1 and 7 are Left/Right mirrors. 2 and 3 are Top/Bottom mirrors.
G.add_node(1, pos=(0, 5))
G.add_node(7, pos=(10, 5)) 

G.add_node(2, pos=(2, 0))
G.add_node(3, pos=(2, 10))

G.add_node(4, pos=(4, 0)) 
G.add_node(6, pos=(4, 10)) 

G.add_node(5, pos=(6, 5)) # Central node (No merge)

# Add edges
G.add_edge(1, 2)
G.add_edge(1, 3)
G.add_edge(5, 7)
G.add_edge(2, 4)
G.add_edge(2, 4)
G.add_edge(4, 5)
G.add_edge(5, 6)

# 2. Run the processing
periodic_G, node_map = create_periodic_multigraph(G, W, H)

# 3. Print Results
print("--- Node Mapping ---")
for old, new in node_map.items():
    print(f"Original {old} -> New {new}")

print("\n--- New Edges (in Pacman World) ---")
for u, v, key, data in periodic_G.edges(keys=True, data=True):
    print(f"Edge from {u} to {v} | Origin: {data['original_u']}-{data['original_v']}")

plot_graph(G, title="Original Graph", width=W, height=H)