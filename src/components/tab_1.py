"""Visualize the imported unit cell and periodic multigraph."""

from dash import html


TAB_1 = html.Div(
    [
        html.H4("Unit Cell Import Preview"),
        html.P(
            "Inspect the imported DXF graph and its abstract periodic multigraph "
            "side by side before moving on to loop discovery."
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H5("Original DXF Graph"),
                        html.Div(id="dxf-preview-container", className="visual-container"),
                    ],
                    className="preview-panel",
                ),
                html.Div(
                    [
                        html.H5("Periodic Multigraph"),
                        html.Div(id="periodic-preview-container", className="visual-container"),
                    ],
                    className="preview-panel",
                ),
            ],
            className="preview-grid",
        ),
        html.Div(
            [
                html.Button("Next", id="btn-next-step-1", className="btn-next"),
            ],
            style={"marginTop": "20px", "display": "flex", "justifyContent": "flex-end"},
        ),
    ],
    className="tab-content",
)
