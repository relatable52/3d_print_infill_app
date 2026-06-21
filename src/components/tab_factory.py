from dash import html, dcc

def create_base_tab_content(title, description, visual_container_id, back_btn_id=None, next_btn_id=None):
    """
    A reusable template for all processing steps.
    Includes a header, a main visualization area, optional extra controls, and navigation buttons.
    """
    # 1. Setup Navigation Buttons
    nav_buttons = []
    if back_btn_id:
        nav_buttons.append(html.Button("Back", id=back_btn_id, className="btn-back"))
    if next_btn_id:
        nav_buttons.append(html.Button("Next", id=next_btn_id, className="btn-next"))

    # 2. Setup Visualization Container
    visual_container = html.Div(id=visual_container_id, className="visual-container")
   
    # 3. Assemble Layout
    return html.Div([
        html.H4(title),
        html.P(description),

        # Standardized Visualization Area
        visual_container,
        
        # Navigation Footer
        html.Div(nav_buttons, style={"marginTop": "20px", "display": "flex", "justifyContent": "space-between" if back_btn_id and next_btn_id else "flex-end"})
        
    ], className="tab-content")