"""Layer tiling view for Step 3."""

from dash import dcc, html


TAB_3 = html.Div(
    [
        html.H4("Layer Tiling"),
        html.P(
            "Set one global grid size for all layers, run tiling and stitching once, "
            "then choose which stitched layer to inspect."
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Rows (m)"),
                        dcc.Input(
                            id="input-tiling-rows",
                            type="number",
                            value=3,
                            min=1,
                            step=1,
                            className="number-input",
                        ),
                    ],
                    className="tiling-control-group",
                ),
                html.Div(
                    [
                        html.Label("Columns (n)"),
                        dcc.Input(
                            id="input-tiling-cols",
                            type="number",
                            value=4,
                            min=1,
                            step=1,
                            className="number-input",
                        ),
                    ],
                    className="tiling-control-group",
                ),
                html.Div(
                    [
                        html.Button("Tile and Stitch", id="btn-run-tiling", className="layer-action-btn"),
                    ],
                    className="tiling-control-group tiling-action-group",
                ),
            ],
            className="tiling-control-row",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Connection Mode"),
                        dcc.Dropdown(
                            id="connection-mode-dropdown",
                            options=[
                                {"label": "Closest Sweep", "value": "closest"},
                                {"label": "Sweep Avoid Crossings", "value": "avoid_intersection"},
                                {"label": "Closest Sweep + Parallel Filter", "value": "parallel"},
                            ],
                            value="closest",
                            clearable=False,
                            className="tiling-dropdown",
                        ),
                    ],
                    className="tiling-control-group",
                ),
                html.Div(
                    [
                        html.Button("Connect Chains", id="btn-connect-chains", className="layer-action-btn"),
                    ],
                    className="tiling-control-group tiling-action-group",
                ),
            ],
            className="tiling-control-row tiling-control-row-secondary",
        ),
        html.Div(
            [
                html.Label("Display Layer"),
                dcc.Dropdown(
                    id="tiling-layer-dropdown",
                    placeholder="Select a stitched layer to display",
                    className="tiling-dropdown",
                    clearable=False,
                ),
            ],
            className="tiling-control-group",
        ),
        html.Div(id="tiling-status-message", className="layer-message"),
        html.Div(id="tiling-preview-summary", className="loop-summary"),
        html.Div(id="tiling-preview-container", className="visual-container"),
        html.Div(
            [
                html.Button("Proceed to G-Code Export", id="btn-next-step-3", className="btn-next"),
            ],
            style={"marginTop": "20px", "display": "flex", "justifyContent": "flex-end"},
        ),
    ],
    className="tab-content",
)
