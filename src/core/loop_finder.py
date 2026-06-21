from dataclasses import asdict, dataclass
from itertools import combinations, product
from typing import Literal

import matplotlib.pyplot as plt
import networkx as nx

CycleMode = Literal["simple", "all"]


@dataclass(frozen=True)
class LoopRecord:
    loop_id: str
    cycle_mode: CycleMode
    periodic_edges: tuple[tuple[str, str, str], ...]
    physical_edges: tuple[tuple[int, int], ...]
    winding: tuple[int, int]
    edge_signature: tuple[tuple[int, int], ...]
    node_sequence: tuple[int, ...]
    path_text: str
    edge_count: int
    closes_periodically: bool


def loop_record_to_dict(loop: LoopRecord) -> dict:
    """Serialize a loop record into a Dash-store-friendly dictionary."""
    return asdict(loop)


def reconstruct_ordered_physical_edges(
    periodic_edges: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...],
    periodic_graph: nx.MultiGraph,
    mapping: dict,
) -> list[tuple[int, int]]:
    """
    Reconstruct directed physical unit-cell edges from an ordered periodic loop.

    Each periodic edge stores the original edge endpoints. The ordered traversal
    direction through the periodic graph determines which original endpoint is
    the physical start and which is the physical end.
    """
    ordered_physical_edges = []

    for u_merge, v_merge, key in periodic_edges:
        data = periodic_graph[u_merge][v_merge][key]
        u_orig = data["original_u"]
        v_orig = data["original_v"]

        if mapping[u_orig] == u_merge:
            start, end = u_orig, v_orig
        else:
            start, end = v_orig, u_orig

        ordered_physical_edges.append((start, end))

    return ordered_physical_edges


def calculate_loop_winding(
    ordered_physical_edges: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    original_graph: nx.Graph,
    tolerance: float = 1e-4,
) -> tuple[int, int]:
    """Calculate the winding induced by periodic jumps in an ordered loop."""
    wind_x = 0
    wind_y = 0

    for i, (curr_start, _) in enumerate(ordered_physical_edges):
        _, prev_end = ordered_physical_edges[(i - 1) % len(ordered_physical_edges)]

        p_start_x, p_start_y = original_graph.nodes[curr_start]["pos"]
        p_prev_x, p_prev_y = original_graph.nodes[prev_end]["pos"]

        if p_start_x > p_prev_x + tolerance:
            wind_x += 1
        elif p_start_x < p_prev_x - tolerance:
            wind_x -= 1

        if p_start_y > p_prev_y + tolerance:
            wind_y += 1
        elif p_start_y < p_prev_y - tolerance:
            wind_y -= 1

    return wind_x, wind_y


def create_edge_signature(
    physical_edges: list[tuple[int, int]] | tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    """
    Create a direction-insensitive signature for loop deduplication.

    The first version deduplicates loops that use the same physical undirected
    edge set, even if traversal order differs.
    """
    signature = [tuple(sorted((u, v))) for u, v in physical_edges]
    return tuple(sorted(signature))


def physical_edges_to_node_sequence(
    physical_edges: list[tuple[int, int]] | tuple[tuple[int, int], ...],
) -> tuple[int, ...]:
    """
    Convert ordered physical edges into a display-friendly node sequence.

    If consecutive edges are not geometrically continuous inside the unit cell,
    the next edge's start node is inserted explicitly in the sequence.
    """
    if not physical_edges:
        return tuple()

    sequence = [physical_edges[0][0], physical_edges[0][1]]

    for start, end in physical_edges[1:]:
        if sequence[-1] != start:
            sequence.append(start)
        sequence.append(end)

    return tuple(sequence)


def physical_edges_to_path_text(
    physical_edges: list[tuple[int, int]] | tuple[tuple[int, int], ...],
) -> str:
    node_sequence = physical_edges_to_node_sequence(physical_edges)
    if not node_sequence:
        return ""

    return " -> ".join(map(str, node_sequence))


def _normalize_edge_id(u: str, v: str, key: str) -> tuple[str, str, str]:
    return tuple(sorted((u, v))) + (key,)


def _reverse_periodic_edge(edge: tuple[str, str, str]) -> tuple[str, str, str]:
    u, v, key = edge
    return v, u, key


def _all_rotations(sequence: tuple[tuple[str, str, str], ...]) -> list[tuple[tuple[str, str, str], ...]]:
    return [
        sequence[i:] + sequence[:i]
        for i in range(len(sequence))
    ]


def canonicalize_periodic_walk(
    periodic_edges: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...],
) -> tuple[tuple[str, str, str], ...]:
    """
    Canonicalize a closed periodic walk up to rotation and reversal.
    """
    sequence = tuple(periodic_edges)
    reversed_sequence = tuple(
        _reverse_periodic_edge(edge)
        for edge in reversed(sequence)
    )

    candidates = _all_rotations(sequence) + _all_rotations(reversed_sequence)
    return min(candidates)


