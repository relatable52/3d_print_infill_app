import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import plotly.colors as pcolors
import networkx as nx
from fullcontrol.visualize.tube_mesh import FlowTubeMesh


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[index:index + 2], 16) for index in (0, 2, 4))


def _rgb_to_hex(rgb_color: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb_color)


def _interpolate_hex_color(start_hex: str, end_hex: str, t: float) -> str:
    start_rgb = _hex_to_rgb(start_hex)
    end_rgb = _hex_to_rgb(end_hex)
    interpolated = tuple(
        round(start_channel + (end_channel - start_channel) * t)
        for start_channel, end_channel in zip(start_rgb, end_rgb)
    )
    return _rgb_to_hex(interpolated)


def _node_sort_key(graph: nx.Graph, node_id) -> tuple[float, float, str]:
    """Matches the deterministic node sorting from the publication script."""
    x, y = graph.nodes[node_id]["pos"]
    return float(x), float(y), str(node_id)


def _pick_path_start_node(graph: nx.Graph, added_edges: list[tuple[str, str]]) -> str:
    """Finds the best endpoint to start the sequential print path."""
    endpoints = [node_id for node_id, degree in graph.degree() if degree == 1]
    if not endpoints:
        return min(graph.nodes(), key=lambda node_id: _node_sort_key(graph, node_id))

    if added_edges:
        anchor_nodes = {str(added_edges[0][0]), str(added_edges[0][1])}
        anchored_endpoints = [node_id for node_id in endpoints if str(node_id) in anchor_nodes]
        if anchored_endpoints:
            return min(anchored_endpoints, key=lambda node_id: _node_sort_key(graph, node_id))

    return min(endpoints, key=lambda node_id: _node_sort_key(graph, node_id))


def _build_ordered_node_walk(graph: nx.Graph, added_edges: list[tuple[str, str]]) -> list[str]:
    """Generates a continuous sequence of nodes to render the gradient Plotly line."""
    if graph.number_of_edges() == 0:
        return []

    start_node = _pick_path_start_node(graph, added_edges)
    path_nodes = [start_node]
    visited_edges = set()
    current_node = start_node
    previous_node = None

    while True:
        neighbors = sorted(graph.neighbors(current_node), key=lambda n: _node_sort_key(graph, n))
        candidate_neighbors = [n for n in neighbors if n != previous_node]
        
        next_node = None
        for neighbor in candidate_neighbors:
            key = tuple(sorted((str(current_node), str(neighbor))))
            if key not in visited_edges:
                next_node = neighbor
                break
        
        if next_node is None:
            break

        visited_edges.add(tuple(sorted((str(current_node), str(next_node)))))
        path_nodes.append(next_node)
        previous_node, current_node = current_node, next_node

    return path_nodes


def _build_fullcontrol_path_mesh(
    path,
    colors_now: list[str],
    extrusion_width: float | None,
    layer_height: float | None,
    sides: int = 8,
) -> go.Mesh3d | None:
    path_points = np.array([path.xvals, path.yvals, path.zvals]).T
    if len(path_points) < 2:
        return None

    good_points = np.ones(len(path_points), dtype=bool)
    duplicate_steps = np.all(np.diff(path_points, axis=0) == 0, axis=1)
    if np.any(duplicate_steps):
        good_points[1:] = ~duplicate_steps
        colors_now = np.array(colors_now, dtype=object)[good_points].tolist()

    path_points = path_points[good_points]
    if len(path_points) < 2:
        return None

    widths = getattr(path, "widths", None)
    if widths:
        widths = np.array(widths)[good_points]
    else:
        widths = extrusion_width if extrusion_width is not None else 0.4

    heights = getattr(path, "heights", None)
    if heights:
        heights = np.array(heights)[good_points]
    else:
        heights = layer_height if layer_height is not None else 0.2

    mesh = FlowTubeMesh(
        path_points,
        widths=widths,
        heights=heights,
        sides=sides,
        capped=False,
        inplace_path=True,
        rounding_strength=0.4,
        flat_sides=False,
    )
    return mesh.to_Mesh3d(colors=colors_now, hoverinfo="none", flatshading=True, showlegend=False)

