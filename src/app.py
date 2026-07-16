import dash
import os
from dotenv import load_dotenv
from src.components.main_layout import serve_app_layout
from src.callbacks import register_callbacks


load_dotenv()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Initialize the Dash app without external styling libraries
app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.title = "Lattice Path Designer"

# Set the layout
app.layout = serve_app_layout()

# Register callbacks
register_callbacks(app)

if __name__ == '__main__':
    app.run(
        debug=_env_flag("DEBUG"),
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
    )
