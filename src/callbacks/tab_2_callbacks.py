import re

from dash import Input, Output, State, ALL, dash, dcc, html, ctx, no_update
import networkx as nx

from src.core.layer_builder import add_loop_to_layer, build_layer_graph, remove_loop_from_layer
from src.core.loop_finder import discover_valid_loops, loop_record_to_dict
from src.core.periodic_graph import create_periodic_multigraph
from src.core.plot_utils import (
    create_labeled_physical_graph_figure,
    create_loop_preview_figure,
    create_stacked_layer_3d_figure,
)


def _make_layer_record(layer_index: int) -> dict:
    return {
        "layer_id": f"layer-{layer_index}",
        "name": f"Layer {layer_index}",
        "selected_loop_ids": [],
        "validation": {
            "is_valid": True,
            "message": "Current layer is empty.",
            "conflicting_loop_ids": [],
            "shared_edges": [],
        },
        "layer_graph": nx.node_link_data(nx.Graph()),
    }


def _get_active_layer(layers: list[dict] | None, active_layer_id: str | None) -> dict | None:
    if not layers:
        return None

    if active_layer_id:
        for layer in layers:
            if layer["layer_id"] == active_layer_id:
                return layer

    return layers[0]


def _replace_layer(layers: list[dict], updated_layer: dict) -> list[dict]:
    return [
        updated_layer if layer["layer_id"] == updated_layer["layer_id"] else layer
        for layer in layers
    ]


def _next_layer_index(layers: list[dict] | None) -> int:
    if not layers:
        return 1

    max_index = 0
    for layer in layers:
        layer_id = layer.get("layer_id", "")
        match = re.search(r"(\d+)$", layer_id)
        if match:
            max_index = max(max_index, int(match.group(1)))

    return max_index + 1 if max_index else len(layers) + 1


def _validation_label(validation: dict | None) -> str:
    if not validation:
        return "No validation yet."

    if validation.get("is_valid", True):
        return validation.get("message", "Valid")

    return validation.get("message", "Conflict detected")


def _find_triggered_button_click(
    triggered: dict | None,
    click_values: list[int | None] | None,
    button_ids: list[dict] | None,
) -> bool:
    if not isinstance(triggered, dict) or not click_values or not button_ids:
        return False

    for button_id, click_value in zip(button_ids, click_values):
        if button_id == triggered:
            return click_value is not None and click_value > 0

    return False


def _build_action_payload(
    triggered: dict | None,
    click_values: list[int | None] | None,
    button_ids: list[dict] | None,
    action_type: str,
) -> dict | None:
    if not _find_triggered_button_click(triggered, click_values, button_ids):
        return None

    loop_id = triggered.get("loop_id") if isinstance(triggered, dict) else None
    if not loop_id:
        return None

    return {
        "action": action_type,
        "loop_id": loop_id,
        "click_count": max(value or 0 for value in click_values or [0]),
    }


