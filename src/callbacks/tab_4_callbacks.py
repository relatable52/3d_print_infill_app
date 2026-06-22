from dash import Input, Output, State, dcc, no_update

from src.core.gcode import (
    ExportSettings,
    build_fullcontrol_steps,
    build_repeating_layer_sequence,
    generate_fullcontrol_gcode,
    generate_fullcontrol_plot_data,
)
from src.core.plot_utils import create_fullcontrol_plot_figure


def _connected_results_for_export(connected_results: dict | None, stitched_results: dict | None) -> dict | None:
    if connected_results and connected_results.get("layers"):
        return connected_results
    if stitched_results and stitched_results.get("layers"):
        return stitched_results
    return None


def _design_cycle_summary(layers: list[dict], export_results: dict | None) -> str:
    if not export_results or not export_results.get("layers") or not layers:
        return "No export-ready layer cycle is available yet."

    available_layers = export_results["layers"]
    cycle_names = [
        available_layers[layer["layer_id"]]["layer_name"]
        for layer in layers
        if layer["layer_id"] in available_layers
    ]
    if not cycle_names:
        return "No export-ready layer cycle is available yet."

    return f"Designed layer cycle: {' -> '.join(cycle_names)}"


def register_tab_4_callbacks(app):
    @app.callback(
        Output("processing-tabs", "value", allow_duplicate=True),
        Output("tab-step-4", "disabled", allow_duplicate=True),
        Input("btn-next-step-3", "n_clicks"),
        State("processing-tabs", "value"),
        prevent_initial_call=True,
    )
    def go_to_step_4(n_clicks, current_tab):
        if n_clicks is None:
            return current_tab, no_update

        return "step-4", False

    @app.callback(
        Output("export-cycle-summary", "children"),
        Input("processing-tabs", "value"),
        Input("store-layers", "data"),
        Input("store-stitched-layer-results", "data"),
        Input("store-connected-layer-results", "data"),
    )
    def render_export_cycle_summary(active_tab, layers, stitched_results, connected_results):
        if active_tab != "step-4":
            return no_update

        export_results = _connected_results_for_export(connected_results, stitched_results)
        return _design_cycle_summary(layers or [], export_results)

    @app.callback(
        Output("store-generated-gcode", "data"),
        Output("gcode-preview-container", "children"),
        Output("gcode-preview-summary", "children"),
        Output("export-status-message", "children"),
        Input("btn-generate-gcode", "n_clicks"),
        State("store-layers", "data"),
        State("store-stitched-layer-results", "data"),
        State("store-connected-layer-results", "data"),
        State("input-export-layer-count", "value"),
        State("input-export-layer-height", "value"),
        State("input-export-nozzle", "value"),
        State("input-export-filament", "value"),
        State("input-export-flow", "value"),
        State("input-export-print-speed", "value"),
        State("input-export-travel-speed", "value"),
        State("input-export-nozzle-temp", "value"),
        State("input-export-bed-temp", "value"),
        State("input-export-scale", "value"),
        State("input-export-origin-x", "value"),
        State("input-export-origin-y", "value"),
        prevent_initial_call=True,
    )
    def generate_gcode_and_preview(
        n_clicks,
        layers,
        stitched_results,
        connected_results,
        number_of_layers,
        layer_height,
        nozzle_diameter,
        filament_diameter,
        flow,
        print_speed,
        travel_speed,
        nozzle_temperature,
        bed_temperature,
        scale_xy,
        origin_x,
        origin_y,
    ):
        if n_clicks is None:
            return no_update, no_update, no_update, no_update

        export_results = _connected_results_for_export(connected_results, stitched_results)
        if not export_results:
            placeholder = dcc.Markdown("Run Step 3 tiling first.")
            return no_update, placeholder, "", "No connected or stitched layer results are available yet."

        export_param_map = {
            "number_of_layers": number_of_layers,
            "layer_height": layer_height,
            "nozzle_diameter": nozzle_diameter,
            "filament_diameter": filament_diameter,
            "flow": flow,
            "print_speed": print_speed,
            "travel_speed": travel_speed,
            "nozzle_temperature": nozzle_temperature,
            "bed_temperature": bed_temperature,
            "scale_xy": scale_xy,
            "origin_x": origin_x,
            "origin_y": origin_y,
        }
        print("[tab_4] Generate G-code parameters:", export_param_map)

        missing_fields = [
            field_name
            for field_name in (
                "number_of_layers",
                "layer_height",
                "nozzle_diameter",
                "filament_diameter",
                "flow",
                "print_speed",
                "travel_speed",
                "nozzle_temperature",
                "bed_temperature",
                "scale_xy",
            )
            if export_param_map[field_name] is None
        ]
        if missing_fields:
            print("[tab_4] Missing required export parameters:", missing_fields)
            placeholder = dcc.Markdown("Fill in all export parameters first.")
            return (
                no_update,
                placeholder,
                "",
                "All export parameters must be provided. Missing: "
                + ", ".join(missing_fields),
            )

        settings = ExportSettings(
            number_of_layers=int(number_of_layers),
            layer_height=float(layer_height),
            nozzle_diameter=float(nozzle_diameter),
            filament_diameter=float(filament_diameter),
            flow=float(flow),
            print_speed=float(print_speed),
            travel_speed=float(travel_speed),
            nozzle_temperature=float(nozzle_temperature),
            bed_temperature=float(bed_temperature),
            scale_xy=float(scale_xy),
            origin_x=float(origin_x or 0.0),
            origin_y=float(origin_y or 0.0),
        )

        if settings.number_of_layers < 1:
            placeholder = dcc.Markdown("Number of layers must be at least 1.")
            return no_update, placeholder, "", "Number of layers must be at least 1."

        layer_sequence = build_repeating_layer_sequence(export_results, layers or [], settings.number_of_layers)
        if not layer_sequence:
            placeholder = dcc.Markdown("No export-ready layer cycle is available.")
            return no_update, placeholder, "", "No export-ready layer cycle is available."

        try:
            steps = build_fullcontrol_steps(layer_sequence, settings)
            gcode_text = generate_fullcontrol_gcode(steps, settings)
            plot_data = generate_fullcontrol_plot_data(steps)
        except ValueError as exc:
            placeholder = dcc.Markdown("The selected layer cycle is not export-ready yet.")
            return no_update, placeholder, "", str(exc)

        preview = dcc.Graph(
            figure=create_fullcontrol_plot_figure(
                plot_data,
                title="FullControl G-code Preview",
                extrusion_width=settings.nozzle_diameter * settings.flow,
                layer_height=settings.layer_height,
            ),
            config={"responsive": True, "displayModeBar": True, "displaylogo": False},
            style={"height": "100%"},
        )

        sequence_names = [layer["layer_name"] for layer in layer_sequence]
        preview_summary = (
            f"Generated {len(layer_sequence)} print layers. "
            f"Cycle preview: {' -> '.join(sequence_names[:12])}"
            + (" -> ..." if len(sequence_names) > 12 else "")
        )
        status = (
            f"G-code generated successfully with {settings.number_of_layers} total layers, "
            f"flow {settings.flow:.2f}, scale {settings.scale_xy:.2f}, "
            f"and origin ({settings.origin_x:.2f}, {settings.origin_y:.2f})."
        )
        return gcode_text, preview, preview_summary, status

    @app.callback(
        Output("download-generated-gcode", "data"),
        Input("btn-download-gcode", "n_clicks"),
        State("store-generated-gcode", "data"),
        prevent_initial_call=True,
    )
    def download_generated_gcode(n_clicks, gcode_text):
        if n_clicks is None or not gcode_text:
            return no_update

        return dcc.send_string(gcode_text, "lattice_print.gcode")