def _get_graph_bounds(graph: nx.Graph) -> tuple[float, float, float, float]:
    all_x = []
    all_y = []

    for node in graph.nodes():
        x, y = graph.nodes[node]["pos"]
        all_x.append(x)
        all_y.append(y)

    return min(all_x), max(all_x), min(all_y), max(all_y)


def _create_boundary_trace(min_x: float, max_x: float, min_y: float, max_y: float) -> go.Scatter:
    boundary_x = [min_x, max_x, max_x, min_x, min_x]
    boundary_y = [min_y, min_y, max_y, max_y, min_y]

    return go.Scatter(
        x=boundary_x,
        y=boundary_y,
        line=dict(width=2, color="black", dash="dash"),
        hoverinfo="none",
        mode="lines",
        name="Boundary",
    )


def _create_base_figure(
    graph: nx.Graph,
    title: str,
    traces: list,
    bounds: tuple[float, float, float, float] | None = None,
) -> go.Figure:
    min_x, max_x, min_y, max_y = bounds or _get_graph_bounds(graph)
    boundary_trace = _create_boundary_trace(min_x, max_x, min_y, max_y)

    fig = go.Figure(
        data=[boundary_trace, *traces],
        layout=go.Layout(
            title=title,
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(
                showgrid=True,
                zeroline=False,
                showticklabels=True,
                scaleanchor="y",
                scaleratio=1,
                gridwidth=1,
                gridcolor="lightgray",
            ),
            yaxis=dict(
                showgrid=True,
                zeroline=False,
                showticklabels=True,
                scaleanchor="x",
                scaleratio=1,
                gridwidth=1,
                gridcolor="lightgray",
            ),
            dragmode="zoom",
        ),
    )

    fig.update_layout(
        xaxis=dict(scaleanchor="y", scaleratio=1),
        yaxis=dict(scaleanchor="x", scaleratio=1),
    )

    return fig


def create_dxf_preview_figure(graph: nx.Graph) -> go.Figure:
    """Creates a Plotly figure to visualize the DXF graph with boundary and axis ticks."""
    if graph is None or len(graph.nodes) == 0:
        return go.Figure()  # Return an empty figure if no graph data

    # Create edge traces
    edge_x = []
    edge_y = []
    for u, v in graph.edges():
        x0, y0 = graph.nodes[u]["pos"]
        x1, y1 = graph.nodes[v]["pos"]
        edge_x.extend([x0, x1, None])  # None separates edges
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=2, color="blue"),
        hoverinfo="none",
        mode="lines",
    )

    # Create node trace
    node_x = []
    node_y = []
    node_text = []
    for node in graph.nodes():
        x, y = graph.nodes[node]["pos"]
        node_x.append(x)
        node_y.append(y)
        node_text.append(f"Node {node}<br>pos=({x:.3f}, {y:.3f})")

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        text=node_text,
        mode="markers",
        hoverinfo="text",
        marker=dict(
            showscale=False,
            color="red",
            size=10,
            line_width=2,
        ),
    )

    return _create_base_figure(
        graph,
        title="DXF Geometry Preview",
        traces=[edge_trace, node_trace],
    )


def create_labeled_physical_graph_figure(graph: nx.Graph, title: str = "Physical Graph") -> go.Figure:
    """Create a physical graph view with always-visible node labels."""
    if graph is None or len(graph.nodes) == 0:
        return go.Figure()

    edge_x = []
    edge_y = []
    for u, v in graph.edges():
        x0, y0 = graph.nodes[u]["pos"]
        x1, y1 = graph.nodes[v]["pos"]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=2, color="#94a3b8"),
        hoverinfo="none",
        mode="lines",
    )

    node_x = []
    node_y = []
    node_hover_text = []
    node_labels = []
    for node in graph.nodes():
        x, y = graph.nodes[node]["pos"]
        node_x.append(x)
        node_y.append(y)
        node_labels.append(str(node))
        node_hover_text.append(f"Node {node}<br>pos=({x:.3f}, {y:.3f})")

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        text=node_labels,
        hovertext=node_hover_text,
        mode="markers+text",
        hoverinfo="text",
        textposition="top center",
        marker=dict(
            showscale=False,
            color="#dc2626",
            size=10,
            line=dict(width=2, color="#0f172a"),
        ),
    )

    return _create_base_figure(
        graph,
        title=title,
        traces=[edge_trace, node_trace],
    )


