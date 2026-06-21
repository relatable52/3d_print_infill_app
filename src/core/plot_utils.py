import plotly.graph_objects as go
import networkx as nx

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
) -> go.Figure:
    min_x, max_x, min_y, max_y = _get_graph_bounds(graph)
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


def create_periodic_multigraph_figure(graph: nx.MultiGraph) -> go.Figure:
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

    return _create_base_figure(
        graph,
        title="Periodic Multigraph Preview",
        traces=[*edge_traces, node_trace],
    )
