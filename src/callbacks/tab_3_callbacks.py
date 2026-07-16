from dash import Input, Output, State, dcc, html, no_update
import networkx as nx

from src.core.pathing import connect_chains_sweep
from src.core.periodic_graph import create_periodic_multigraph
from src.core.plot_utils import create_connected_component_figure, create_tiled_component_figure
from src.core.tiling import tile_and_stitch_layer


def _result_options(results: dict | None, layers: list[dict] | None) -> list[dict]:
    if not results or not results.get("layers") or not layers:
        return []

    layer_names = {layer["layer_id"]: layer["name"] for layer in layers}
    return [
        {
            "label": layer_names.get(layer_id, layer_id),
            "value": layer_id,
        }
        for layer_id in results["layers"].keys()
    ]


def register_tab_3_callbacks(app):
    @app.callback(
        Output("processing-tabs", "value", allow_duplicate=True),
        Output("tab-step-3", "disabled", allow_duplicate=True),
        Input("btn-next-step-2", "n_clicks"),
        State("processing-tabs", "value"),
        prevent_initial_call=True,
    )
    def go_to_step_3(n_clicks, current_tab):
        if n_clicks is None:
            return current_tab, no_update

        return "step-3", False

    @app.callback(
        Output("tiling-layer-dropdown", "options"),
        Output("tiling-layer-dropdown", "value"),
        Input("processing-tabs", "value"),
        Input("store-stitched-layer-results", "data"),
        Input("store-connected-layer-results", "data"),
        Input("store-active-layer-id", "data"),
        State("store-layers", "data"),
        State("tiling-layer-dropdown", "value"),
    )
    def populate_tiling_layer_dropdown(
        active_tab,
        stitched_results,
        connected_results,
        active_layer_id,
        layers,
        current_value,
    ):
        if active_tab != "step-3":
            return no_update, no_update

        display_results = connected_results if connected_results and connected_results.get("layers") else stitched_results
        options = _result_options(display_results, layers)
        if not options:
            return [], None

        valid_values = {option["value"] for option in options}
        if current_value in valid_values:
            selected_value = current_value
        elif active_layer_id in valid_values:
            selected_value = active_layer_id
        else:
            selected_value = options[0]["value"]

        return options, selected_value

    @app.callback(
        Output("store-stitched-layer-results", "data"),
        Output("store-connected-layer-results", "data"),
        Output("tiling-status-message", "children"),
        Input("btn-run-tiling", "n_clicks"),
        State("input-tiling-rows", "value"),
        State("input-tiling-cols", "value"),
        State("store-layers", "data"),
        State("store-loop-catalog", "data"),
        State("store-graph-data", "data"),
        State("store-graph-dimensions", "data"),
        prevent_initial_call=True,
    )
    def run_tiling_for_all_layers(
        n_clicks,
        rows,
        cols,
        layers,
        loop_catalog,
        graph_data_json,
        dimensions,
    ):
        if n_clicks is None:
            return no_update, no_update, no_update

        if graph_data_json is None or dimensions is None:
            return no_update, no_update, "No unit-cell graph is available yet."

        if not layers:
            return no_update, no_update, "Build at least one layer in Step 2 first."

        if not rows or not cols or rows < 1 or cols < 1:
            return no_update, no_update, "Rows and columns must both be at least 1."

        catalog_by_id = {loop["loop_id"]: loop for loop in (loop_catalog or [])}
        graph = nx.node_link_graph(graph_data_json)
        width, height = dimensions
        _periodic_graph, mapping = create_periodic_multigraph(graph, width, height)
        results = {
            "rows": int(rows),
            "cols": int(cols),
            "layers": {},
        }
        tiled_layer_count = 0
        skipped_layers = []

        for layer in layers:
            selected_loop_ids = layer.get("selected_loop_ids", [])
            if not selected_loop_ids:
                skipped_layers.append(f"{layer['name']} (empty)")
                continue

            selected_loops = [
                catalog_by_id[loop_id]
                for loop_id in selected_loop_ids
                if loop_id in catalog_by_id
            ]
            if not selected_loops:
                skipped_layers.append(f"{layer['name']} (missing loop records)")
                continue

            threaded_layer, stitched_graph = tile_and_stitch_layer(
                selected_loops,
                graph,
                mapping,
                width,
                height,
                int(rows),
                int(cols),
            )

            results["layers"][layer["layer_id"]] = {
                "layer_name": layer["name"],
                "selected_loop_ids": list(selected_loop_ids),
                "threaded_node_count": len(threaded_layer.node_records),
                "threaded_edge_count": len(threaded_layer.threaded_edges),
                "stitched_graph": nx.node_link_data(stitched_graph),
                "stitched_node_count": stitched_graph.number_of_nodes(),
                "stitched_edge_count": stitched_graph.number_of_edges(),
                "component_count": nx.number_connected_components(stitched_graph),
            }
            tiled_layer_count += 1

        if tiled_layer_count == 0:
            return no_update, no_update, "No non-empty layers could be tiled. Build at least one non-empty layer in Step 2 first."

        skipped_text = f" Skipped: {', '.join(skipped_layers)}." if skipped_layers else ""
        status = (
            f"Tiling and stitching completed for {tiled_layer_count} layer(s) "
            f"on a {int(rows)} x {int(cols)} grid.{skipped_text}"
        )
        return results, None, status

    @app.callback(
        Output("store-connected-layer-results", "data", allow_duplicate=True),
        Output("tiling-status-message", "children", allow_duplicate=True),
        Input("btn-connect-chains", "n_clicks"),
        State("connection-mode-dropdown", "value"),
        State("store-stitched-layer-results", "data"),
        prevent_initial_call=True,
    )
    def connect_all_stitched_layers(n_clicks, connection_mode, stitched_results):
        if n_clicks is None:
            return no_update, no_update

        if not stitched_results or not stitched_results.get("layers"):
            return no_update, "Run Tile and Stitch before connecting chains."

        if connection_mode not in {"closest", "avoid_intersection", "parallel"}:
            return no_update, "Select a valid connection mode."

        connected_results = {
            "rows": stitched_results["rows"],
            "cols": stitched_results["cols"],
            "mode": connection_mode,
            "layers": {},
        }

        for layer_id, result in stitched_results["layers"].items():
            stitched_graph = nx.node_link_graph(result["stitched_graph"])
            connection_result = connect_chains_sweep(stitched_graph, mode=connection_mode)
            connected_results["layers"][layer_id] = {
                **result,
                "connected_graph": nx.node_link_data(connection_result.connected_graph),
                "added_edges": [list(edge) for edge in connection_result.added_edges],
                "component_count_before_connection": connection_result.component_count_before,
                "component_count_after_connection": connection_result.component_count_after,
            }

        mode_labels = {
            "closest": "Closest Sweep",
            "avoid_intersection": "Sweep Avoid Crossings",
            "parallel": "Closest Sweep + Parallel Filter",
        }
        mode_label = mode_labels[connection_mode]
        status = f"Chain connection completed for all stitched layers using {mode_label} mode."
        return connected_results, status

    @app.callback(
        Output("tiling-preview-container", "children"),
        Output("tiling-preview-summary", "children"),
        Input("tiling-layer-dropdown", "value"),
        Input("store-stitched-layer-results", "data"),
        Input("store-connected-layer-results", "data"),
        State("store-graph-dimensions", "data"),
    )
    def render_stitched_layer_preview(selected_layer_id, stitched_results, connected_results, dimensions):
        display_results = connected_results if connected_results and connected_results.get("layers") else stitched_results
        if not display_results or not display_results.get("layers"):
            placeholder = html.Div(
                "Run Tile and Stitch to generate stitched layer results.",
                className="placeholder-text",
            )
            return placeholder, ""

        if dimensions is None:
            placeholder = html.Div("No unit-cell dimensions available.", className="placeholder-text")
            return placeholder, ""

        results_by_layer = display_results["layers"]
        if not selected_layer_id or selected_layer_id not in results_by_layer:
            first_layer_id = next(iter(results_by_layer.keys()))
            selected_layer_id = first_layer_id

        result = results_by_layer[selected_layer_id]
        width, height = dimensions
        rows = display_results["rows"]
        cols = display_results["cols"]

        if connected_results and connected_results.get("layers") and selected_layer_id in connected_results["layers"]:
            connected_graph = nx.node_link_graph(result["connected_graph"])
            added_edges = [tuple(edge) for edge in result.get("added_edges", [])]
            preview = dcc.Graph(
                figure=create_connected_component_figure(
                    connected_graph,
                    added_edges,
                    width,
                    height,
                    rows,
                    cols,
                    title=f"{result['layer_name']} Connected Chains",
                ),
                config={"responsive": True, "displayModeBar": True, "displaylogo": False},
            )
            summary = (
                f"Displaying connected {result['layer_name']} on a {rows} x {cols} grid. "
                f"Loops: {', '.join(result['selected_loop_ids'])}. "
                f"Threaded unit-cell: {result['threaded_node_count']} nodes, "
                f"{result['threaded_edge_count']} edges. "
                f"Before connection: {result['component_count_before_connection']} component(s). "
                f"After connection: {result['component_count_after_connection']} component(s). "
                f"Added edges: {len(result.get('added_edges', []))}."
            )
        else:
            stitched_graph = nx.node_link_graph(result["stitched_graph"])
            preview = dcc.Graph(
                figure=create_tiled_component_figure(
                    stitched_graph,
                    width,
                    height,
                    rows,
                    cols,
                    title=f"{result['layer_name']} Components",
                ),
                config={"responsive": True, "displayModeBar": True, "displaylogo": False},
            )
            summary = (
                f"Displaying stitched {result['layer_name']} on a {rows} x {cols} grid. "
                f"Loops: {', '.join(result['selected_loop_ids'])}. "
                f"Threaded unit-cell: {result['threaded_node_count']} nodes, "
                f"{result['threaded_edge_count']} edges. "
                f"Stitched result: {result['stitched_node_count']} nodes, "
                f"{result['stitched_edge_count']} edges, "
                f"{result['component_count']} connected component(s)."
            )
        return preview, summary
