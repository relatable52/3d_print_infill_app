from dataclasses import dataclass

import matplotlib.pyplot as plt
import networkx as nx

from src.core.loop_finder import discover_valid_loops
from src.core.periodic_graph import create_periodic_multigraph


@dataclass(frozen=True)
class ThreadedNodeRecord:
    label: str
    original_node_id: int
    periodic_group: str
    loop_id: str
    visit_index: int
    pos: tuple[float, float]


@dataclass(frozen=True)
class ThreadedLayer:
    node_records: tuple[ThreadedNodeRecord, ...]
    threaded_edges: tuple[tuple[str, str], ...]
    horizontal_boundary_pairs: tuple[tuple[int, int], ...]
    vertical_boundary_pairs: tuple[tuple[int, int], ...]


def _boundary_near(value: float, target: float, tolerance: float) -> bool:
    return abs(value - target) < tolerance


def detect_boundary_pairs(
    original_graph: nx.Graph,
    width: float,
    height: float,
    tolerance: float = 1e-4,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Detect periodic partner nodes across horizontal and vertical boundaries."""
    node_positions = nx.get_node_attributes(original_graph, "pos")
    horizontal_pairs = []
    vertical_pairs = []
    nodes = list(original_graph.nodes())

    for i, left_candidate in enumerate(nodes):
        x_u, y_u = node_positions[left_candidate]

        for right_candidate in nodes[i + 1 :]:
            x_v, y_v = node_positions[right_candidate]

            if abs(y_u - y_v) < tolerance:
                if _boundary_near(x_u, 0.0, tolerance) and _boundary_near(x_v, width, tolerance):
                    horizontal_pairs.append((left_candidate, right_candidate))
                elif _boundary_near(x_v, 0.0, tolerance) and _boundary_near(x_u, width, tolerance):
                    horizontal_pairs.append((right_candidate, left_candidate))

            if abs(x_u - x_v) < tolerance:
                if _boundary_near(y_u, 0.0, tolerance) and _boundary_near(y_v, height, tolerance):
                    vertical_pairs.append((left_candidate, right_candidate))
                elif _boundary_near(y_v, 0.0, tolerance) and _boundary_near(y_u, height, tolerance):
                    vertical_pairs.append((right_candidate, left_candidate))

    return horizontal_pairs, vertical_pairs


def create_threaded_loop_edges(
    loop_id: str,
    ordered_physical_edges: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    mapping: dict[int, str],
    original_graph: nx.Graph,
) -> tuple[list[tuple[str, str]], dict[str, ThreadedNodeRecord]]:
    """
    Split repeated visits into visit-labeled threaded nodes for one loop.

    Labels include the loop ID so different loops can share physical nodes
    without collapsing into the same threaded chain.
    """
    if not ordered_physical_edges:
        return [], {}

    group_counters = {group_id: 0 for group_id in set(mapping.values())}
    prev_end_visit_index = None
    prev_end_group = None

    threaded_edges = []
    node_records = {}
    edge_count = len(ordered_physical_edges)

    for edge_index, (start_node, end_node) in enumerate(ordered_physical_edges):
        start_group = mapping[start_node]
        end_group = mapping[end_node]

        if edge_index == 0:
            start_visit_index = 0
        elif start_group == prev_end_group:
            start_visit_index = prev_end_visit_index
        else:
            start_visit_index = group_counters[start_group]

        if edge_index == edge_count - 1:
            first_start_node, _ = ordered_physical_edges[0]
            first_group = mapping[first_start_node]
            if end_group == first_group:
                end_visit_index = 0
            else:
                end_visit_index = group_counters[end_group] + 1
        else:
            group_counters[end_group] += 1
            end_visit_index = group_counters[end_group]

        prev_end_visit_index = end_visit_index
        prev_end_group = end_group

        start_label = f"{loop_id}|{start_node}_{start_visit_index}"
        end_label = f"{loop_id}|{end_node}_{end_visit_index}"
        threaded_edges.append((start_label, end_label))

        if start_label not in node_records:
            node_records[start_label] = ThreadedNodeRecord(
                label=start_label,
                original_node_id=start_node,
                periodic_group=start_group,
                loop_id=loop_id,
                visit_index=start_visit_index,
                pos=tuple(original_graph.nodes[start_node]["pos"]),
            )

        if end_label not in node_records:
            node_records[end_label] = ThreadedNodeRecord(
                label=end_label,
                original_node_id=end_node,
                periodic_group=end_group,
                loop_id=loop_id,
                visit_index=end_visit_index,
                pos=tuple(original_graph.nodes[end_node]["pos"]),
            )

    return threaded_edges, node_records


def build_threaded_layer(
    selected_loops: list[dict],
    mapping: dict[int, str],
    original_graph: nx.Graph,
    width: float,
    height: float,
) -> ThreadedLayer:
    """Build the authoritative threaded unit-cell representation for one layer."""
    combined_edges = []
    combined_nodes: dict[str, ThreadedNodeRecord] = {}

    for loop in selected_loops:
        loop_id = loop["loop_id"]
        threaded_edges, node_records = create_threaded_loop_edges(
            loop_id,
            loop["physical_edges"],
            mapping,
            original_graph,
        )
        combined_edges.extend(threaded_edges)
        combined_nodes.update(node_records)

    horizontal_pairs, vertical_pairs = detect_boundary_pairs(
        original_graph,
        width,
        height,
    )

    return ThreadedLayer(
        node_records=tuple(sorted(combined_nodes.values(), key=lambda record: record.label)),
        threaded_edges=tuple(combined_edges),
        horizontal_boundary_pairs=tuple(sorted(horizontal_pairs)),
        vertical_boundary_pairs=tuple(sorted(vertical_pairs)),
    )


def _make_tiled_node_id(threaded_label: str, row: int, col: int) -> str:
    return f"{threaded_label}|r{row}|c{col}"


def tile_threaded_layer(
    threaded_layer: ThreadedLayer,
    width: float,
    height: float,
    rows: int,
    cols: int,
) -> nx.Graph:
    """Instantiate the threaded unit-cell layer over an m x n grid."""
    tiled_graph = nx.Graph()
    node_records_by_label = {record.label: record for record in threaded_layer.node_records}

    for row in range(rows):
        for col in range(cols):
            offset_x = col * width
            offset_y = row * height

            for start_label, end_label in threaded_layer.threaded_edges:
                start_record = node_records_by_label[start_label]
                end_record = node_records_by_label[end_label]

                tiled_start = _make_tiled_node_id(start_label, row, col)
                tiled_end = _make_tiled_node_id(end_label, row, col)

                tiled_graph.add_node(
                    tiled_start,
                    pos=(start_record.pos[0] + offset_x, start_record.pos[1] + offset_y),
                    original_node_id=start_record.original_node_id,
                    periodic_group=start_record.periodic_group,
                    loop_id=start_record.loop_id,
                    visit_index=start_record.visit_index,
                    thread_label=start_record.label,
                    row=row,
                    col=col,
                )
                tiled_graph.add_node(
                    tiled_end,
                    pos=(end_record.pos[0] + offset_x, end_record.pos[1] + offset_y),
                    original_node_id=end_record.original_node_id,
                    periodic_group=end_record.periodic_group,
                    loop_id=end_record.loop_id,
                    visit_index=end_record.visit_index,
                    thread_label=end_record.label,
                    row=row,
                    col=col,
                )
                tiled_graph.add_edge(tiled_start, tiled_end)

    return tiled_graph


def stitch_threaded_boundaries(
    tiled_graph: nx.Graph,
    threaded_layer: ThreadedLayer,
    rows: int,
    cols: int,
) -> nx.Graph:
    """Stitch periodic neighbors only when loop/thread visit identity matches."""
    stitched_graph = tiled_graph.copy()
    thread_lookup = {
        (record.original_node_id, record.loop_id, record.visit_index): record.label
        for record in threaded_layer.node_records
    }

    for row in range(rows):
        for col in range(cols):
            if col < cols - 1:
                for left_node_id, right_node_id in threaded_layer.horizontal_boundary_pairs:
                    for right_record in threaded_layer.node_records:
                        if right_record.original_node_id != right_node_id:
                            continue

                        partner_label = thread_lookup.get(
                            (left_node_id, right_record.loop_id, right_record.visit_index)
                        )
                        if partner_label is None:
                            continue

                        current_node = _make_tiled_node_id(right_record.label, row, col)
                        neighbor_node = _make_tiled_node_id(partner_label, row, col + 1)
                        if stitched_graph.has_node(current_node) and stitched_graph.has_node(neighbor_node):
                            stitched_graph.add_edge(current_node, neighbor_node)

            if row < rows - 1:
                for bottom_node_id, top_node_id in threaded_layer.vertical_boundary_pairs:
                    for top_record in threaded_layer.node_records:
                        if top_record.original_node_id != top_node_id:
                            continue

                        partner_label = thread_lookup.get(
                            (bottom_node_id, top_record.loop_id, top_record.visit_index)
                        )
                        if partner_label is None:
                            continue

                        current_node = _make_tiled_node_id(top_record.label, row, col)
                        neighbor_node = _make_tiled_node_id(partner_label, row + 1, col)
                        if stitched_graph.has_node(current_node) and stitched_graph.has_node(neighbor_node):
                            stitched_graph.add_edge(current_node, neighbor_node)

    return stitched_graph


def tile_and_stitch_layer(
    selected_loops: list[dict],
    original_graph: nx.Graph,
    mapping: dict[int, str],
    width: float,
    height: float,
    rows: int,
    cols: int,
) -> tuple[ThreadedLayer, nx.Graph]:
    """Convenience wrapper for Milestone 8 backend use."""
    threaded_layer = build_threaded_layer(
        selected_loops,
        mapping,
        original_graph,
        width,
        height,
    )
    tiled_graph = tile_threaded_layer(threaded_layer, width, height, rows, cols)
    stitched_graph = stitch_threaded_boundaries(tiled_graph, threaded_layer, rows, cols)
    return threaded_layer, stitched_graph


def plot_tiled_components(
    tiled_graph: nx.Graph,
    width: float,
    height: float,
    rows: int,
    cols: int,
    title: str = "Tiled Threaded Layer",
) -> None:
    """Plot the stitched tiled graph using a different color per connected component."""
    if tiled_graph.number_of_nodes() == 0:
        print("No tiled graph data to plot.")
        return

    positions = nx.get_node_attributes(tiled_graph, "pos")
    components = list(nx.connected_components(tiled_graph))
    color_map = plt.cm.get_cmap("tab20", max(len(components), 1))

    plt.figure(figsize=(10, 10))
    plt.plot(
        [0, width * cols, width * cols, 0, 0],
        [0, 0, height * rows, height * rows, 0],
        "k--",
        alpha=0.35,
    )

    for component_index, component_nodes in enumerate(components):
        component_graph = tiled_graph.subgraph(component_nodes)
        component_color = color_map(component_index)
        nx.draw_networkx_edges(
            component_graph,
            positions,
            edge_color=[component_color],
            width=2.5,
        )
        nx.draw_networkx_nodes(
            component_graph,
            positions,
            node_color=[component_color],
            node_size=35,
        )

    plt.title(f"{title} ({len(components)} connected components)")
    plt.gca().set_aspect("equal")
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def _build_demo_graph() -> tuple[nx.Graph, float, float]:
    demo_graph = nx.Graph()
    demo_graph.add_node(1, pos=(0.0, 5.0))
    demo_graph.add_node(2, pos=(10.0, 5.0))
    demo_graph.add_node(3, pos=(2.0, 0.0))
    demo_graph.add_node(4, pos=(2.0, 10.0))
    demo_graph.add_node(5, pos=(5.0, 5.0))

    demo_graph.add_edge(1, 3)
    demo_graph.add_edge(1, 4)
    demo_graph.add_edge(2, 5)
    demo_graph.add_edge(3, 5)
    demo_graph.add_edge(4, 5)
    return demo_graph, 10.0, 10.0


if __name__ == "__main__":
    GRID_ROWS = 4
    GRID_COLS = 6
    SELECTED_LOOP_IDS = None

    graph, cell_width, cell_height = _build_demo_graph()
    periodic_graph, mapping = create_periodic_multigraph(graph, cell_width, cell_height)
    loop_catalog = [
        {
            "loop_id": loop.loop_id,
            "physical_edges": loop.physical_edges,
        }
        for loop in discover_valid_loops(graph, periodic_graph, mapping, cycle_mode="simple")
    ]

    if not loop_catalog:
        print("No valid loops found in the demo graph.")
    else:
        if SELECTED_LOOP_IDS:
            selected_loops = [loop for loop in loop_catalog if loop["loop_id"] in SELECTED_LOOP_IDS]
        else:
            selected_loops = [loop_catalog[0], loop_catalog[5]]

        threaded_layer, stitched_graph = tile_and_stitch_layer(
            selected_loops,
            graph,
            mapping,
            cell_width,
            cell_height,
            GRID_ROWS,
            GRID_COLS,
        )

        print(f"Selected loops: {[loop['loop_id'] for loop in selected_loops]}")
        print(f"Threaded unit-cell nodes: {len(threaded_layer.node_records)}")
        print(f"Threaded unit-cell edges: {len(threaded_layer.threaded_edges)}")
        print(f"Tiled graph nodes: {stitched_graph.number_of_nodes()}")
        print(f"Tiled graph edges: {stitched_graph.number_of_edges()}")
        print(f"Connected components: {nx.number_connected_components(stitched_graph)}")

        plot_tiled_components(
            stitched_graph,
            cell_width,
            cell_height,
            GRID_ROWS,
            GRID_COLS,
            title="Milestone 8 Debug Plot",
        )
