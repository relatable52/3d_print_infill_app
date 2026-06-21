import base64

from dash import Input, Output, State, dash, html, dcc
import networkx as nx

from src.core.dxf_parser import parse_dxf_to_graph
from src.core.periodic_graph import create_periodic_multigraph
from src.core.plot_utils import (
    create_dxf_preview_figure,
    create_periodic_multigraph_figure,
)

def register_upload_callbacks(app):
    """
    
    """
    # Callback to handle file upload and parsing
    @app.callback(
        Output('upload-status-output', 'children'),
        Output('upload-area-text', 'children'),
        Output('store-graph-data', 'data'),
        Output('store-graph-dimensions', 'data'),
        Output('btn-next-step-1', 'disabled'),
        Input('upload-dxf', 'contents'),
        State('upload-dxf', 'filename')
    )
    def handle_file_upload(contents, filename):
        if contents is None:
            return "No file uploaded yet.", "Drag and Drop or Select .DXF File", None, None, True
        
        # 1. Decode the uploaded file
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # 2. Parse the DXF and extract graph data
        graph_data, width, height = parse_dxf_to_graph(decoded)

        graph_data_json = nx.node_link_data(graph_data) if graph_data else None

        if graph_data_json is not None:
            status_message = f"Successfully parsed '{filename}'. Graph has {len(graph_data.nodes)} nodes and {len(graph_data.edges)} edges."
            upload_area_text = f"File: {filename}"
        else:
            status_message = f"Error parsing '{filename}'. Please ensure it's a valid DXF format."
            upload_area_text = "Invalid file format. Please upload a valid .DXF file."

            return status_message, upload_area_text, None, None, True

        return status_message, upload_area_text, graph_data_json, (width, height), False
    
    # Listen to Store and Render Plotly graph in Tab 1
    @app.callback(
        Output('dxf-preview-container', 'children'),
        Output('periodic-preview-container', 'children'),
        Input('store-graph-data', 'data'),
        State('store-graph-dimensions', 'data')
    )
    def render_graph_from_store(graph_data_json, dimensions):
        # If no graph data, show placeholder
        if graph_data_json is None or dimensions is None:
            placeholder = html.Div("Visualization will go here.", className="placeholder-text")
            return placeholder, placeholder
        
        try:
            # Unpack graph data from JSON
            graph = nx.node_link_graph(graph_data_json)
            width, height = dimensions

            dxf_fig = create_dxf_preview_figure(graph)
            periodic_graph, _ = create_periodic_multigraph(graph, width, height)
            periodic_fig = create_periodic_multigraph_figure(periodic_graph, width, height)

            config = {
                'responsive': True,
                'displayModeBar': True,
                'displaylogo': False,
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': 'graph_preview',
                    'height': 800,
                    'width': 1000,
                    'scale': 2
                },
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            }
            
            return (
                dcc.Graph(figure=dxf_fig, config=config),
                dcc.Graph(figure=periodic_fig, config=config),
            )
        except Exception as e:
            print(f"Error rendering graph: {e}")
            error = html.Div("Error rendering graph.", className="error-text")
            return error, error

def register_next_step_callbacks(app):
    @app.callback(
        Output('processing-tabs', 'value'),
        Output('tab-step-2', 'disabled'),
        Input('btn-next-step-1', 'n_clicks'),
        State('processing-tabs', 'value'),
    )
    def go_to_next_step(n_clicks, current_tab):
        if n_clicks is None:
            return current_tab, dash.no_update

        return 'step-2', False

    
def register_tab_1_callbacks(app):
    register_upload_callbacks(app)
    register_next_step_callbacks(app)