def create_periodic_multigraph_figure(
    graph: nx.MultiGraph,
    width: float | None = None,
    height: float | None = None,
) -> go.Figure:
    """Create an abstract topology view of the periodic multigraph."""
    if graph is None or len(graph.nodes) == 0:
        return go.Figure()

    edge_traces = []
    pair_counts = {}
    pair_offsets = {}

    for u, v, key, data in graph.edges(keys=True, data=True):
        pair = tuple(sorted((u, v)))
        pair_counts[pair] = pair_counts.get(pair, 0) + 1

    for u, v, key, data in graph.edges(keys=True, data=True):
        pair = tuple(sorted((u, v)))
        pair_offsets[pair] = pair_offsets.get(pair, 0) + 1

        x0, y0 = graph.nodes[u]["pos"]
        x1, y1 = graph.nodes[v]["pos"]
        total_edges = pair_counts[pair]
        edge_index = pair_offsets[pair] - 1
        offset_level = edge_index - (total_edges - 1) / 2

        dx = x1 - x0
        dy = y1 - y0
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length == 0:
            normal_x, normal_y = 0.0, 0.0
        else:
            normal_x = -dy / length
            normal_y = dx / length

        curvature = 0.35 * offset_level
        ctrl_x = (x0 + x1) / 2 + normal_x * curvature
        ctrl_y = (y0 + y1) / 2 + normal_y * curvature

        path_x = [x0, ctrl_x, x1]
        path_y = [y0, ctrl_y, y1]
        hover_text = (
            f"Periodic edge: {u} -> {v}"
            f"<br>Original edge: {data['original_u']} -> {data['original_v']}"
            f"<br>Edge key: {key}"
        )

        edge_traces.append(
            go.Scatter(
                x=path_x,
                y=path_y,
                mode="lines",
                line=dict(width=2, color="#0f766e"),
                hoverinfo="text",
                text=[hover_text, hover_text, hover_text],
            )
        )

    node_x = []
    node_y = []
    node_text = []
    node_labels = []

    for node_id, data in graph.nodes(data=True):
        x, y = data["pos"]
        node_x.append(x)
        node_y.append(y)
        node_labels.append(str(node_id))
        merged_nodes = ", ".join(map(str, data.get("original_nodes", (node_id,))))
        node_text.append(
            f"Periodic node: {node_id}<br>"
            f"Original nodes: [{merged_nodes}]<br>"
            f"pos=({x:.3f}, {y:.3f})"
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        text=node_text,
        mode="markers+text",
        hoverinfo="text",
        textposition="top center",
        textfont=dict(size=11, color="#134e4a"),
        texttemplate="%{customdata}",
        customdata=node_labels,
        marker=dict(
            showscale=False,
            color="#14b8a6",
            size=12,
            line=dict(width=2, color="#0f172a"),
        ),
    )

    bounds = None
    if width is not None and height is not None:
        bounds = (0.0, width, 0.0, height)

    return _create_base_figure(
        graph,
        title="Periodic Multigraph Preview",
        traces=[*edge_traces, node_trace],
        bounds=bounds,
    )


def create_loop_preview_figure(
    original_graph: nx.Graph,
    physical_edges: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    loop_id: str | None = None,
) -> go.Figure:
    """Create a highlighted loop preview on top of the physical graph."""
    if original_graph is None or len(original_graph.nodes) == 0:
        return go.Figure()

    base_fig = create_labeled_physical_graph_figure(
        original_graph,
        title=f"Loop Preview{f' - {loop_id}' if loop_id else ''}",
    )

    edge_x = []
    edge_y = []
    for start, end in physical_edges:
        x0, y0 = original_graph.nodes[start]["pos"]
        x1, y1 = original_graph.nodes[end]["pos"]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

        base_fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.2,
            arrowwidth=2,
            arrowcolor="#2563eb",
            opacity=0.95,
        )

    highlighted_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=4, color="#2563eb"),
        hoverinfo="none",
        mode="lines",
    )

    base_fig.add_trace(highlighted_trace)
    return base_fig