def register_tab_2_callbacks(app):
    @app.callback(
        Output("store-loop-catalog", "data"),
        Output("store-preview-loop-id", "data"),
        Output("store-layers", "data"),
        Output("store-active-layer-id", "data"),
        Input("processing-tabs", "value"),
        State("store-graph-data", "data"),
        State("store-graph-dimensions", "data"),
    )
    def populate_loop_catalog(active_tab, graph_data_json, dimensions):
        if active_tab != "step-2" or graph_data_json is None or dimensions is None:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

        graph = nx.node_link_graph(graph_data_json)
        width, height = dimensions
        periodic_graph, mapping = create_periodic_multigraph(graph, width, height)
        loops = discover_valid_loops(graph, periodic_graph, mapping, cycle_mode="simple")
        catalog = [loop_record_to_dict(loop) for loop in loops]
        preview_loop_id = catalog[0]["loop_id"] if catalog else None
        default_layer = _make_layer_record(1)
        return (
            catalog,
            preview_loop_id,
            [default_layer],
            default_layer["layer_id"],
        )

    @app.callback(
        Output("store-loop-preview-action", "data"),
        Input({"type": "loop-select-btn", "loop_id": ALL}, "n_clicks"),
        State({"type": "loop-select-btn", "loop_id": ALL}, "id"),
        prevent_initial_call=True,
    )
    def capture_loop_preview_action(clicks, button_ids):
        triggered = ctx.triggered_id
        payload = _build_action_payload(triggered, clicks, button_ids, "preview")
        if payload is None:
            return no_update

        return payload

    @app.callback(
        Output("store-preview-loop-id", "data", allow_duplicate=True),
        Input("store-loop-preview-action", "data"),
        State("store-loop-catalog", "data"),
        prevent_initial_call=True,
    )
    def apply_loop_preview_action(preview_action, loop_catalog):
        if not preview_action or not loop_catalog:
            return no_update

        loop_id = preview_action.get("loop_id")
        if not any(loop["loop_id"] == loop_id for loop in loop_catalog):
            return no_update

        return loop_id

    @app.callback(
        Output("store-layers", "data", allow_duplicate=True),
        Output("store-active-layer-id", "data", allow_duplicate=True),
        Input("btn-add-layer", "n_clicks"),
        Input("btn-remove-layer", "n_clicks"),
        State("store-layers", "data"),
        State("store-active-layer-id", "data"),
        prevent_initial_call=True,
    )
    def manage_layer_list(_add_clicks, _remove_clicks, layers, active_layer_id):
        if not layers:
            default_layer = _make_layer_record(1)
            return [default_layer], default_layer["layer_id"]

        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update

        if triggered == "btn-add-layer":
            next_index = _next_layer_index(layers)
            new_layer = _make_layer_record(next_index)
            return [*layers, new_layer], new_layer["layer_id"]

        if triggered == "btn-remove-layer":
            if len(layers) == 1:
                only_layer = layers[0]
                updated_layer = {
                    **only_layer,
                    "validation": {
                        "is_valid": False,
                        "message": "Cannot remove the last remaining layer.",
                        "conflicting_loop_ids": [],
                        "shared_edges": [],
                    },
                }
                return [updated_layer], updated_layer["layer_id"]

            active_id = active_layer_id or layers[0]["layer_id"]
            active_index = next(
                (index for index, layer in enumerate(layers) if layer["layer_id"] == active_id),
                0,
            )
            remaining_layers = [
                layer for layer in layers if layer["layer_id"] != active_id
            ]
            next_active_index = max(0, active_index - 1)
            next_active_id = remaining_layers[next_active_index]["layer_id"]
            return remaining_layers, next_active_id

        return no_update, no_update

    @app.callback(
        Output("store-active-layer-id", "data", allow_duplicate=True),
        Input({"type": "layer-edit-btn", "layer_id": ALL}, "n_clicks"),
        State("store-layers", "data"),
        State({"type": "layer-edit-btn", "layer_id": ALL}, "id"),
        prevent_initial_call=True,
    )
    def set_active_layer(edit_clicks, layers, button_ids):
        if not layers:
            return no_update

        triggered = ctx.triggered_id
        if not _find_triggered_button_click(triggered, edit_clicks, button_ids):
            return no_update

        layer_id = triggered.get("layer_id")
        if not layer_id:
            return no_update

        if not any(layer["layer_id"] == layer_id for layer in layers):
            return no_update

        return layer_id

    @app.callback(
        Output("store-loop-layer-action", "data"),
        Input({"type": "loop-add-btn", "loop_id": ALL}, "n_clicks"),
        Input({"type": "loop-remove-btn", "loop_id": ALL}, "n_clicks"),
        State({"type": "loop-add-btn", "loop_id": ALL}, "id"),
        State({"type": "loop-remove-btn", "loop_id": ALL}, "id"),
        prevent_initial_call=True,
    )
    def capture_layer_loop_action(add_clicks, remove_clicks, add_button_ids, remove_button_ids):
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == "loop-add-btn":
            payload = _build_action_payload(triggered, add_clicks, add_button_ids, "add")
            return payload if payload is not None else no_update

        if isinstance(triggered, dict) and triggered.get("type") == "loop-remove-btn":
            payload = _build_action_payload(triggered, remove_clicks, remove_button_ids, "remove")
            return payload if payload is not None else no_update

        return no_update

    @app.callback(
        Output("store-layers", "data", allow_duplicate=True),
        Input("store-loop-layer-action", "data"),
        State("store-loop-catalog", "data"),
        State("store-layers", "data"),
        State("store-active-layer-id", "data"),
        State("store-graph-data", "data"),
        prevent_initial_call=True,
    )
    def update_current_layer(layer_action, loop_catalog, layers, active_layer_id, graph_data_json):
        if not layer_action or not loop_catalog or graph_data_json is None or not layers:
            return no_update

        loop_id = layer_action.get("loop_id")
        if not loop_id:
            return no_update

        active_layer = _get_active_layer(layers, active_layer_id)
        if active_layer is None:
            return no_update

        current_ids = active_layer["selected_loop_ids"] or []
        if layer_action.get("action") == "add":
            result = add_loop_to_layer(current_ids, loop_catalog, loop_id)
        elif layer_action.get("action") == "remove":
            result = remove_loop_from_layer(current_ids, loop_id)
        else:
            return no_update

        graph = nx.node_link_graph(graph_data_json)
        catalog_by_id = {loop["loop_id"]: loop for loop in loop_catalog}
        selected_loops = [catalog_by_id[selected_id] for selected_id in result.selected_loop_ids if selected_id in catalog_by_id]
        layer_graph = build_layer_graph(selected_loops, graph)

        validation = {
            "is_valid": not result.conflicting_loop_ids,
            "message": result.message,
            "conflicting_loop_ids": list(result.conflicting_loop_ids),
            "shared_edges": [list(edge) for edge in result.shared_edges],
        }

        updated_layer = {
            **active_layer,
            "selected_loop_ids": list(result.selected_loop_ids),
            "validation": validation,
            "layer_graph": nx.node_link_data(layer_graph),
        }
        return _replace_layer(layers, updated_layer)

    @app.callback(
        Output("selected-loop-preview-container", "children"),
        Input("store-graph-data", "data"),
        Input("store-loop-catalog", "data"),
        Input("store-preview-loop-id", "data"),
    )
    def render_loop_preview(
        graph_data_json,
        loop_catalog,
        preview_loop_id,
    ):
        loop_placeholder = html.Div(
            "Select a loop from the list below to preview it here.",
            className="placeholder-text",
        )

        if graph_data_json is None:
            return loop_placeholder

        if not loop_catalog:
            return loop_placeholder

        graph = nx.node_link_graph(graph_data_json)
        selected_loop_id = preview_loop_id or loop_catalog[0]["loop_id"]
        selected_loop = next(
            (loop for loop in loop_catalog if loop["loop_id"] == selected_loop_id),
            loop_catalog[0],
        )

        return dcc.Graph(
            figure=create_loop_preview_figure(
                graph,
                selected_loop["physical_edges"],
                loop_id=selected_loop["loop_id"],
            ),
            config={"responsive": True, "displayModeBar": True, "displaylogo": False},
        )

    @app.callback(
        Output("loop-source-graph-container", "children"),
        Output("loop-catalog-summary", "children"),
        Output("current-layer-summary", "children"),
        Output("layer-validation-message", "children"),
        Output("loop-catalog-container", "children"),
        Output("layer-manager-summary", "children"),
        Output("layer-manager-container", "children"),
        Input("store-graph-data", "data"),
        Input("store-loop-catalog", "data"),
        Input("store-preview-loop-id", "data"),
        Input("store-layers", "data"),
        Input("store-active-layer-id", "data"),
    )
    def render_loop_catalog_view(
        graph_data_json,
        loop_catalog,
        preview_loop_id,
        layers,
        active_layer_id,
    ):
        graph_placeholder = html.Div(
            "Upload a DXF and proceed to loop discovery.",
            className="placeholder-text",
        )

        if graph_data_json is None:
            return (
                graph_placeholder,
                "",
                "",
                "",
                html.Div("No loops discovered yet.", className="placeholder-text"),
                "",
                html.Div("No layers available yet.", className="placeholder-text"),
            )

        graph = nx.node_link_graph(graph_data_json)
        graph_view = dcc.Graph(
            figure=create_labeled_physical_graph_figure(graph, title="Original Physical Graph"),
            config={"responsive": True, "displayModeBar": True, "displaylogo": False},
        )

        if not loop_catalog:
            return (
                graph_view,
                "No loops discovered yet.",
                "",
                "",
                html.Div("No loops discovered yet.", className="placeholder-text"),
                "",
                html.Div("No layers available yet.", className="placeholder-text"),
            )

        active_layer = _get_active_layer(layers, active_layer_id)
        if active_layer is None:
            active_layer = _make_layer_record(1)
        layer_list = layers or [active_layer]
        selected_loop_id = preview_loop_id or loop_catalog[0]["loop_id"]
        selected_loop = next(
            (loop for loop in loop_catalog if loop["loop_id"] == selected_loop_id),
            loop_catalog[0],
        )

        summary = (
            f"Found {len(loop_catalog)} loops. "
            f"Currently previewing {selected_loop['loop_id']} "
            f"with winding {tuple(selected_loop['winding'])}."
        )
        active_ids = active_layer["selected_loop_ids"] if active_layer else []
        current_layer_summary = (
            f"Editing {active_layer['name']}: " if active_layer else "Editing layer: "
        ) + (", ".join(active_ids) if active_ids else "No loops selected yet.")
        validation_message = active_layer["validation"]["message"] if active_layer else ""
        layer_manager_summary = (
            f"{len(layer_list)} layer(s) total. Active layer: {active_layer['name']}."
            if layer_list else
            "No layers available yet."
        )

        rows = []
        for loop in loop_catalog:
            is_selected = loop["loop_id"] == selected_loop["loop_id"]
            is_in_layer = loop["loop_id"] in active_ids
            rows.append(
                html.Tr(
                    [
                        html.Td(loop["loop_id"]),
                        html.Td(str(tuple(loop["winding"]))),
                        html.Td(str(loop["edge_count"])),
                        html.Td(loop["path_text"]),
                        html.Td(
                            html.Button(
                                "Preview" if not is_selected else "Previewing",
                                id={"type": "loop-select-btn", "loop_id": loop["loop_id"]},
                                className="loop-select-btn" + (" is-selected" if is_selected else ""),
                                disabled=is_selected,
                            )
                        ),
                        html.Td(
                            html.Button(
                                "Add" if not is_in_layer else "Added",
                                id={"type": "loop-add-btn", "loop_id": loop["loop_id"]},
                                className="loop-add-btn" + (" is-added" if is_in_layer else ""),
                                disabled=is_in_layer,
                            )
                        ),
                        html.Td(
                            html.Button(
                                "Remove",
                                id={"type": "loop-remove-btn", "loop_id": loop["loop_id"]},
                                className="loop-remove-btn",
                                disabled=not is_in_layer,
                            )
                        ),
                    ],
                    className="loop-row" + (" is-selected" if is_selected else "") + (" is-in-layer" if is_in_layer else ""),
                )
            )

        table = html.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Loop ID"),
                            html.Th("Winding"),
                            html.Th("Edges"),
                            html.Th("Path"),
                            html.Th("Preview"),
                            html.Th("Add"),
                            html.Th("Remove"),
                        ]
                    )
                ),
                html.Tbody(rows),
            ],
            className="loop-table",
        )

        layer_rows = []
        for layer in layer_list:
            is_active_layer = layer["layer_id"] == active_layer["layer_id"]
            layer_loop_text = ", ".join(layer["selected_loop_ids"]) if layer["selected_loop_ids"] else "Empty"
            layer_rows.append(
                html.Tr(
                    [
                        html.Td(layer["name"]),
                        html.Td(layer_loop_text),
                        html.Td(
                            html.Button(
                                "Active" if is_active_layer else "Set Active",
                                id={"type": "layer-edit-btn", "layer_id": layer["layer_id"]},
                                className="layer-edit-btn" + (" is-active" if is_active_layer else ""),
                                disabled=is_active_layer,
                            )
                        ),
                    ],
                    className="is-active-row" if is_active_layer else "",
                )
            )

        layer_manager = html.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Layer"),
                            html.Th("Loops"),
                            html.Th("Action"),
                        ]
                    )
                ),
                html.Tbody(layer_rows),
            ],
            className="loop-table layer-table",
        )

        return (
            graph_view,
            summary,
            current_layer_summary,
            validation_message,
            table,
            layer_manager_summary,
            layer_manager,
        )

    @app.callback(
        Output("stacked-layer-preview-container", "children"),
        Input("store-layers", "data"),
    )
    def render_stacked_layer_preview(layers):
        if not layers:
            return html.Div("No layers available yet.", className="placeholder-text")

        return dcc.Graph(
            figure=create_stacked_layer_3d_figure(layers),
            config={"responsive": True, "displayModeBar": True, "displaylogo": False},
        )
