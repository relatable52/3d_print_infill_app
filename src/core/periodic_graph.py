import networkx as nx


def _get_leftmost_uppermost_node_id(original_graph: nx.Graph, node_ids) -> int:
    """Pick the representative node using leftmost-first, then uppermost tie-break."""
    return min(
        node_ids,
        key=lambda node_id: (
            original_graph.nodes[node_id]["pos"][0],
            -original_graph.nodes[node_id]["pos"][1],
            node_id,
        ),
    )


def create_periodic_multigraph(
    original_graph: nx.Graph,
    width: float,
    height: float,
    tolerance: float = 1e-5,
) -> tuple[nx.MultiGraph, dict]:
    """
    Collapse a unit-cell graph into a periodic multigraph.

    Nodes that sit on opposite boundaries are treated as periodic partners and
    merged into one logical node. Original edge metadata is preserved so later
    stages can reconstruct physical paths on the unit cell.
    """
    merge_logic = nx.Graph()
    merge_logic.add_nodes_from(original_graph.nodes())
    nodes = list(original_graph.nodes(data=True))

    for i, (u, data_u) in enumerate(nodes):
        x_u, y_u = data_u["pos"]

        for v, data_v in nodes[i + 1 :]:
            x_v, y_v = data_v["pos"]
            dx = abs(x_u - x_v)
            dy = abs(y_u - y_v)

            is_wrap = (
                ((abs(dx - width) < tolerance or dx < tolerance)
                and (abs(dy - height) < tolerance or dy < tolerance))
                and not (dx < tolerance and dy < tolerance)
            )

            if is_wrap:
                merge_logic.add_edge(u, v)

    mapping = {}
    periodic_graph = nx.MultiGraph()

    for component in nx.connected_components(merge_logic):
        sorted_ids = sorted(component)
        periodic_node_id = "_".join(map(str, sorted_ids))

        for old_id in sorted_ids:
            mapping[old_id] = periodic_node_id

        representative_id = _get_leftmost_uppermost_node_id(original_graph, sorted_ids)
        periodic_graph.add_node(
            periodic_node_id,
            pos=original_graph.nodes[representative_id]["pos"],
            original_nodes=tuple(sorted_ids),
        )

    for node_id in original_graph.nodes():
        if node_id in mapping:
            continue

        periodic_node_id = str(node_id)
        mapping[node_id] = periodic_node_id
        periodic_graph.add_node(
            periodic_node_id,
            pos=original_graph.nodes[node_id]["pos"],
            original_nodes=(node_id,),
        )

    for u, v, data in original_graph.edges(data=True):
        periodic_u = mapping[u]
        periodic_v = mapping[v]
        edge_key = f"{u}-{v}"

        periodic_graph.add_edge(
            periodic_u,
            periodic_v,
            key=edge_key,
            original_u=u,
            original_v=v,
            **data,
        )

    return periodic_graph, mapping


if __name__ == "__main__":
    unit_cell_graph = nx.Graph()
    unit_cell_graph.add_node(1, pos=(0.0, 5.0))
    unit_cell_graph.add_node(2, pos=(10.0, 5.0))
    unit_cell_graph.add_node(3, pos=(2.0, 0.0))
    unit_cell_graph.add_node(4, pos=(2.0, 10.0))
    unit_cell_graph.add_node(5, pos=(5.0, 5.0))

    unit_cell_graph.add_edge(1, 3)
    unit_cell_graph.add_edge(1, 4)
    unit_cell_graph.add_edge(2, 5)
    unit_cell_graph.add_edge(3, 5)
    unit_cell_graph.add_edge(4, 5)

    periodic_graph, mapping = create_periodic_multigraph(
        unit_cell_graph,
        width=10.0,
        height=10.0,
    )

    print("Original to periodic node mapping:")
    for original_node, periodic_node in sorted(mapping.items()):
        print(f"  {original_node} -> {periodic_node}")

    print("\nPeriodic nodes:")
    for node_id, data in periodic_graph.nodes(data=True):
        print(f"  {node_id}: {data}")

    print("\nPeriodic edges:")
    for u, v, key, data in periodic_graph.edges(keys=True, data=True):
        print(f"  {u} -> {v} [{key}] {data}")