def _edge_keys_between_nodes(graph: nx.MultiGraph, u: str, v: str) -> list[str]:
    edge_dict = graph.get_edge_data(u, v)
    if not edge_dict:
        return []

    return sorted(edge_dict.keys())


def _iter_edge_steps(graph: nx.MultiGraph, current_node: str) -> list[tuple[str, str, str]]:
    steps = []

    for u, v, key in graph.edges(current_node, keys=True):
        next_node = v if u == current_node else u
        steps.append((current_node, next_node, key))

    return sorted(steps)


def find_simple_periodic_cycles(
    periodic_graph: nx.MultiGraph,
    max_cycle_edges: int | None = None,
) -> list[list[tuple[str, str, str]]]:
    """
    Enumerate simple cycles in the periodic multigraph.

    Simple here means no repeated nodes except the closure back to the start.
    Edge identities are preserved, so parallel edges can produce distinct cycles.
    """
    discovered = {}

    def dfs(
        start_node: str,
        current_node: str,
        visited_nodes: set[str],
        used_edges: set[tuple[str, str, str]],
        path_edges: list[tuple[str, str, str]],
    ) -> None:
        for edge in _iter_edge_steps(periodic_graph, current_node):
            _, next_node, key = edge
            edge_id = _normalize_edge_id(current_node, next_node, key)
            if edge_id in used_edges:
                continue

            new_path = path_edges + [edge]
            if max_cycle_edges is not None and len(new_path) > max_cycle_edges:
                continue

            if next_node == start_node and len(new_path) >= 2:
                canonical = canonicalize_periodic_walk(new_path)
                discovered[canonical] = list(canonical)
                continue

            if next_node in visited_nodes:
                continue

            dfs(
                start_node,
                next_node,
                visited_nodes | {next_node},
                used_edges | {edge_id},
                new_path,
            )

    for start_node in sorted(periodic_graph.nodes()):
        dfs(start_node, start_node, {start_node}, set(), [])

    return list(discovered.values())


def find_all_periodic_cycles(
    periodic_graph: nx.MultiGraph,
    max_cycle_edges: int | None = None,
) -> list[list[tuple[str, str, str]]]:
    """
    Enumerate all closed edge-walks in the periodic multigraph.

    Nodes may be revisited, but edges may not be reused within the same loop.
    """
    discovered = {}
    if max_cycle_edges is None:
        max_cycle_edges = periodic_graph.number_of_edges()

    def dfs(
        start_node: str,
        current_node: str,
        used_edges: set[tuple[str, str, str]],
        path_edges: list[tuple[str, str, str]],
    ) -> None:
        for edge in _iter_edge_steps(periodic_graph, current_node):
            _, next_node, key = edge
            edge_id = _normalize_edge_id(current_node, next_node, key)
            if edge_id in used_edges:
                continue

            new_path = path_edges + [edge]
            if len(new_path) > max_cycle_edges:
                continue

            if next_node == start_node and len(new_path) >= 2:
                canonical = canonicalize_periodic_walk(new_path)
                discovered[canonical] = list(canonical)

            dfs(
                start_node,
                next_node,
                used_edges | {edge_id},
                new_path,
            )

    for start_node in sorted(periodic_graph.nodes()):
        dfs(start_node, start_node, set(), [])

    return list(discovered.values())


def _find_candidate_periodic_loops(
    periodic_graph: nx.MultiGraph,
    cycle_mode: CycleMode = "simple",
    max_cycle_edges: int | None = None,
) -> list[list[tuple[str, str, str]]]:
    if cycle_mode == "all":
        return find_all_periodic_cycles(periodic_graph, max_cycle_edges=max_cycle_edges)

    return find_simple_periodic_cycles(periodic_graph, max_cycle_edges=max_cycle_edges)


def discover_valid_loops(
    original_graph: nx.Graph,
    periodic_graph: nx.MultiGraph,
    mapping: dict,
    cycle_mode: CycleMode = "simple",
    max_cycle_edges: int | None = None,
) -> list[LoopRecord]:
    """
    Discover printable loop candidates and keep only non-zero-winding loops.

    This first version intentionally favors inspectability over completeness.
    """
    discovered_loops = []

    for periodic_edges in _find_candidate_periodic_loops(
        periodic_graph,
        cycle_mode=cycle_mode,
        max_cycle_edges=max_cycle_edges,
    ):
        physical_edges = reconstruct_ordered_physical_edges(
            periodic_edges,
            periodic_graph,
            mapping,
        )
        winding = calculate_loop_winding(physical_edges, original_graph)
        if winding == (0, 0):
            continue

        edge_signature = create_edge_signature(physical_edges)
        node_sequence = physical_edges_to_node_sequence(physical_edges)
        path_text = physical_edges_to_path_text(physical_edges)
        loop_index = len(discovered_loops) + 1
        discovered_loops.append(
            LoopRecord(
                loop_id=f"L{loop_index}",
                cycle_mode=cycle_mode,
                periodic_edges=tuple(periodic_edges),
                physical_edges=tuple(physical_edges),
                winding=winding,
                edge_signature=edge_signature,
                node_sequence=node_sequence,
                path_text=path_text,
                edge_count=len(physical_edges),
                closes_periodically=bool(node_sequence) and node_sequence[0] == node_sequence[-1],
            )
        )

    return discovered_loops


