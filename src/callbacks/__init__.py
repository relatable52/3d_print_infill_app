from src.callbacks.tab_1_callbacks import register_tab_1_callbacks
from src.callbacks.tab_2_callbacks import register_tab_2_callbacks
from src.callbacks.tab_3_callbacks import register_tab_3_callbacks
from src.callbacks.tab_4_callbacks import register_tab_4_callbacks

def register_callbacks(app):
    """Centralized function to register all callbacks."""
    register_tab_1_callbacks(app)
    register_tab_2_callbacks(app)
    register_tab_3_callbacks(app)
    register_tab_4_callbacks(app)
