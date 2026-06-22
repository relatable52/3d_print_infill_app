import plotly.graph_objects as go
import networkx as nx


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
    """Create a geometric 2D view with a different color per connected component."""
    if tiled_graph is None or len(tiled_graph.nodes) == 0:
        return go.Figure()

    boundary_trace = _create_boundary_trace(0.0, width * cols, 0.0, height * rows)
    fig = go.Figure(data=[boundary_trace])

    components = list(nx.connected_components(tiled_graph))
    component_count = max(len(components), 1)

    for component_index, component_nodes in enumerate(components):
        component_graph = tiled_graph.subgraph(component_nodes)
        t = 0.0 if component_count <= 1 else component_index / (component_count - 1)
        color = _interpolate_hex_color("#2563eb", "#ea580c", t)

        edge_x = []
        edge_y = []
        for start, end in component_graph.edges():
            x0, y0 = tiled_graph.nodes[start]["pos"]
            x1, y1 = tiled_graph.nodes[end]["pos"]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        node_x = []
        node_y = []
        node_text = []
        for node_id in component_graph.nodes():
            x, y = tiled_graph.nodes[node_id]["pos"]
            node_x.append(x)
            node_y.append(y)
            node_text.append(str(node_id))

        fig.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line=dict(width=3, color=color),
                hoverinfo="none",
                name=f"Chain {component_index + 1}",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers",
                text=node_text,
                hoverinfo="text",
                marker=dict(size=6, color=color, line=dict(width=1, color="#0f172a")),
                showlegend=False,
            )
        )

    fig.update_layout(
        title=title,
        showlegend=True,
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
    )
    return fig
