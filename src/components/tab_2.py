"""Loop catalog view for Step 2."""

from dash import html


TAB_2 = html.Div(
    [
        html.H4("Loop Catalog"),
        html.P(
            "Inspect the discovered loops, review their backend-generated path "
            "descriptions, and preview one loop at a time before building layers."
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
                html.Div(id="loop-catalog-container", className="loop-list-container"),
            ],
            className="loop-catalog-section",
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