def create_layer_graph_preview_figure(
    original_graph: nx.Graph,
    layer_graph: nx.Graph,
    layer_name: str | None = None,
) -> go.Figure:
    """Create a merged layer preview on top of the original unit-cell graph."""
    if original_graph is None or len(original_graph.nodes) == 0:
        return go.Figure()

    title = "Active Layer Preview"
    if layer_name:
        title = f"{title} - {layer_name}"

    base_fig = create_labeled_physical_graph_figure(original_graph, title=title)

    if layer_graph is None or len(layer_graph.edges) == 0:
        base_fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            text="No loops added to this layer yet.",
            showarrow=False,
            font=dict(size=14, color="#64748b"),
            bgcolor="rgba(255,255,255,0.85)",
        )
        return base_fig

    edge_x = []
    edge_y = []
    for start, end in layer_graph.edges():
        x0, y0 = original_graph.nodes[start]["pos"]
        x1, y1 = original_graph.nodes[end]["pos"]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    highlighted_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=5, color="#0f766e"),
        hoverinfo="none",
        mode="lines",
        name="Active Layer",
    )
    base_fig.add_trace(highlighted_trace)
    return base_fig


def create_stacked_layer_3d_figure(
    layers: list[dict] | None,
    active_layer_id: str | None = None,
    z_spacing: float = 1.0,
) -> go.Figure:
    """Create a simple stacked 3D line preview for all non-empty layers."""
    fig = go.Figure()

    if not layers:
        fig.update_layout(
            title="Stacked Layer Preview",
            annotations=[
                dict(
                    text="No layers available yet.",
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=14, color="#64748b"),
                )
            ],
            margin=dict(l=0, r=0, b=0, t=40),
        )
        return fig

    has_visible_trace = False
    layer_count = len(layers)

    for index, layer in enumerate(layers):
        layer_graph_data = layer.get("layer_graph")
        if not layer_graph_data:
            continue

        layer_graph = nx.node_link_graph(layer_graph_data)
        if len(layer_graph.edges) == 0:
            continue

        has_visible_trace = True
        z_level = index * z_spacing
        t = 0.0 if layer_count <= 1 else index / (layer_count - 1)
        color = _interpolate_hex_color("#1d4ed8", "#ea580c", t)
        is_active = layer.get("layer_id") == active_layer_id

        edge_x = []
        edge_y = []
        edge_z = []

        for start, end in layer_graph.edges():
            x0, y0 = layer_graph.nodes[start]["pos"]
            x1, y1 = layer_graph.nodes[end]["pos"]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_z.extend([z_level, z_level, None])

        fig.add_trace(
            go.Scatter3d(
                x=edge_x,
                y=edge_y,
                z=edge_z,
                mode="lines",
                line=dict(
                    width=8 if is_active else 5,
                    color=color,
                ),
                hoverinfo="text",
                text=[layer["name"]] * len(edge_x),
                name=layer["name"],
                opacity=1.0 if is_active else 0.78,
            )
        )

    if not has_visible_trace:
        fig.update_layout(
            title="Stacked Layer Preview",
            annotations=[
                dict(
                    text="Add loops to one or more layers to see the 3D stack.",
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=14, color="#64748b"),
                )
            ],
            margin=dict(l=0, r=0, b=0, t=40),
        )
        return fig

    fig.update_layout(
        title="Stacked Layer Preview",
        margin=dict(l=0, r=0, b=0, t=40),
        scene=dict(
            xaxis=dict(title="X", backgroundcolor="#f8fafc"),
            yaxis=dict(title="Y", backgroundcolor="#f8fafc"),
            zaxis=dict(title="Layer Z", backgroundcolor="#f8fafc"),
            aspectmode="data",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
    )
    return fig


def create_tiled_component_figure(
    tiled_graph: nx.Graph,
    width: float,
    height: float,
    rows: int,
    cols: int,
    title: str = "Tiled Layer Components",
) -> go.Figure:
    """Create a geometric 2D view with publication-style thick outlines and distinct colors."""
    if tiled_graph is None or len(tiled_graph.nodes) == 0:
        return go.Figure()

    boundary_trace = _create_boundary_trace(0.0, width * cols, 0.0, height * rows)
    fig = go.Figure(data=[boundary_trace])

    components = list(nx.connected_components(tiled_graph))
    
    # Use Plotly's default distinct color sequence
    colors = px.colors.qualitative.Plotly 

    for component_index, component_nodes in enumerate(components):
        component_graph = tiled_graph.subgraph(component_nodes)
        color = colors[component_index % len(colors)]

        edge_x, edge_y = [], []
        for start, end in component_graph.edges():
            x0, y0 = tiled_graph.nodes[start]["pos"]
            x1, y1 = tiled_graph.nodes[end]["pos"]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        node_x, node_y, node_text = [], [], []
        for node_id in component_graph.nodes():
            x, y = tiled_graph.nodes[node_id]["pos"]
            node_x.append(x)
            node_y.append(y)
            node_text.append(str(node_id))

        # 1. Thick black outline underneath (matches matplotlib linewidth=3.8)
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines", 
            line=dict(width=7, color="black"), 
            hoverinfo="none", showlegend=False
        ))

        # 2. Colored thinner line on top (matches matplotlib linewidth=2.0)
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines", 
            line=dict(width=3, color=color), 
            name=f"Chain {component_index + 1}"
        ))

        # 3. Nodes with black edges (matches matplotlib edgecolors="black")
        fig.add_trace(go.Scatter(
            x=node_x, y=node_y, mode="markers", text=node_text, hoverinfo="text",
            marker=dict(size=7, color=color, line=dict(width=1.5, color="black")),
            showlegend=False,
        ))

    fig.update_layout(
        title=title, hovermode="closest",
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=True, zeroline=False, scaleanchor="y", scaleratio=1, gridcolor="lightgray"),
        yaxis=dict(showgrid=True, zeroline=False, scaleanchor="x", scaleratio=1, gridcolor="lightgray"),
        plot_bgcolor="white",
        dragmode="zoom",
    )
    return fig


