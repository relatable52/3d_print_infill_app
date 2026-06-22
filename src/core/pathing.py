from dataclasses import dataclass
from math import hypot
from typing import Literal

import networkx as nx

ConnectionMode = Literal["closest", "avoid_intersection"]


@dataclass(frozen=True)
class ConnectionResult:
    connected_graph: nx.Graph
    added_edges: tuple[tuple[str, str], ...]
    component_count_before: int
    component_count_after: int


def _node_position(graph: nx.Graph, node_id: str) -> tuple[float, float]:
    x, y = graph.nodes[node_id]["pos"]
    return float(x), float(y)


def _top_left_key(position: tuple[float, float]) -> tuple[float, float]:
    x, y = position
    return (-y, x)


def _distance(position_a: tuple[float, float], position_b: tuple[float, float]) -> float:
    return hypot(position_a[0] - position_b[0], position_a[1] - position_b[1])


def _graph_bounds(graph: nx.Graph) -> tuple[float, float, float, float]:
    positions = [_node_position(graph, node_id) for node_id in graph.nodes()]
    all_x = [position[0] for position in positions]
    all_y = [position[1] for position in positions]
    return min(all_x), max(all_x), min(all_y), max(all_y)


def _build_rank_positions(
    graph: nx.Graph,
    ports: list[str],
) -> dict[str, tuple[int, int]]:
    """Map each port to rank-space coordinates based on sorted x and y values."""
    if not ports:
        return {}

    unique_x = sorted({round(_node_position(graph, port)[0], 10) for port in ports})
    unique_y = sorted({round(_node_position(graph, port)[1], 10) for port in ports})
    x_rank = {x_value: index for index, x_value in enumerate(unique_x)}
    y_rank = {y_value: index for index, y_value in enumerate(unique_y)}

    return {
        port: (
            x_rank[round(_node_position(graph, port)[0], 10)],
            y_rank[round(_node_position(graph, port)[1], 10)],
        )
        for port in ports
    }


def _rank_manhattan_distance(
    rank_position_a: tuple[int, int],
    rank_position_b: tuple[int, int],
) -> int:
    return abs(rank_position_a[0] - rank_position_b[0]) + abs(rank_position_a[1] - rank_position_b[1])


def _boundary_labels(
    position: tuple[float, float],
    bounds: tuple[float, float, float, float],
    tolerance: float = 1e-6,
) -> set[str]:
    min_x, max_x, min_y, max_y = bounds
    x, y = position
    labels = set()

    if abs(x - min_x) < tolerance:
        labels.add("left")
    if abs(x - max_x) < tolerance:
        labels.add("right")
    if abs(y - min_y) < tolerance:
        labels.add("bottom")
    if abs(y - max_y) < tolerance:
        labels.add("top")

    return labels