def plot_discovered_loops(
    original_graph: nx.Graph,
    loops: list[LoopRecord],
    max_loops: int = 6,
    title: str = "Discovered Loops",
) -> None:
    """Plot up to `max_loops` discovered loops on the unit-cell geometry."""
    if not loops:
        print("No loops to plot.")
        return

    subset = loops[:max_loops]
    pos = nx.get_node_attributes(original_graph, "pos")
    all_x = [point[0] for point in pos.values()]
    all_y = [point[1] for point in pos.values()]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    cols = min(3, len(subset))
    rows = (len(subset) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 5 * rows))
    axes_list = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for ax, loop in zip(axes_list, subset):
        boundary_x = [min_x, max_x, max_x, min_x, min_x]
        boundary_y = [min_y, min_y, max_y, max_y, min_y]
        ax.plot(boundary_x, boundary_y, "k--", alpha=0.4, linewidth=1.5)

        for u, v in original_graph.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            ax.plot([x0, x1], [y0, y1], color="#d1d5db", linewidth=1.5, zorder=1)

        for start, end in loop.physical_edges:
            x0, y0 = pos[start]
            x1, y1 = pos[end]
            ax.annotate(
                "",
                xy=(x1, y1),
                xytext=(x0, y0),
                arrowprops=dict(
                    arrowstyle="->",
                    color="#2563eb",
                    lw=2.2,
                    shrinkA=0,
                    shrinkB=0,
                    mutation_scale=12,
                ),
                zorder=3,
            )

        node_x = [pos[node][0] for node in original_graph.nodes()]
        node_y = [pos[node][1] for node in original_graph.nodes()]
        ax.scatter(node_x, node_y, color="#dc2626", s=50, zorder=4)

        for node_id, (x, y) in pos.items():
            ax.text(x + 0.08, y + 0.08, str(node_id), fontsize=9, color="#111827")

        ax.set_title(f"{loop.loop_id} | winding={loop.winding}", fontsize=11)
        ax.set_aspect("equal")
        ax.set_xlim(min_x - 0.5, max_x + 0.5)
        ax.set_ylim(min_y - 0.5, max_y + 0.5)
        ax.grid(True, linestyle=":", alpha=0.4)

    for ax in axes_list[len(subset):]:
        ax.axis("off")

    fig.suptitle(title, fontsize=14)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    from src.core.periodic_graph import create_periodic_multigraph

    unit_cell_graph = nx.Graph()
    unit_cell_graph.add_node(1, pos=(0.0, 5.0))
    unit_cell_graph.add_node(2, pos=(10.0, 5.0))
    unit_cell_graph.add_node(3, pos=(5.0, 10.0))
    unit_cell_graph.add_node(4, pos=(5.0, 0.0))

    unit_cell_graph.add_edge(1, 3)
    unit_cell_graph.add_edge(3, 2)
    unit_cell_graph.add_edge(2, 4)
    unit_cell_graph.add_edge(4, 1)

    periodic_graph, mapping = create_periodic_multigraph(
        unit_cell_graph,
        width=10.0,
        height=10.0,
    )

    for cycle_mode in ("simple", "all"):
        loops = discover_valid_loops(
            unit_cell_graph,
            periodic_graph,
            mapping,
            cycle_mode=cycle_mode,
        )

        print(f"Discovered valid loops ({cycle_mode} mode):")
        if not loops:
            print("  No non-zero-winding loops found.")

        for loop in loops:
            print(f"  {loop.loop_id}")
            print(f"    cycle_mode={loop.cycle_mode}")
            print(f"    periodic_edges={loop.periodic_edges}")
            print(f"    physical_edges={loop.physical_edges}")
            print(f"    node_sequence={loop.node_sequence}")
            print(f"    path_text={loop.path_text}")
            print(f"    winding={loop.winding}")
            print(f"    edge_count={loop.edge_count}")
            print(f"    closes_periodically={loop.closes_periodically}")
            print(f"    edge_signature={loop.edge_signature}")

        plot_discovered_loops(
            unit_cell_graph,
            loops,
            max_loops=6,
            title=f"First 6 Discovered Non-Zero-Winding Loops ({cycle_mode})",
        )
