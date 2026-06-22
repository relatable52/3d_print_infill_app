import dash
from src.components.main_layout import serve_app_layout
from src.callbacks import register_callbacks

# Initialize the Dash app without external styling libraries
app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.title = "Lattice Path Designer"

# Set the layout
app.layout = serve_app_layout()

# Register callbacks
register_callbacks(app)

if __name__ == '__main__':
    app.run(debug=False, port=8050)