def _line_distance_from_origin(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    """Distance from the origin to the infinite line through two points."""
    x1, y1 = point_a
    x2, y2 = point_b
    denominator = hypot(x2 - x1, y2 - y1)
    if denominator == 0:
        return hypot(x1, y1)

    numerator = abs(x1 * y2 - y1 * x2)
    return numerator / denominator


def _component_line_distance(graph: nx.Graph, component_ports: list[str]) -> float:
    if not component_ports:
        return 0.0

    if len(component_ports) == 1:
        return hypot(*_node_position(graph, component_ports[0]))

    if len(component_ports) == 2:
        return _line_distance_from_origin(
            _node_position(graph, component_ports[0]),
            _node_position(graph, component_ports[1]),
        )

    best_distance = 0.0
    for index, first_port in enumerate(component_ports):
        for second_port in component_ports[index + 1 :]:
            candidate_distance = _line_distance_from_origin(
                _node_position(graph, first_port),
                _node_position(graph, second_port),
            )
            best_distance = max(best_distance, candidate_distance)

    return best_distance


def _component_ports(graph: nx.Graph, component_nodes: set[str]) -> list[str]:
    component_graph = graph.subgraph(component_nodes)
    ports = [node_id for node_id, degree in component_graph.degree() if degree == 1]
    if ports:
        return ports

    # Fallback for closed structures: use all nodes so the algorithm still progresses.
    return sorted(component_nodes)


def _choose_exit_port(
    graph: nx.Graph,
    component_ports: list[str],
    entry_port: str,
) -> str:
    if len(component_ports) <= 1:
        return entry_port

    entry_position = _node_position(graph, entry_port)
    alternatives = [port for port in component_ports if port != entry_port]
    if not alternatives:
        return entry_port

    return max(
        alternatives,
        key=lambda port: _distance(entry_position, _node_position(graph, port)),
    )


def _orientation(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
    tolerance: float = 1e-9,
) -> int:
    cross_value = (
        (point_b[1] - point_a[1]) * (point_c[0] - point_b[0])
        - (point_b[0] - point_a[0]) * (point_c[1] - point_b[1])
    )
    if abs(cross_value) < tolerance:
        return 0
    return 1 if cross_value > 0 else 2


def _on_segment(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
    tolerance: float = 1e-9,
) -> bool:
    return (
        min(point_a[0], point_c[0]) - tolerance <= point_b[0] <= max(point_a[0], point_c[0]) + tolerance
        and min(point_a[1], point_c[1]) - tolerance <= point_b[1] <= max(point_a[1], point_c[1]) + tolerance
    )


def _segments_intersect(
    segment_a_start: tuple[float, float],
    segment_a_end: tuple[float, float],
    segment_b_start: tuple[float, float],
    segment_b_end: tuple[float, float],
) -> bool:
    orientation_1 = _orientation(segment_a_start, segment_a_end, segment_b_start)
    orientation_2 = _orientation(segment_a_start, segment_a_end, segment_b_end)
    orientation_3 = _orientation(segment_b_start, segment_b_end, segment_a_start)
    orientation_4 = _orientation(segment_b_start, segment_b_end, segment_a_end)

    if orientation_1 != orientation_2 and orientation_3 != orientation_4:
        return True

    if orientation_1 == 0 and _on_segment(segment_a_start, segment_b_start, segment_a_end):
        return True
    if orientation_2 == 0 and _on_segment(segment_a_start, segment_b_end, segment_a_end):
        return True
    if orientation_3 == 0 and _on_segment(segment_b_start, segment_a_start, segment_b_end):
        return True
    if orientation_4 == 0 and _on_segment(segment_b_start, segment_a_end, segment_b_end):
        return True

    return False


def _candidate_intersects_existing_geometry(
    graph: nx.Graph,
    start_node: str,
    end_node: str,
    added_edges: list[tuple[str, str]],
) -> bool:
    start_position = _node_position(graph, start_node)
    end_position = _node_position(graph, end_node)

    for existing_start, existing_end in list(graph.edges()) + list(added_edges):
        if {start_node, end_node}.intersection({existing_start, existing_end}):
            continue

        existing_start_position = _node_position(graph, existing_start)
        existing_end_position = _node_position(graph, existing_end)
        if _segments_intersect(
            start_position,
            end_position,
            existing_start_position,
            existing_end_position,
        ):
            return True

    return False


def connect_chains_sweep(
    stitched_graph: nx.Graph,
    mode: ConnectionMode = "closest",
) -> ConnectionResult:
    """Greedily connect connected components through a sweep-style endpoint walk."""
    if stitched_graph.number_of_nodes() == 0:
        return ConnectionResult(stitched_graph.copy(), tuple(), 0, 0)

    working_graph = stitched_graph.copy()
    components = []
    for component_index, component_nodes in enumerate(nx.connected_components(working_graph)):
        ports = _component_ports(working_graph, component_nodes)
        if not ports:
            continue
        components.append(
            {
                "id": component_index,
                "nodes": set(component_nodes),
                "ports": ports,
                "connected": False,
            }
        )

    if not components:
        component_count = nx.number_connected_components(working_graph)
        return ConnectionResult(working_graph, tuple(), component_count, component_count)

    all_ports = [
        port
        for component in components
        for port in component["ports"]
    ]
    rank_positions = _build_rank_positions(working_graph, all_ports)
    bounds = _graph_bounds(working_graph)

    start_component_index = max(
        range(len(components)),
        key=lambda index: (
            _component_line_distance(working_graph, components[index]["ports"]),
            max(rank_positions[port][1] for port in components[index]["ports"]),
            -min(rank_positions[port][0] for port in components[index]["ports"]),
        ),
    )
    start_component = components[start_component_index]
    start_port = min(
        start_component["ports"],
        key=lambda port: (
            rank_positions[port][0],
            -rank_positions[port][1],
            _top_left_key(_node_position(working_graph, port)),
        ),
    )
    start_component["connected"] = True
    current_exit_port = _choose_exit_port(working_graph, start_component["ports"], start_port)

    added_edges: list[tuple[str, str]] = []
    component_count_before = nx.number_connected_components(working_graph)

    while True:
        candidate_steps = []
        current_position = _node_position(working_graph, current_exit_port)
        current_rank = rank_positions[current_exit_port]
        current_boundary_labels = _boundary_labels(current_position, bounds)

        for component in components:
            if component["connected"]:
                continue

            for entry_port in component["ports"]:
                target_position = _node_position(working_graph, entry_port)
                target_rank = rank_positions[entry_port]
                target_boundary_labels = _boundary_labels(target_position, bounds)
                candidate_steps.append(
                    {
                        "component": component,
                        "entry_port": entry_port,
                        "rank_distance": _rank_manhattan_distance(current_rank, target_rank),
                        "euclidean_distance": _distance(current_position, target_position),
                        "same_boundary": 0 if current_boundary_labels.intersection(target_boundary_labels) else 1,
                        "top_left_key": _top_left_key(target_position),
                        "intersects": _candidate_intersects_existing_geometry(
                            working_graph,
                            current_exit_port,
                            entry_port,
                            added_edges,
                        ),
                    }
                )

        if not candidate_steps:
            break

        if mode == "avoid_intersection":
            clean_candidates = [candidate for candidate in candidate_steps if not candidate["intersects"]]
            candidates_to_sort = clean_candidates if clean_candidates else candidate_steps
        else:
            candidates_to_sort = candidate_steps

        selected_candidate = min(
            candidates_to_sort,
            key=lambda candidate: (
                candidate["rank_distance"],
                candidate["euclidean_distance"],
                candidate["same_boundary"],
                candidate["top_left_key"],
            ),
        )

        entry_port = selected_candidate["entry_port"]
        target_component = selected_candidate["component"]
        working_graph.add_edge(current_exit_port, entry_port)
        added_edges.append((current_exit_port, entry_port))
        target_component["connected"] = True
        current_exit_port = _choose_exit_port(working_graph, target_component["ports"], entry_port)

    component_count_after = nx.number_connected_components(working_graph)
    return ConnectionResult(
        connected_graph=working_graph,
        added_edges=tuple(added_edges),
        component_count_before=component_count_before,
        component_count_after=component_count_after,
    )
