from dash import html, dcc

from src.components.tab_1 import TAB_1
from src.components.tab_2 import TAB_2
from src.components.tab_3 import TAB_3

def create_upload_section():
    """Creates a basic drag-and-drop upload zone."""
    return html.Div([
        html.H3("Import Unit Cell"),
        dcc.Upload(
            id='upload-dxf',
            children=html.Div(['Drag and Drop or Select .DXF File'], id='upload-area-text'),
            className="upload-area",
            multiple=False
        ),
        html.Div(id='upload-status-output', className="status-text")
    ], className="upload-container")

def create_dcc_stores():
    """Centralized storage for app state."""
    return html.Div([
        dcc.Store(id='store-graph-data'),  # Stores the graph representation of the DXF
        dcc.Store(id='store-graph-dimensions'),  # Stores width and height for scaling
        dcc.Store(id='store-loop-catalog'),  # Stores discovered non-zero-winding loops
        dcc.Store(id='store-preview-loop-id'),  # Stores the loop shown in the preview panel
        dcc.Store(id='store-loop-preview-action'),  # Stores the latest preview button action
        dcc.Store(id='store-loop-layer-action'),  # Stores the latest add/remove loop action
        dcc.Store(id='store-layers'),  # Stores all layer records for Step 2 editing
        dcc.Store(id='store-active-layer-id'),  # Stores which layer is currently being edited
        dcc.Store(id='store-tiling-config'),  # Stores user-defined tiling parameters
        dcc.Store(id='store-stitched-layer-results'),  # Stores Step 3 tiled/stitched results for all layers
        dcc.Store(id='store-connected-layer-results')  # Stores Step 3 chain-connection results for all layers
    ])

def create_processing_tabs():
    """Creates the standard step-by-step processing tabs."""
    return dcc.Tabs(
        id="processing-tabs", 
        value="step-1", 
        children=[
            # STEP 1: PARSE & PREVIEW
            dcc.Tab(
                label="1. DXF Preview", 
                value="step-1", 
                className="slicer-tab",
                id="tab-step-1", 
                children=[
                    TAB_1
                ]
            ),
            
            # STEP 2: LOOP DISCOVERY
            dcc.Tab(label="2. Loop Discovery", value="step-2", disabled=True, className="slicer-tab", id="tab-step-2", children=[
                TAB_2
            ]),
            
            # STEP 3: TILING & STITCHING
            dcc.Tab(label="3. Layer Tiling", value="step-3", disabled=True, className="slicer-tab", id="tab-step-3", children=[
                TAB_3
            ]),
            
            # STEP 4: G-CODE GENERATION
            dcc.Tab(label="4. Export G-Code", value="step-4", disabled=True, className="slicer-tab", id="tab-step-4", children=[
                html.Div([
                    html.H4("Print Settings & Export"),
                    html.P("Configure nozzle temperature, extrusion rate, and speed."),
                    
                    html.Button("Download G-Code", id="btn-download-gcode", className="btn-download")
                ], className="tab-content")
            ]),
        ]
    )

def serve_app_layout():
    """Combines everything into the final page layout."""
    return html.Div([
        create_upload_section(),
        html.Br(),
        create_processing_tabs(),
        create_dcc_stores(),
    ], className="main-app-container")
