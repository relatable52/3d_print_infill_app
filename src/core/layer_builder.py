from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class LayerOperationResult:
    selected_loop_ids: tuple[str, ...]
    added: bool
    removed: bool
    message: str
    conflicting_loop_ids: tuple[str, ...]
    shared_edges: tuple[tuple[int, int], ...]


def loop_to_edge_set(loop_record: dict) -> set[tuple[int, int]]:
    """Return the undirected physical edge set used by a loop."""
    return {tuple(sorted(edge)) for edge in loop_record["physical_edges"]}


def find_loop_edge_conflicts(existing_loops: list[dict], candidate_loop: dict) -> list[dict]:
    """Return conflicts between a candidate loop and the current layer loops."""
    candidate_edges = loop_to_edge_set(candidate_loop)
    conflicts = []

    for loop in existing_loops:
        shared_edges = sorted(candidate_edges.intersection(loop_to_edge_set(loop)))
        if shared_edges:
            conflicts.append(
                {
                    "loop_id": loop["loop_id"],
                    "shared_edges": tuple(shared_edges),
                }
            )

    return conflicts


def can_add_loop(existing_loops: list[dict], candidate_loop: dict) -> dict:
    """Check whether a loop can be added to the current layer."""
    conflicts = find_loop_edge_conflicts(existing_loops, candidate_loop)
    if not conflicts:
        return {
            "allowed": True,
            "message": f"Added {candidate_loop['loop_id']} to the current layer.",
            "conflicting_loop_ids": tuple(),
            "shared_edges": tuple(),
        }

    conflicting_ids = tuple(conflict["loop_id"] for conflict in conflicts)
    shared_edges = tuple(
        edge
        for conflict in conflicts
        for edge in conflict["shared_edges"]
    )
    return {
        "allowed": False,
        "message": (
            f"Cannot add {candidate_loop['loop_id']}. "
            f"It shares edges with {', '.join(conflicting_ids)}."
        ),
        "conflicting_loop_ids": conflicting_ids,
        "shared_edges": shared_edges,
    }


def add_loop_to_layer(
    selected_loop_ids: list[str] | tuple[str, ...],
    loop_catalog: list[dict],
    candidate_loop_id: str,
) -> LayerOperationResult:
    """Attempt to add one loop to the current layer."""
    current_ids = list(selected_loop_ids)
    if candidate_loop_id in current_ids:
        return LayerOperationResult(
            selected_loop_ids=tuple(current_ids),
            added=False,
            removed=False,
            message=f"{candidate_loop_id} is already in the current layer.",
            conflicting_loop_ids=tuple(),
            shared_edges=tuple(),
        )

    catalog_by_id = {loop["loop_id"]: loop for loop in loop_catalog}
    candidate_loop = catalog_by_id[candidate_loop_id]
    existing_loops = [catalog_by_id[loop_id] for loop_id in current_ids if loop_id in catalog_by_id]

    validation = can_add_loop(existing_loops, candidate_loop)
    if not validation["allowed"]:
        return LayerOperationResult(
            selected_loop_ids=tuple(current_ids),
            added=False,
            removed=False,
            message=validation["message"],
            conflicting_loop_ids=validation["conflicting_loop_ids"],
            shared_edges=validation["shared_edges"],
        )

    return LayerOperationResult(
        selected_loop_ids=tuple(current_ids + [candidate_loop_id]),
        added=True,
        removed=False,
        message=validation["message"],
        conflicting_loop_ids=tuple(),
        shared_edges=tuple(),
    )


def remove_loop_from_layer(
    selected_loop_ids: list[str] | tuple[str, ...],
    loop_id: str,
) -> LayerOperationResult:
    """Remove one loop from the current layer."""
    updated_ids = tuple(existing_id for existing_id in selected_loop_ids if existing_id != loop_id)
    if len(updated_ids) == len(selected_loop_ids):
        return LayerOperationResult(
            selected_loop_ids=tuple(selected_loop_ids),
            added=False,
            removed=False,
            message=f"{loop_id} was not present in the current layer.",
            conflicting_loop_ids=tuple(),
            shared_edges=tuple(),
        )

    return LayerOperationResult(
        selected_loop_ids=updated_ids,
        added=False,
        removed=True,
        message=f"Removed {loop_id} from the current layer.",
        conflicting_loop_ids=tuple(),
        shared_edges=tuple(),
    )


def build_layer_graph(selected_loops: list[dict], original_graph: nx.Graph) -> nx.Graph:
    """Merge selected loops into a single unit-cell layer graph."""
    layer_graph = nx.Graph()

    for loop in selected_loops:
        for start, end in loop["physical_edges"]:
            if start not in layer_graph:
                layer_graph.add_node(start, pos=original_graph.nodes[start]["pos"])
            if end not in layer_graph:
                layer_graph.add_node(end, pos=original_graph.nodes[end]["pos"])
            layer_graph.add_edge(start, end)

    return layer_graph
