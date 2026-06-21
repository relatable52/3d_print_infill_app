from dash import html, dcc

from components.tab_1 import TAB_1

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
        dcc.Store(id='store-active-layer-loop-ids'),  # Stores the current layer loop selection
        dcc.Store(id='store-layer-validation'),  # Stores compatibility results for the current layer
        dcc.Store(id='store-tiling-config')  # Stores user-defined tiling parameters
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
            dcc.Tab(label="2. Loop Discovery", value="step-2", disabled=True, className="slicer-tab", children=[
                html.Div([
                    html.H4("Loop Catalog"),
                    html.P("Discover valid non-zero-winding loops and choose which ones belong to the active layer."),
                    html.Div("Loop discovery, metadata, and layer selection controls will go here.", className="placeholder-text"),
                    
                    html.Button("Proceed to Grid Tiling ➔", id="btn-next-step-2", className="btn-next")
                ], className="tab-content")
            ]),
            
            # STEP 3: TILING & STITCHING
            dcc.Tab(label="3. Layer Tiling", value="step-3", disabled=True, className="slicer-tab", children=[
                html.Div([
                    html.H4("Layer Tiling Preview"),
                    html.Label("Rows: "),
                    dcc.Input(id="input-rows", type="number", value=3, min=1, className="number-input"),
                    
                    html.Label("Columns: "),
                    dcc.Input(id="input-cols", type="number", value=4, min=1, className="number-input"),
                    
                    html.Div("The tiled layer preview and path stitching summary will go here.", className="placeholder-text"),
                    
                    html.Button("Proceed to G-Code Export ➔", id="btn-next-step-3", className="btn-next")
                ], className="tab-content")
            ]),
            
            # STEP 4: G-CODE GENERATION
            dcc.Tab(label="4. Export G-Code", value="step-4", disabled=True, className="slicer-tab", children=[
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
