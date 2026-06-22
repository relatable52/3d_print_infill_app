"""G-code export view for Step 4."""

from dash import dcc, html


TAB_4 = html.Div(
    [
        html.H4("G-Code Generation"),
        html.P(
            "Repeat the designed layer cycle for the requested layer count, "
            "preview the FullControl plot, and export the generated G-code."
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H5("Export Parameters"),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Label("Number of Layers"),
                                        dcc.Input(id="input-export-layer-count", type="number", value=9, min=1, step=1, className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Layer Height"),
                                        dcc.Input(id="input-export-layer-height", type="number", value=0.2, min=0.01, step=0.01, className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Nozzle Diameter"),
                                        dcc.Input(id="input-export-nozzle", type="number", value=0.4, min=0.01, step=0.01, className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Filament Diameter"),
                                        dcc.Input(id="input-export-filament", type="number", value=1.75, min=0.1, step=0.01, className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Flow"),
                                        dcc.Input(id="input-export-flow", type="number", value=1.0, min=0.1, step="any", className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Print Speed"),
                                        dcc.Input(id="input-export-print-speed", type="number", value=1000, min=1, step="any", className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Travel Speed"),
                                        dcc.Input(id="input-export-travel-speed", type="number", value=8000, min=1, step="any", className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Nozzle Temperature"),
                                        dcc.Input(id="input-export-nozzle-temp", type="number", value=210, min=0, step=1, className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Bed Temperature"),
                                        dcc.Input(id="input-export-bed-temp", type="number", value=60, min=0, step=1, className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Scale XY"),
                                        dcc.Input(id="input-export-scale", type="number", value=1.0, min=0.01, step="any", className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Origin X"),
                                        dcc.Input(id="input-export-origin-x", type="number", value=0.0, step="any", className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                                html.Div(
                                    [
                                        html.Label("Origin Y"),
                                        dcc.Input(id="input-export-origin-y", type="number", value=0.0, step="any", className="number-input"),
                                    ],
                                    className="tiling-control-group",
                                ),
                            ],
                            className="export-parameter-grid",
                        ),
                        html.Div(id="export-cycle-summary", className="loop-summary"),
                        html.Div(id="export-status-message", className="layer-message"),
                        html.Div(
                            [
                                html.Button("Generate G-code and Preview", id="btn-generate-gcode", className="layer-action-btn"),
                                html.Button("Download G-code", id="btn-download-gcode", className="btn-download export-download-btn"),
                            ],
                            className="export-action-row",
                        ),
                        dcc.Download(id="download-generated-gcode"),
                    ],
                    className="export-side-panel",
                ),
                html.Div(
                    [
                        html.H5("FullControl Preview"),
                        html.Div(id="gcode-preview-summary", className="loop-summary"),
                        html.Div(id="gcode-preview-container", className="visual-container gcode-visual-container"),
                    ],
                    className="preview-panel",
                ),
            ],
            className="export-grid",
        ),
    ],
    className="tab-content",
)