def create_connected_component_figure(
    connected_graph: nx.Graph,
    added_edges: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    width: float,
    height: float,
    rows: int,
    cols: int,
    title: str = "Connected Layer Chains",
) -> go.Figure:
    """Create a publication-style continuous sequence plot with overlapping Z-order crossings."""
    if connected_graph is None or len(connected_graph.nodes) == 0:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(_create_boundary_trace(0.0, width * cols, 0.0, height * rows))

    # 1. Draw Faint Background Graph
    bg_x, bg_y = [], []
    for u, v in connected_graph.edges():
        x0, y0 = connected_graph.nodes[u]["pos"]
        x1, y1 = connected_graph.nodes[v]["pos"]
        bg_x.extend([x0, x1, None])
        bg_y.extend([y0, y1, None])

    fig.add_trace(go.Scatter(
        x=bg_x, y=bg_y, mode="lines+markers", 
        line=dict(width=2, color="#d1d5db"), 
        marker=dict(size=2, color="#d1d5db", symbol="circle"),
        hoverinfo="none", showlegend=False, name="Base Graph"
    ))

    # 2. Build Ordered Walk
    added_edges_list = list(added_edges) if added_edges else []
    path_nodes = _build_ordered_node_walk(connected_graph, added_edges_list)

    if path_nodes:
        # FILTER: Extract physical segments and discard 0mm jumps
        valid_segments = []
        for i in range(len(path_nodes) - 1):
            n1 = path_nodes[i]
            n2 = path_nodes[i+1]
            x0, y0 = connected_graph.nodes[n1]["pos"]
            x1, y1 = connected_graph.nodes[n2]["pos"]
            
            # Keep only if distance is greater than a tiny tolerance
            if abs(x0 - x1) > 1e-9 or abs(y0 - y1) > 1e-9:
                valid_segments.append(((x0, y0), (x1, y1)))

        num_segments = len(valid_segments)
        
        if num_segments > 0:
            # Map colors purely to the valid physical segments
            segment_colors = pcolors.sample_colorscale("plasma", np.linspace(0, 1, num_segments))

            # 3. Interleaved Plotting for Perfect Z-Order Overlaps & Seamless Joints
            for i, ((x0, y0), (x1, y1)) in enumerate(valid_segments):
                x_seg = [x0, x1]
                y_seg = [y0, y1]
                
                # DRAW OUTLINE: Plot the thick black background for the current segment (i)
                fig.add_trace(go.Scatter(
                    x=x_seg, y=y_seg, 
                    mode="lines+markers", 
                    line=dict(width=7, color="black"), 
                    marker=dict(size=7, color="black", symbol="circle"),
                    hoverinfo="none",
                    showlegend=False
                ))

                # DRAW PREVIOUS FILL: Plot the color line for the PREVIOUS segment (i-1)
                # This ensures the color fill covers the black start-cap of the current segment!
                if i > 0:
                    prev_x0, prev_y0 = valid_segments[i-1][0]
                    prev_x1, prev_y1 = valid_segments[i-1][1]
                    fig.add_trace(go.Scatter(
                        x=[prev_x0, prev_x1], y=[prev_y0, prev_y1], 
                        mode="lines+markers", 
                        line=dict(width=3, color=segment_colors[i-1]), 
                        marker=dict(size=3, color=segment_colors[i-1], symbol="circle"),
                        hovertext=f"Print Step {i-1}",
                        hoverinfo="text",
                        showlegend=False
                    ))

            # DRAW FINAL FILL: Don't forget the color fill for the very last segment!
            if num_segments > 0:
                last_x0, last_y0 = valid_segments[-1][0]
                last_x1, last_y1 = valid_segments[-1][1]
                fig.add_trace(go.Scatter(
                    x=[last_x0, last_x1], y=[last_y0, last_y1], 
                    mode="lines+markers", 
                    line=dict(width=3, color=segment_colors[-1]), 
                    marker=dict(size=3, color=segment_colors[-1], symbol="circle"),
                    hovertext=f"Print Step {num_segments - 1}",
                    hoverinfo="text",
                    showlegend=False
                ))

            # 4. Dummy Trace for Colorbar
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers",
                marker=dict(
                    colorscale="plasma",
                    cmin=0, cmax=num_segments,
                    color=[0, num_segments],
                    showscale=True,
                    colorbar=dict(title="Print Sequence →", thickness=15, len=0.8, x=1.02)
                ),
                showlegend=False, hoverinfo="none"
            ))

        # 5. Add Start and End Markers using the very first and very last nodes
        start_x, start_y = connected_graph.nodes[path_nodes[0]]["pos"]
        end_x, end_y = connected_graph.nodes[path_nodes[-1]]["pos"]

        fig.add_trace(go.Scatter(
            x=[start_x], y=[start_y], mode="markers", 
            marker=dict(size=10, color="black", symbol="circle"), 
            name="Start"
        ))
        fig.add_trace(go.Scatter(
            x=[end_x], y=[end_y], mode="markers", 
            marker=dict(size=10, color="black", symbol="square"), 
            name="End"
        ))

    fig.update_layout(
        title=title, hovermode="closest",
        margin=dict(b=20, l=5, r=100, t=40), 
        xaxis=dict(showgrid=True, zeroline=False, scaleanchor="y", scaleratio=1, gridcolor="lightgray"),
        yaxis=dict(showgrid=True, zeroline=False, scaleanchor="x", scaleratio=1, gridcolor="lightgray"),
        plot_bgcolor="white",
        dragmode="zoom",
    )
    return fig


