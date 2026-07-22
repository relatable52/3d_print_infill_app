import itertools
import networkx as nx

def generate_printable_layers(
    physical_graph: nx.Graph, 
    periodic_graph: nx.MultiGraph, 
    loop_catalog: list[dict], 
    num_layers: int, 
    max_solutions: int = 100
) -> list[list[list[str]]]:
    
    # 1. Correctly extract Periodic Nodes
    all_periodic_nodes = set(periodic_graph.nodes())
    
    # 2. Correctly extract Periodic Edges from the MultiGraph WITH keys
    all_periodic_edges = set()
    for u, v, key in periodic_graph.edges(keys=True):
        # Use frozenset for (u, v) so order doesn't matter, combined with the key
        all_periodic_edges.add((frozenset([u, v]), key))
    
    # 3. Parse the Loop Catalog to match the exact same format
    loops_data = []
    for loop in loop_catalog:
        p_nodes = set()
        p_edges = set()
        for edge_list in loop.get("periodic_edges", []):
            # Extract exactly the 3 items from your JSON format
            u, v, key = edge_list
            p_nodes.add(u)
            p_nodes.add(v)
            p_edges.add((frozenset([u, v]), key))
            
        loops_data.append({"id": loop["loop_id"], "edges": p_edges, "nodes": p_nodes})

    valid_single_layers = []

    # 4. Find all valid single layers
    def find_valid_layers(index, current_loops, covered_edges, covered_nodes):
        if covered_nodes == all_periodic_nodes:
            valid_single_layers.append([l["id"] for l in current_loops])
            # Do not return here; we might be able to add more disjoint loops

        for i in range(index, len(loops_data)):
            loop = loops_data[i]
            if not covered_edges.intersection(loop["edges"]):
                current_loops.append(loop)
                find_valid_layers(
                    i + 1, 
                    current_loops, 
                    covered_edges.union(loop["edges"]), 
                    covered_nodes.union(loop["nodes"])
                )
                current_loops.pop()

    find_valid_layers(0, [], set(), set())

    if not valid_single_layers:
        return []

    # 5. Find layer combinations
    solutions = []
    for layer_combo in itertools.combinations(valid_single_layers, num_layers):
        total_covered_edges = set()
        for layer in layer_combo:
            for loop_id in layer:
                loop = next(l for l in loops_data if l["id"] == loop_id)
                total_covered_edges.update(loop["edges"])
        
        # If the union of these layers covers every edge in the periodic graph
        if total_covered_edges == all_periodic_edges:
            solutions.append(list(layer_combo))
            if len(solutions) >= max_solutions:
                break

    return solutions