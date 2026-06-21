from dash import Input, Output, State, ALL, dash, dcc, html, ctx, no_update
import networkx as nx

from src.core.loop_finder import discover_valid_loops, loop_record_to_dict
from src.core.periodic_graph import create_periodic_multigraph
from src.core.plot_utils import (
    create_labeled_physical_graph_figure,
    create_loop_preview_figure,
)


def register_tab_2_callbacks(app):
    @app.callback(
        Output("store-loop-catalog", "data"),
        Output("store-active-layer-loop-ids", "data"),
        Input("processing-tabs", "value"),
        State("store-graph-data", "data"),
        State("store-graph-dimensions", "data"),
    )
    def populate_loop_catalog(active_tab, graph_data_json, dimensions):
        if active_tab != "step-2" or graph_data_json is None or dimensions is None:
            return dash.no_update, dash.no_update

        graph = nx.node_link_graph(graph_data_json)
        width, height = dimensions
        periodic_graph, mapping = create_periodic_multigraph(graph, width, height)
        loops = discover_valid_loops(graph, periodic_graph, mapping, cycle_mode="simple")
        catalog = [loop_record_to_dict(loop) for loop in loops]
        selected = [catalog[0]["loop_id"]] if catalog else []
        return catalog, selected

    @app.callback(
        Output("store-active-layer-loop-ids", "data", allow_duplicate=True),
        Input({"type": "loop-select-btn", "loop_id": ALL}, "n_clicks"),
        State("store-loop-catalog", "data"),
        prevent_initial_call=True,
    )
    def select_loop_for_preview(_n_clicks, loop_catalog):
        if not loop_catalog:
            return no_update

        triggered = ctx.triggered_id
        if not isinstance(triggered, dict):
            return no_update

        loop_id = triggered.get("loop_id")
        if not loop_id:
            return no_update

        return [loop_id]

    @app.callback(
        Output("loop-source-graph-container", "children"),
        Output("selected-loop-preview-container", "children"),
        Output("loop-catalog-summary", "children"),
        Output("loop-catalog-container", "children"),
        Input("store-graph-data", "data"),
        Input("store-loop-catalog", "data"),
        Input("store-active-layer-loop-ids", "data"),
    )
    def render_loop_catalog_view(graph_data_json, loop_catalog, selected_loop_ids):
        graph_placeholder = html.Div(
            "Upload a DXF and proceed to loop discovery.",
            className="placeholder-text",
        )
        loop_placeholder = html.Div(
            "Select a loop from the list below to preview it here.",
            className="placeholder-text",
        )

        if graph_data_json is None:
            return (
                graph_placeholder,
                loop_placeholder,
                "",
                html.Div("No loops discovered yet.", className="placeholder-text"),
            )

        graph = nx.node_link_graph(graph_data_json)
        graph_view = dcc.Graph(
            figure=create_labeled_physical_graph_figure(graph, title="Original Physical Graph"),
            config={"responsive": True, "displayModeBar": True, "displaylogo": False},
        )

        if not loop_catalog:
            return (
                graph_view,
                loop_placeholder,
                "No loops discovered yet.",
                html.Div("No loops discovered yet.", className="placeholder-text"),
            )

        selected_loop_id = selected_loop_ids[0] if selected_loop_ids else loop_catalog[0]["loop_id"]
        selected_loop = next(
            (loop for loop in loop_catalog if loop["loop_id"] == selected_loop_id),
            loop_catalog[0],
        )

        selected_view = dcc.Graph(
            figure=create_loop_preview_figure(
                graph,
                selected_loop["physical_edges"],
                loop_id=selected_loop["loop_id"],
            ),
            config={"responsive": True, "displayModeBar": True, "displaylogo": False},
        )

        summary = (
            f"Found {len(loop_catalog)} loops. "
            f"Currently previewing {selected_loop['loop_id']} "
            f"with winding {tuple(selected_loop['winding'])}."
        )

        rows = []
        for loop in loop_catalog:
            is_selected = loop["loop_id"] == selected_loop["loop_id"]
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
                    ],
                    className="loop-row" + (" is-selected" if is_selected else ""),
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
                        ]
                    )
                ),
                html.Tbody(rows),
            ],
            className="loop-table",
        )

        return graph_view, selected_view, summary, table
