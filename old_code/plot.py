import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from unitcell import honeycomb_unit_cell, snake_unit_cell, diamond_unit_cell

def create_periodic_multigraph(original_graph, width, height, tolerance=1e-5):
    """
    Collapses a 2D unit cell graph into a periodic MultiGraph.
    Labels merged nodes as "A+B".
    """
    # 1. Identify Merges
    merge_logic = nx.Graph()
    merge_logic.add_nodes_from(original_graph.nodes())
    
    nodes = list(original_graph.nodes(data=True))
    
    for i in range(len(nodes)):
        u_id, u_data = nodes[i]
        x1, y1 = u_data['pos']
        
        for j in range(i + 1, len(nodes)):
            v_id, v_data = nodes[j]
            x2, y2 = v_data['pos']
            
            dx = abs(x1 - x2)
            dy = abs(y1 - y2)
            
            is_h_wrap = (abs(dx - width) < tolerance) and (dy < tolerance)
            is_v_wrap = (abs(dy - height) < tolerance) and (dx < tolerance)
            is_c_wrap = (abs(dx - width) < tolerance) and (abs(dy - height) < tolerance)
            
            if is_h_wrap or is_v_wrap or is_c_wrap:
                merge_logic.add_edge(u_id, v_id)

    # 2. Create Mapping (Logic for "1+3" labels)
    mapping = {}
    new_node_positions = {}
    
    for component in nx.connected_components(merge_logic):
        sorted_ids = sorted(list(component))
        
        # KEY CHANGE: Create label "1+7"
        new_id = "+".join(map(str, sorted_ids))
        
        for old_id in sorted_ids:
            mapping[old_id] = new_id
            
        # Use position of the first node (usually Left/Bottom) for plot
        first_node = sorted_ids[0]
        new_node_positions[new_id] = original_graph.nodes[first_node]['pos']

    # 3. Build MultiGraph
    new_graph = nx.MultiGraph()
    for new_id, pos in new_node_positions.items():
        new_graph.add_node(new_id, pos=pos)
        
    for u, v, data in original_graph.edges(data=True):
        new_u = mapping[u]
        new_v = mapping[v]
        edge_name = f"{u}-{v}"
        new_graph.add_edge(new_u, new_v, key=edge_name, original_u=u, original_v=v, **data)
        
    return new_graph, mapping

def plot_comparison(G_flat, G_merged, width, height):
    """
    Plots Flat vs Merged with Nice Multigraph Curves
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))

    edge_colors = {}
    edges_flat = list(G_flat.edges())
    colormap = cm.get_cmap('tab20') # High contrast palette
    
    for i, (u, v) in enumerate(edges_flat):
        key = tuple(sorted((u, v)))
        edge_colors[key] = colormap(i / len(edges_flat))
    
    # --- PLOT 1: FLAT ---
    ax1 = axes[0]
    pos_flat = nx.get_node_attributes(G_flat, 'pos')
    
    # Boundary
    ax1.plot([0, width, width, 0, 0], [0, 0, height, height, 0], 'k--', alpha=0.3)
    
    # Nodes/Edges
    nx.draw_networkx_edges(G_flat, pos_flat, ax=ax1, edge_color=[edge_colors[tuple(sorted((u, v)))] for u, v in G_flat.edges()], width=6)
    nx.draw_networkx_nodes(G_flat, pos_flat, ax=ax1, node_size=300, node_color='white', edgecolors='black')
    nx.draw_networkx_labels(G_flat, pos_flat, ax=ax1)
    nx.draw_networkx_edge_labels(G_flat, pos_flat, ax=ax1, edge_labels={(u, v): f"{u}-{v}" for u, v in G_flat.edges()}, font_color='gray', font_size=7)
    
    # Highlight Boundary Nodes
    # l_nodes = [n for n, p in pos_flat.items() if p[0] < 0.1]
    # r_nodes = [n for n, p in pos_flat.items() if p[0] > width - 0.1]
    # nx.draw_networkx_nodes(G_flat, pos_flat, nodelist=l_nodes, ax=ax1, node_color='#ffcccc', edgecolors='red') # Red tint
    # nx.draw_networkx_nodes(G_flat, pos_flat, nodelist=r_nodes, ax=ax1, node_color='#ccccff', edgecolors='blue') # Blue tint
    
    ax1.set_title("(a) Flat Unit Cell", fontsize=14)
    ax1.axis('equal')

    # --- PLOT 2: MERGED MULTIGRAPH ---
    ax2 = axes[1]
    pos_merged = nx.get_node_attributes(G_merged, 'pos')
    
    # Draw "Seam" (Left Line)
    # ax2.plot([0, 0], [0, height], 'k-', lw=5, alpha=0.1, label='Merged Seam')
    ax2.plot([0, width, width, 0, 0], [0, 0, height, height, 0], 'k--', alpha=0.3)
    
    # Draw Edges with Curvature logic
    # We group edges by (u,v) pair to calculate curvature offsets
    edge_groups = {}
    for u, v, key in G_merged.edges(keys=True):
        pair = tuple(sorted((u, v)))
        if pair not in edge_groups: edge_groups[pair] = []
        edge_groups[pair].append((u, v, key))
        
    for pair, edges in edge_groups.items():
        count = len(edges)
        for i, (u, v, key) in enumerate(edges):
            # Calculate curvature (rad)
            # If 1 edge: rad=0 (straight)
            # If multiple: spread rads like 0.1, -0.1, 0.2, -0.2
            if count == 1:
                rad = 0
            else:
                # Logic to fan out edges
                # i=0 -> 0.15, i=1 -> -0.15, i=2 -> 0.30, etc
                sign = 1 if i % 2 == 0 else -1
                step = (i // 2) + 1
                rad = 0.15 * step * sign

            original_u = G_merged.edges[u, v, key]['original_u']
            original_v = G_merged.edges[u, v, key]['original_v']
            
            # Draw single edge
            nx.draw_networkx_edges(G_merged, pos_merged, ax=ax2, edgelist=[(u, v)], 
                                   connectionstyle=f'arc3, rad={rad}', 
                                   edge_color=edge_colors[tuple(sorted((original_u, original_v)))], width=6, 
                                   arrowstyle='-', label=f"{original_u}-{original_v}")
            nx.draw_networkx_edge_labels(G_merged, pos_merged, connectionstyle=f'arc3, rad={rad}', ax=ax2, edge_labels={(u, v): f"{original_u}-{original_v}"}, font_color='gray', font_size=7)

    # Draw Nodes (Merged ones highlighted)
    merged_nodes = [n for n in G_merged.nodes() if "+" in str(n)]
    normal_nodes = [n for n in G_merged.nodes() if "+" not in str(n)]
    
    nx.draw_networkx_nodes(G_merged, pos_merged, nodelist=normal_nodes, ax=ax2, node_size=300, node_color='white', edgecolors='black')
    nx.draw_networkx_nodes(G_merged, pos_merged, nodelist=merged_nodes, ax=ax2, node_size=600, node_color='#e6ccff', edgecolors='purple')
    
    # Labels (smaller font for merged to fit "1+3")
    nx.draw_networkx_labels(G_merged, pos_merged, ax=ax2, font_size=8)
    
    ax2.set_title("(b) Periodic Multigraph (Merged)", fontsize=14)
    ax2.axis('equal')
    
    plt.tight_layout()
    plt.show()

# ==========================================
# 3. RUN
# ==========================================
if __name__ == "__main__":
    data = snake_unit_cell
    
    periodic_G, mapping = create_periodic_multigraph(data.graph, data.W, data.H)
    plot_comparison(data.graph, periodic_G, data.W, data.H)