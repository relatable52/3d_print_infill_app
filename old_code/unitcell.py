import networkx as nx
import math

sin_60 = math.sin(math.radians(60))
cos_60 = math.cos(math.radians(60))

class UnitCell():
    def __init__(self, H, W, graph):
        self.H = H
        self.W = W
        self.graph = graph

honeycomb_graph = nx.Graph()
honeycomb_graph.add_nodes_from(
    [
        (1, {"pos": (5*sin_60, 15)}),
        (2, {"pos": (0, 12.5)}),
        (3, {"pos": (10*sin_60, 12.5)}),
        (4, {"pos": (0, 7.5)}),
        (5, {"pos": (5*sin_60, 5)}),
        (6, {"pos": (10*sin_60, 7.5)}),
        (7, {"pos": (5*sin_60, 0)}),
    ]
)
honeycomb_graph.add_edges_from(
    [
        (1, 2),
        (1, 3),
        (2, 4),
        (4, 5),
        (5, 6),
        (5, 7)
    ]
)

honeycomb_unit_cell = UnitCell(H=15, W=10*sin_60, graph=honeycomb_graph)

snake_graph = nx.Graph()
snake_graph.add_nodes_from(
    [
        (1, {"pos": (2.65, 15)}),
        (2, {"pos": (3.4, 14.3)}),
        (3, {"pos": (5.3, 5.3)}),
        (4, {"pos": (3.05, 0.5)}),
        (5, {"pos": (2.65, 0)}),
        (6, {"pos": (1.3, 0.5)}),
        (7, {"pos": (0.5, 1.5)}),
        (8, {"pos": (0, 5.3)}),
        (9, {"pos": (1.9, 14.3)})
    ]
)
snake_graph.add_edges_from(
    [
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 8),
        (8, 9),
        (9, 1)
    ]
)

snake_unit_cell = UnitCell(H=15, W=5.3, graph=snake_graph)

diamond_graph = nx.Graph()
diamond_graph.add_nodes_from(
    [
        (1, {"pos": (0, 7.5)}),
        (2, {"pos": (5, 15)}),
        (3, {"pos": (10, 7.5)}),
        (4, {"pos": (5, 0)})
    ]
)

diamond_graph.add_edges_from(
    [
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 1)
    ]
)

diamond_unit_cell = UnitCell(H=15, W=10, graph=diamond_graph)

reentrant_graph = nx.Graph()
reentrant_graph.add_nodes_from(
    [
        (1, {"pos": (0, 5)}),
        (2, {"pos": (5, 5)}),
        (3, {"pos": (2.5, 10)}),
        (4, {"pos": (2.5, 0)}),
        (5, {"pos": (12.5, 0)}),
        (6, {"pos": (10, 5)}),
        (7, {"pos": (12.5, 10)}),
        (8, {"pos": (15, 5)})
    ]
)
reentrant_graph.add_edges_from(
    [
        (1, 2),
        (2, 3),
        (2, 4),
        (4, 5),
        (5, 6),
        (6, 7),
        (6, 8)
    ]
)

reentrant_unit_cell = UnitCell(H=10, W=15, graph=reentrant_graph)

def create_super_unit_cell(base_unit_cell, rows, cols, tolerance=1e-4):
    """
    Creates a larger UnitCell by tiling the base_unit_cell in a grid.
    Automatically stitches internal boundaries where nodes overlap.
    """
    super_H = base_unit_cell.H * rows
    super_W = base_unit_cell.W * cols
    super_graph = nx.Graph()
    
    # Dictionary to map geometric positions (rounded) to new unique Node IDs
    # This is what performs the "stitching" of internal seams.
    # Key: (x, y), Value: New_Node_ID
    pos_map = {}
    next_node_id = 1
    
    base_pos = nx.get_node_attributes(base_unit_cell.graph, 'pos')
    
    for r in range(rows):
        for c in range(cols):
            # Calculate the offset for this specific cell in the grid
            offset_x = c * base_unit_cell.W
            offset_y = r * base_unit_cell.H
            
            # Temporary mapping for this cell: Old_ID -> New_ID
            # We need this to reconstruct the edges using the new IDs
            local_id_map = {}
            
            # 1. Process Nodes
            for old_id, (x, y) in base_pos.items():
                # Calculate new absolute position
                new_x = x + offset_x
                new_y = y + offset_y
                
                # Create a rounded tuple key for geometric comparison
                pos_key = (round(new_x, 4), round(new_y, 4))
                
                if pos_key not in pos_map:
                    # New unique position found: Create a new node
                    pos_map[pos_key] = next_node_id
                    super_graph.add_node(next_node_id, pos=(new_x, new_y))
                    next_node_id += 1
                
                # Map the old local ID to the (possibly existing) global ID
                local_id_map[old_id] = pos_map[pos_key]
            
            # 2. Process Edges
            for u, v in base_unit_cell.graph.edges():
                new_u = local_id_map[u]
                new_v = local_id_map[v]
                
                # Add edge (NetworkX ignores duplicates automatically)
                if new_u != new_v: # Avoid self-loops if 2 nodes merged (rare)
                    super_graph.add_edge(new_u, new_v)

    return UnitCell(H=super_H, W=super_W, graph=super_graph)

