import io

import ezdxf
import networkx as nx

def parse_dxf_to_graph(file_path_or_bytes, tolerance_decimals: int = 4)-> tuple[nx.Graph, float, float]:
    """
    Parses a DXF file (or bytes) and extracts a graph representation of the line segments.
    Args:
        file_path_or_bytes: A file-like object, bytes, or a file path to the DXF file.
        tolerance_decimals: Number of decimal places to round coordinates for tolerance.
    Returns:
        A NetworkX graph where nodes are unique points and edges represent line segments.
    """
    # 1. Read the DXF (Supports both file paths and in-memory bytes from Dash)
    try:
        if isinstance(file_path_or_bytes, bytes):
            try:
                doc = ezdxf.read(io.StringIO(file_path_or_bytes.decode('utf-8')))
            except UnicodeDecodeError:
                doc = ezdxf.read(io.BytesIO(file_path_or_bytes))
        else:
            doc = ezdxf.readfile(file_path_or_bytes)
    except Exception as e:
        print(f"Error reading DXF: {e}")
        return None, 0, 0

    msp = doc.modelspace()
    G = nx.Graph()

    # 2. Setup tracking variables
    node_map = {} # Maps rounded (x, y) coordinates to integer Node IDs
    next_node_id = 0
    min_x, max_x = float('inf'), float('-inf')
    min_y, max_y = float('inf'), float('-inf')

    def get_or_create_node(x, y):
        """Spatial hashing to merge connected lines into single nodes."""
        nonlocal next_node_id, min_x, max_x, min_y, max_y
        
        # Update bounding box
        if x < min_x: min_x = x
        if x > max_x: max_x = x
        if y < min_y: min_y = y
        if y > max_y: max_y = y

        # Round to tolerance to ensure lines that "touch" share the same node
        key = (round(x, tolerance_decimals), round(y, tolerance_decimals))
        
        if key not in node_map:
            node_map[key] = next_node_id
            # Add node with 'pos' attribute required by create_periodic_multigraph
            G.add_node(next_node_id, pos=(x, y))
            next_node_id += 1
            
        return node_map[key]

    # 3. Extract Geometry
    for entity in msp:
        if entity.dxftype() == 'LINE':
            u_id = get_or_create_node(entity.dxf.start.x, entity.dxf.start.y)
            v_id = get_or_create_node(entity.dxf.end.x, entity.dxf.end.y)
            if u_id != v_id:
                G.add_edge(u_id, v_id)
                
        elif entity.dxftype() == 'LWPOLYLINE':
            points = entity.get_points() # Returns (x, y, start_width, end_width, bulge)
            node_ids = [get_or_create_node(p[0], p[1]) for p in points]
            
            # Connect sequential points
            for i in range(len(node_ids) - 1):
                if node_ids[i] != node_ids[i+1]:
                    G.add_edge(node_ids[i], node_ids[i+1])
                    
            # Close the loop if the polyline is closed
            if entity.is_closed and len(node_ids) > 0:
                if node_ids[-1] != node_ids[0]:
                    G.add_edge(node_ids[-1], node_ids[0])

    # 4. Calculate Dimensions & Normalize
    width = max_x - min_x
    height = max_y - min_y

    # Shift all nodes to ensure the unit cell sits exactly at (0,0) to (W,H)
    # This prevents bounding box issues in your periodic wrapping logic
    for n in G.nodes():
        px, py = G.nodes[n]['pos']
        G.nodes[n]['pos'] = (px - min_x, py - min_y)

    return G, width, height