from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib import cm
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D


plt.rcParams.update(
    {
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 12,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


@dataclass(frozen=True)
class VariantConfig:
    dataset: str
    variant: str
    unit_plot_mode: str


VARIANT_CONFIGS = (
    VariantConfig("honeycomb", "2-layer-setting", "layer_graph"),
    VariantConfig("honeycomb", "3-layer-setting", "layer_graph"),
    VariantConfig("reentrant", "split-1", "layer_graph"),
    VariantConfig("reentrant", "split-2", "layer_graph"),
    VariantConfig("snake", "crossing", "selected_loops"),
    VariantConfig("snake", "crossing-parallel", "selected_loops"),
    VariantConfig("snake", "non-crossing", "selected_loops"),
)


def _load_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except JSONDecodeError:
        return json.loads(text.lstrip("\ufeff\n\r\t "))


def _normalize_layers(payload) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            return payload["data"]
        if "layer_id" in payload:
            return [payload]
        return list(payload.values())
    raise TypeError(f"Unsupported layer payload type: {type(payload)!r}")


def _fallback_layers_from_results(stitched_results: dict | None, connected_results: dict | None) -> list[dict]:
    source_results = connected_results if connected_results and connected_results.get("layers") else stitched_results
    if not source_results or not source_results.get("layers"):
        return []

    recovered_layers = []
    for layer_id, layer_result in source_results["layers"].items():
        recovered_layers.append(
            {
                "layer_id": layer_id,
                "name": layer_result.get("layer_name", layer_id),
                "selected_loop_ids": list(layer_result.get("selected_loop_ids", [])),
            }
        )
    return recovered_layers


def _node_sort_key(graph: nx.Graph, node_id) -> tuple[float, float, str]:
    x, y = graph.nodes[node_id]["pos"]
    return float(x), float(y), str(node_id)


def _ordered_neighbors(graph: nx.Graph, node_id) -> list:
    return sorted(graph.neighbors(node_id), key=lambda neighbor: _node_sort_key(graph, neighbor))


def _edge_key(u, v) -> tuple[str, str]:
    return tuple(sorted((str(u), str(v))))


def _graph_from_payload(payload: dict) -> nx.Graph:
    graph = nx.node_link_graph(payload)
    for node_id, data in graph.nodes(data=True):
        if "pos" in data:
            x, y = data["pos"]
            data["pos"] = (float(x), float(y))
    return graph


def _bounds_from_graph(graph: nx.Graph) -> tuple[float, float]:
    positions = [data["pos"] for _, data in graph.nodes(data=True) if "pos" in data]
    if not positions:
        raise ValueError("Cannot infer graph dimensions from a graph with no positioned nodes.")

    all_x = [float(position[0]) for position in positions]
    all_y = [float(position[1]) for position in positions]
    return max(all_x) - min(all_x), max(all_y) - min(all_y)


def _loop_catalog_by_id(loop_catalog: list[dict]) -> dict[str, dict]:
    return {loop["loop_id"]: loop for loop in loop_catalog}


def _unit_segments_from_loop(loop_record: dict, graph: nx.Graph) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments = []
    for start_node, end_node in loop_record.get("physical_edges", []):
        start_pos = tuple(graph.nodes[start_node]["pos"])
        end_pos = tuple(graph.nodes[end_node]["pos"])
        segments.append((start_pos, end_pos))
    return segments


def _graph_segments(graph: nx.Graph) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments = []
    for start_node, end_node in graph.edges():
        start_pos = tuple(graph.nodes[start_node]["pos"])
        end_pos = tuple(graph.nodes[end_node]["pos"])
        segments.append((start_pos, end_pos))
    return segments


def _is_zero_length_segment(segment: np.ndarray | tuple[tuple[float, float], tuple[float, float]], tolerance: float = 1e-9) -> bool:
    start_pos, end_pos = segment
    return abs(float(start_pos[0]) - float(end_pos[0])) <= tolerance and abs(float(start_pos[1]) - float(end_pos[1])) <= tolerance


def _draw_boundary(ax, width: float, height: float, rows: int = 1, cols: int = 1) -> None:
    boundary_x = [0.0, width * cols, width * cols, 0.0, 0.0]
    boundary_y = [0.0, 0.0, height * rows, height * rows, 0.0]
    ax.plot(boundary_x, boundary_y, "k--", alpha=0.45, linewidth=1.2, dashes=(4, 4), label="Boundary")


def _apply_axes_style(ax, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
    x_pad = max((x_max - x_min) * 0.05, 0.4)
    y_pad = max((y_max - y_min) * 0.05, 0.4)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)
    ax.set_aspect("equal")
    ax.set_xlabel("X Position (mm)")
    ax.set_ylabel("Y Position (mm)")
    ax.grid(True, linestyle=":", alpha=0.35)


def _save_figure(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="pdf", bbox_inches="tight", dpi=300)
    plt.close(fig)


def _draw_segment_collection(
    ax,
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    color,
    linewidth: float,
    zorder: int,
    label: str | None = None,
) -> None:
    if not segments:
        return

    line_collection = LineCollection(
        np.array(segments),
        colors=[color],
        linewidths=linewidth,
        capstyle="round",
        joinstyle="round",
        zorder=zorder,
        label=label,
    )
    ax.add_collection(line_collection)


def _draw_component_plot(
    graph: nx.Graph,
    width: float,
    height: float,
    rows: int,
    cols: int,
    title: str,
    output_path: Path,
) -> None:
    positions = nx.get_node_attributes(graph, "pos")
    components = list(nx.connected_components(graph))
    component_cmap = plt.get_cmap("tab10", max(len(components), 1))

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    _draw_boundary(ax, width, height, rows=rows, cols=cols)

    legend_handles = [Line2D([0], [0], color="black", linestyle="--", linewidth=1.2, label="Boundary")]

    for component_index, component_nodes in enumerate(components):
        component_graph = graph.subgraph(component_nodes)
        component_color = component_cmap(component_index)
        component_segments = _graph_segments(component_graph)
        _draw_segment_collection(ax, component_segments, "black", 3.8, zorder=1)
        _draw_segment_collection(
            ax,
            component_segments,
            component_color,
            2.0,
            zorder=2,
            label=f"Chain {component_index + 1}",
        )

        node_x = [positions[node_id][0] for node_id in component_graph.nodes()]
        node_y = [positions[node_id][1] for node_id in component_graph.nodes()]
        ax.scatter(node_x, node_y, color=component_color, s=16, edgecolors="black", linewidths=0.4, zorder=3)
        legend_handles.append(Line2D([0], [0], color=component_color, linewidth=2.0, label=f"Chain {component_index + 1}"))

    _apply_axes_style(ax, 0.0, width * cols, 0.0, height * rows)
    ax.legend(handles=legend_handles, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig.tight_layout(pad=0.5)
    _save_figure(fig, output_path)


def _pick_path_start_node(graph: nx.Graph, added_edges: list[tuple[str, str]]) -> str:
    endpoints = [node_id for node_id, degree in graph.degree() if degree == 1]
    if not endpoints:
        return min(graph.nodes(), key=lambda node_id: _node_sort_key(graph, node_id))

    if added_edges:
        anchor_nodes = {str(added_edges[0][0]), str(added_edges[0][1])}
        anchored_endpoints = [node_id for node_id in endpoints if str(node_id) in anchor_nodes]
        if anchored_endpoints:
            return min(anchored_endpoints, key=lambda node_id: _node_sort_key(graph, node_id))

    return min(endpoints, key=lambda node_id: _node_sort_key(graph, node_id))


def _build_ordered_edge_walk(graph: nx.Graph, added_edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if graph.number_of_edges() == 0:
        return []

    start_node = _pick_path_start_node(graph, added_edges)
    ordered_edges: list[tuple[str, str]] = []
    visited_edges: set[tuple[str, str]] = set()
    current_node = start_node
    previous_node = None

    while True:
        candidate_neighbors = [neighbor for neighbor in _ordered_neighbors(graph, current_node) if neighbor != previous_node]
        next_node = None
        for neighbor in candidate_neighbors:
            key = _edge_key(current_node, neighbor)
            if key in visited_edges:
                continue
            next_node = neighbor
            break

        if next_node is None:
            break

        visited_edges.add(_edge_key(current_node, next_node))
        ordered_edges.append((current_node, next_node))
        previous_node, current_node = current_node, next_node

    if len(ordered_edges) != graph.number_of_edges():
        raise ValueError(
            "Connected path plot expects a single continuous non-branching path, "
            f"but visited {len(ordered_edges)} of {graph.number_of_edges()} edges."
        )

    return ordered_edges


def _draw_gradient_path_plot(
    graph: nx.Graph,
    width: float,
    height: float,
    rows: int,
    cols: int,
    title: str,
    added_edges: list[tuple[str, str]],
    output_path: Path,
) -> None:
    ordered_edges = _build_ordered_edge_walk(graph, added_edges)
    if not ordered_edges:
        return

    raw_segments = np.array(
        [
            [graph.nodes[start_node]["pos"], graph.nodes[end_node]["pos"]]
            for start_node, end_node in ordered_edges
        ],
        dtype=float,
    )
    nonzero_mask = np.array([not _is_zero_length_segment(segment) for segment in raw_segments], dtype=bool)
    segments = raw_segments[nonzero_mask]
    if len(segments) == 0:
        return

    segment_count = len(segments)
    cmap = plt.get_cmap("autumn")
    norm = plt.Normalize(0, max(segment_count - 1, 1))
    mapped_colors = cmap(norm(np.arange(segment_count)))

    indices = []
    types = []
    for index in range(segment_count + 1):
        if index < segment_count:
            indices.append(index)
            types.append(0)
        if index > 0:
            indices.append(index - 1)
            types.append(1)
    indices.append(segment_count - 1)
    types.append(1)

    indices_array = np.array(indices)
    types_array = np.array(types)
    ordered_segments = segments[indices_array]
    ordered_linewidths = np.zeros(len(indices_array))
    ordered_linewidths[types_array == 0] = 4.2
    ordered_linewidths[types_array == 1] = 1.8

    ordered_colors = np.zeros((len(indices_array), 4))
    ordered_colors[types_array == 0] = [0.0, 0.0, 0.0, 1.0]
    ordered_colors[types_array == 1] = mapped_colors[indices_array[types_array == 1]]

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    _draw_boundary(ax, width, height, rows=rows, cols=cols)

    base_segments = _graph_segments(graph)
    _draw_segment_collection(ax, base_segments, "#d1d5db", 1.0, zorder=0)

    line_collection = LineCollection(
        np.array(ordered_segments),
        colors=ordered_colors,
        linewidths=ordered_linewidths,
        capstyle="round",
        joinstyle="round",
        zorder=2,
    )
    ax.add_collection(line_collection)

    start_point = segments[0][0]
    end_point = segments[-1][1]
    ax.plot(start_point[0], start_point[1], "ko", markersize=4.0, zorder=4, label="Start")
    ax.plot(end_point[0], end_point[1], "ks", markersize=4.2, zorder=4, label="End")

    _apply_axes_style(ax, 0.0, width * cols, 0.0, height * rows)

    scalar_mappable = cm.ScalarMappable(cmap=cmap, norm=norm)
    scalar_mappable.set_array([])
    colorbar = fig.colorbar(scalar_mappable, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label("Print Sequence →")

    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), frameon=False, ncol=2)
    fig.tight_layout(pad=0.5)
    _save_figure(fig, output_path)


def _draw_layer_graph_plot(
    graph: nx.Graph,
    width: float,
    height: float,
    title: str,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    _draw_boundary(ax, width, height)
    segments = _graph_segments(graph)
    _draw_segment_collection(ax, segments, "black", 3.6, zorder=1)
    _draw_segment_collection(ax, segments, "#1d4ed8", 1.8, zorder=2)
    _apply_axes_style(ax, 0.0, width, 0.0, height)
    fig.tight_layout(pad=0.5)
    _save_figure(fig, output_path)


def _draw_selected_loops_plot(
    original_graph: nx.Graph,
    width: float,
    height: float,
    selected_loop_ids: list[str],
    loop_catalog_by_id: dict[str, dict],
    title: str,
    output_path: Path,
) -> None:
    selected_loops = [loop_catalog_by_id[loop_id] for loop_id in selected_loop_ids if loop_id in loop_catalog_by_id]
    if not selected_loops:
        return

    figure_width = max(4.6, 3.3 * len(selected_loops))
    fig, axes = plt.subplots(1, len(selected_loops), figsize=(figure_width, 4.1), squeeze=False)

    for axis, loop_record in zip(axes[0], selected_loops):
        _draw_boundary(axis, width, height)
        segments = _unit_segments_from_loop(loop_record, original_graph)
        _draw_segment_collection(axis, segments, "black", 3.4, zorder=1)
        _draw_segment_collection(axis, segments, "#1d4ed8", 1.8, zorder=2)
        _apply_axes_style(axis, 0.0, width, 0.0, height)

    fig.tight_layout(pad=0.6)
    _save_figure(fig, output_path)


def _iter_variant_configs(output_root: Path, dataset_filter: str | None, variant_filter: str | None) -> Iterable[VariantConfig]:
    for config in VARIANT_CONFIGS:
        if dataset_filter and config.dataset != dataset_filter:
            continue
        if variant_filter and config.variant != variant_filter:
            continue
        variant_dir = output_root / config.dataset / config.variant
        if variant_dir.exists():
            yield config


def _resolve_graph_dimensions(
    dataset_root: Path,
    stitched_results: dict | None,
    connected_results: dict | None,
) -> tuple[float, float]:
    dimensions_payload = _load_json(dataset_root / "graph-dimensions.json")
    if dimensions_payload:
        width, height = dimensions_payload
        return float(width), float(height)

    graph_data_payload = _load_json(dataset_root / "graph-data.json")
    if graph_data_payload:
        return _bounds_from_graph(_graph_from_payload(graph_data_payload))

    source_results = connected_results if connected_results and connected_results.get("layers") else stitched_results
    if not source_results or not source_results.get("layers"):
        raise ValueError(f"Could not resolve graph dimensions for dataset root {dataset_root}.")

    sample_layer = next(iter(source_results["layers"].values()))
    sample_graph_payload = sample_layer.get("stitched_graph") or sample_layer.get("connected_graph")
    if not sample_graph_payload:
        raise ValueError(f"Could not infer graph dimensions from stitched or connected results in {dataset_root}.")

    sample_graph = _graph_from_payload(sample_graph_payload)
    rows = max(int(source_results.get("rows", 1)), 1)
    cols = max(int(source_results.get("cols", 1)), 1)
    total_width, total_height = _bounds_from_graph(sample_graph)
    return total_width / cols, total_height / rows


def _render_variant(output_root: Path, config: VariantConfig) -> list[Path]:
    dataset_root = output_root / config.dataset
    variant_root = dataset_root / config.variant
    plots_root = variant_root / "plots"

    stitched_results = _load_json(variant_root / "stitched-layer-results.json")
    connected_results = _load_json(variant_root / "connected-layer-results.json")
    width, height = _resolve_graph_dimensions(dataset_root, stitched_results, connected_results)
    original_graph = None
    loop_catalog_by_id: dict[str, dict] = {}
    if config.unit_plot_mode == "selected_loops":
        original_graph = _graph_from_payload(_load_json(dataset_root / "graph-data.json"))
        loop_catalog = _load_json(dataset_root / "loop-catalog.json")
        loop_catalog_by_id = _loop_catalog_by_id(loop_catalog)

    layers = _normalize_layers(_load_json(variant_root / "layers.json"))
    if not layers:
        layers = _fallback_layers_from_results(stitched_results, connected_results)
    rows = int(stitched_results["rows"])
    cols = int(stitched_results["cols"])

    generated_paths: list[Path] = []

    for layer in layers:
        layer_id = layer["layer_id"]
        layer_name = layer.get("name") or layer.get("layer_name") or layer_id
        safe_layer_name = layer_id.replace("/", "-")

        if config.unit_plot_mode == "layer_graph":
            layer_graph = _graph_from_payload(layer["layer_graph"])
            layer_graph_path = plots_root / f"{config.dataset}_{config.variant}_{safe_layer_name}_layer-graph.pdf"
            _draw_layer_graph_plot(
                layer_graph,
                width,
                height,
                title=f"{layer_name} Layer Graph",
                output_path=layer_graph_path,
            )
            generated_paths.append(layer_graph_path)
        elif config.unit_plot_mode == "selected_loops":
            selected_loops_path = plots_root / f"{config.dataset}_{config.variant}_{safe_layer_name}_loops.pdf"
            _draw_selected_loops_plot(
                original_graph,
                width,
                height,
                layer.get("selected_loop_ids", []),
                loop_catalog_by_id,
                title=f"{layer_name} Selected Loops",
                output_path=selected_loops_path,
            )
            generated_paths.append(selected_loops_path)

        stitched_layer = stitched_results["layers"].get(layer_id)
        if stitched_layer:
            stitched_graph = _graph_from_payload(stitched_layer["stitched_graph"])
            stitched_path = plots_root / f"{config.dataset}_{config.variant}_{safe_layer_name}_stitched.pdf"
            _draw_component_plot(
                stitched_graph,
                width,
                height,
                rows,
                cols,
                title=f"{layer_name} Stitched Components",
                output_path=stitched_path,
            )
            generated_paths.append(stitched_path)

        connected_layer = connected_results["layers"].get(layer_id)
        if connected_layer:
            connected_graph = _graph_from_payload(connected_layer["connected_graph"])
            added_edges = [tuple(edge) for edge in connected_layer.get("added_edges", [])]
            connected_path = plots_root / f"{config.dataset}_{config.variant}_{safe_layer_name}_connected.pdf"
            _draw_gradient_path_plot(
                connected_graph,
                width,
                height,
                rows,
                cols,
                title=f"{layer_name} Connected Path",
                added_edges=added_edges,
                output_path=connected_path,
            )
            generated_paths.append(connected_path)

    return generated_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate publication-ready PDFs from exported JSON results.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("output"),
        help="Root folder containing exported JSON results.",
    )
    parser.add_argument(
        "--dataset",
        choices=sorted({config.dataset for config in VARIANT_CONFIGS}),
        help="Optional dataset filter.",
    )
    parser.add_argument(
        "--variant",
        help="Optional variant filter inside the selected dataset.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_paths: list[Path] = []
    for config in _iter_variant_configs(args.output_root, args.dataset, args.variant):
        generated_paths.extend(_render_variant(args.output_root, config))

    if not generated_paths:
        raise SystemExit("No matching dataset variants were found under the requested output root.")

    print(f"Generated {len(generated_paths)} plot file(s):")
    for path in generated_paths:
        print(path)


if __name__ == "__main__":
    main()