def create_fullcontrol_plot_figure(
    plot_data,
    title: str = "FullControl Preview",
    extrusion_width: float | None = None,
    layer_height: float | None = None,
) -> go.Figure:
    """Convert FullControl raw plot data into a Dash-friendly Plotly figure."""
    fig = go.Figure()

    bounding_box = getattr(plot_data, "bounding_box", None)
    if bounding_box is not None:
        minx = getattr(bounding_box, "minx", getattr(bounding_box, "xmin", None))
        maxx = getattr(bounding_box, "maxx", getattr(bounding_box, "xmax", None))
        miny = getattr(bounding_box, "miny", getattr(bounding_box, "ymin", None))
        maxy = getattr(bounding_box, "maxy", getattr(bounding_box, "ymax", None))
        minz = getattr(bounding_box, "minz", getattr(bounding_box, "zmin", None))
        maxz = getattr(bounding_box, "maxz", getattr(bounding_box, "zmax", None))
        x_padding = 0.0
        y_padding = 0.0
        z_padding = 0.0
        if minx is not None and maxx is not None:
            x_padding = max((maxx - minx) * 0.06, extrusion_width or 0.4)
        if miny is not None and maxy is not None:
            y_padding = max((maxy - miny) * 0.06, extrusion_width or 0.4)
        if minz is not None and maxz is not None:
            z_padding = max((maxz - minz) * 0.04, layer_height or 0.2)

        x_range = [minx - x_padding, maxx + x_padding] if minx is not None and maxx is not None else None
        y_range = [miny - y_padding, maxy + y_padding] if miny is not None and maxy is not None else None
        z_range = [minz - z_padding, maxz + z_padding] if minz is not None and maxz is not None else None

        xy_extent = max(
            (maxx - minx) if minx is not None and maxx is not None else 0.0,
            (maxy - miny) if miny is not None and maxy is not None else 0.0,
        )
        bead_width = extrusion_width if extrusion_width is not None else max(xy_extent * 0.012, 0.1)
        bead_height = layer_height if layer_height is not None else max(bead_width * 0.5, 0.05)
    else:
        x_range = y_range = z_range = None
        bead_width = extrusion_width if extrusion_width is not None else 0.1
        bead_height = layer_height if layer_height is not None else 0.05

    for path in getattr(plot_data, "paths", []):
        if not getattr(path, "xvals", None):
            continue

        is_extruding = getattr(getattr(path, "extruder", None), "on", False)
        if getattr(path, "colors", None):
            first_color = path.colors[0]
            if isinstance(first_color, (list, tuple)) and len(first_color) == 3:
                rgb_color = tuple(max(0, min(255, int(channel * 255))) for channel in first_color)
                color = f"rgb({rgb_color[0]}, {rgb_color[1]}, {rgb_color[2]})"
            else:
                color = "#2563eb" if is_extruding else "#94a3b8"
        else:
            color = "#2563eb" if is_extruding else "#94a3b8"

        if is_extruding:
            colors_now = []
            for point_color in getattr(path, "colors", []) or []:
                if isinstance(point_color, (list, tuple)) and len(point_color) == 3:
                    colors_now.append(
                        f"rgb({point_color[0] * 255:.2f}, {point_color[1] * 255:.2f}, {point_color[2] * 255:.2f})"
                    )
                else:
                    colors_now.append(color)
            if not colors_now:
                colors_now = [color] * len(path.xvals)

            mesh_trace = _build_fullcontrol_path_mesh(
                path,
                colors_now=colors_now,
                extrusion_width=bead_width,
                layer_height=bead_height,
            )
            if mesh_trace is not None:
                fig.add_trace(mesh_trace)
        else:
            fig.add_trace(
                go.Scatter3d(
                    mode="lines",
                    x=path.xvals,
                    y=path.yvals,
                    z=path.zvals,
                    line=dict(color=color, width=3, dash="dash"),
                    hoverinfo="none",
                    name="Travel",
                    showlegend=False,
                )
            )

    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#020617",
        plot_bgcolor="#020617",
        margin=dict(l=0, r=0, b=0, t=40),
        scene=dict(
            bgcolor="#020617",
            xaxis=dict(
                title="X",
                range=x_range,
                backgroundcolor="#020617",
                gridcolor="rgba(148,163,184,0.18)",
                zerolinecolor="rgba(148,163,184,0.22)",
            ),
            yaxis=dict(
                title="Y",
                range=y_range,
                backgroundcolor="#020617",
                gridcolor="rgba(148,163,184,0.18)",
                zerolinecolor="rgba(148,163,184,0.22)",
            ),
            zaxis=dict(
                title="Z",
                range=z_range,
                backgroundcolor="#020617",
                gridcolor="rgba(148,163,184,0.18)",
                zerolinecolor="rgba(148,163,184,0.22)",
            ),
            aspectmode="data",
        ),
    )
    return fig
