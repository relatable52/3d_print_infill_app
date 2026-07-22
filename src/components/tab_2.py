"""Loop catalog view for Step 2."""

from dash import html, dcc

TAB_2 = html.Div(
    [
        html.H4("Loop Catalog"),
        html.P(
            "Inspect the discovered loops, review their backend-generated path "
            "descriptions, and build the active layer one loop at a time."
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H5("Original Physical Graph"),
                        html.Div(id="loop-source-graph-container", className="visual-container"),
                    ],
                    className="preview-panel",
                ),
                html.Div(
                    [
                        html.H5("Selected Loop Preview"),
                        html.Div(id="selected-loop-preview-container", className="visual-container"),
                    ],
                    className="preview-panel",
                ),
            ],
            className="preview-grid",
        ),
        html.Div(
            [
                html.H5("Discovered Loops"),
                html.Div(id="loop-catalog-summary", className="loop-summary"),
                html.Div(id="current-layer-summary", className="layer-summary"),
                html.Div(id="layer-validation-message", className="layer-message"),
                html.Div(id="loop-catalog-container", className="loop-list-container"),
            ],
            className="loop-catalog-section",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H5("Layers"),
                        html.Div(id="layer-manager-summary", className="loop-summary"),
                        html.Div(
                            [
                                html.Button("Add Layer", id="btn-add-layer", className="layer-action-btn"),
                                html.Button("Remove Layer", id="btn-remove-layer", className="layer-action-btn is-danger"),
                            ],
                            className="layer-action-row",
                        ),
                        html.Div(
                            [
                                dcc.Input(
                                    id="input-auto-layers",
                                    type="number",
                                    placeholder="Total Layers",
                                    min=1,
                                    step=1,
                                    style={"width": "120px", "marginRight": "10px"}
                                ),
                                html.Button(
                                    "Find Solutions", 
                                    id="btn-auto-generate", 
                                    className="layer-action-btn"
                                ),
                            ],
                            style={"marginTop": "15px", "display": "flex", "alignItems": "center"}
                        ),
                        # NEW UI: Hidden by default, shows up when solutions are found
                        html.Div(
                            [
                                dcc.Dropdown(
                                    id="dropdown-auto-solutions",
                                    placeholder="Select a valid sequence...",
                                    style={"width": "250px", "marginRight": "10px"}
                                ),
                                html.Button(
                                    "Apply Selected", 
                                    id="btn-apply-solution", 
                                    className="layer-action-btn is-success",
                                    disabled=True
                                ),
                            ],
                            id="auto-solution-selector-container",
                            style={"marginTop": "10px", "marginBottom": "15px", "display": "none", "alignItems": "center"}
                        ),
                        html.Div(id="layer-manager-container", className="loop-list-container"),
                    ],
                    className="preview-panel",
                ),
                html.Div(
                    [
                        html.H5("Stacked 3D Preview"),
                        html.Div(id="stacked-layer-preview-container", className="visual-container"),
                    ],
                    className="preview-panel",
                ),
            ],
            className="preview-grid bottom-preview-grid",
        ),
        html.Div(
            [
                html.Button("Next", id="btn-next-step-2", className="btn-next"),
            ],
            style={"marginTop": "20px", "display": "flex", "justifyContent": "flex-end"},
        ),
    ],
    className="tab-content",
)
