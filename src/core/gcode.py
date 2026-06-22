from dataclasses import dataclass

import fullcontrol as fc
import networkx as nx


@dataclass(frozen=True)
class ExportSettings:
    number_of_layers: int
    layer_height: float
    nozzle_diameter: float
    filament_diameter: float
    flow: float
    print_speed: float
    travel_speed: float
    nozzle_temperature: float
    bed_temperature: float
    scale_xy: float
    origin_x: float
    origin_y: float


def extract_ordered_path_points(connected_graph: nx.Graph) -> list[tuple[float, float]]:
    """Extract one ordered path from a single connected chain graph."""
    if connected_graph.number_of_nodes() == 0:
        return []

    if nx.number_connected_components(connected_graph) != 1:
        raise ValueError("Expected one connected component per designed layer for export.")

    degree_one_nodes = [node_id for node_id, degree in connected_graph.degree() if degree == 1]
    if degree_one_nodes:
        start_node = min(
            degree_one_nodes,
            key=lambda node_id: (
                connected_graph.nodes[node_id]["pos"][0],
                -connected_graph.nodes[node_id]["pos"][1],
                str(node_id),
            ),
        )
    else:
        start_node = next(iter(connected_graph.nodes()))

    ordered_nodes = [start_node]
    visited_nodes = {start_node}
    previous_node = None
    current_node = start_node

    while True:
        next_candidates = [
            neighbor
            for neighbor in connected_graph.neighbors(current_node)
            if neighbor != previous_node and neighbor not in visited_nodes
        ]
        if not next_candidates:
            break

        next_node = next_candidates[0]
        ordered_nodes.append(next_node)
        visited_nodes.add(next_node)
        previous_node = current_node
        current_node = next_node

    return [
        tuple(connected_graph.nodes[node_id]["pos"])
        for node_id in ordered_nodes
    ]


def build_repeating_layer_sequence(
    connected_results: dict,
    layers: list[dict],
    number_of_layers: int,
) -> list[dict]:
    """Repeat the designed layer order until the requested print layer count is reached."""
    if not connected_results or not connected_results.get("layers"):
        return []

    available_results = connected_results["layers"]
    design_cycle = [
        {
            "layer_id": layer["layer_id"],
            "layer_name": available_results[layer["layer_id"]]["layer_name"],
            "connected_graph": nx.node_link_graph(available_results[layer["layer_id"]]["connected_graph"]),
        }
        for layer in layers
        if layer["layer_id"] in available_results
    ]

    if not design_cycle:
        return []

    full_sequence = []
    for index in range(number_of_layers):
        source_layer = design_cycle[index % len(design_cycle)]
        full_sequence.append(
            {
                "print_layer_index": index,
                "layer_id": source_layer["layer_id"],
                "layer_name": source_layer["layer_name"],
                "connected_graph": source_layer["connected_graph"],
            }
        )

    return full_sequence


def build_fullcontrol_steps(
    layer_sequence: list[dict],
    settings: ExportSettings,
) -> list:
    """Translate the repeated layer sequence into FullControl steps."""
    steps = [
        fc.Printer(print_speed=settings.print_speed, travel_speed=settings.travel_speed),
        fc.Extruder(on=False, dia_feed=settings.filament_diameter, relative_gcode=True),
        fc.ExtrusionGeometry(
            area_model="rectangle",
            width=settings.nozzle_diameter * settings.flow,
            height=settings.layer_height,
        ),
    ]

    for layer in layer_sequence:
        z_height = (layer["print_layer_index"] + 1) * settings.layer_height
        path_points = extract_ordered_path_points(layer["connected_graph"])
        if not path_points:
            continue

        first_x, first_y = path_points[0]
        steps.append(
            fc.Point(
                x=first_x * settings.scale_xy + settings.origin_x,
                y=first_y * settings.scale_xy + settings.origin_y,
                z=z_height,
            )
        )
        steps.append(fc.Extruder(on=True))

        for x_value, y_value in path_points[1:]:
            steps.append(
                fc.Point(
                    x=x_value * settings.scale_xy + settings.origin_x,
                    y=y_value * settings.scale_xy + settings.origin_y,
                    z=z_height,
                )
            )

        steps.append(fc.Extruder(on=False))

    return steps


def generate_fullcontrol_gcode(steps: list, settings: ExportSettings) -> str:
    """Generate G-code text from FullControl steps."""
    return fc.transform(
        steps,
        "gcode",
        fc.GcodeControls(
            printer_name="generic",
            initialization_data={
                "print_speed": settings.print_speed,
                "travel_speed": settings.travel_speed,
                "extrusion_width": settings.nozzle_diameter * settings.flow,
                "extrusion_height": settings.layer_height,
                "nozzle_temp": settings.nozzle_temperature,
                "bed_temp": settings.bed_temperature,
                "dia_feed": settings.filament_diameter,
                "material_flow_percent": settings.flow * 100.0,
            },
        ),
    )


def generate_fullcontrol_plot_data(steps: list):
    """Generate FullControl raw plot data for custom Dash/Plotly rendering."""
    return fc.transform(
        steps,
        "plot",
        fc.PlotControls(
            raw_data=True,
            color_type="print_sequence",
            hide_annotations=True,
            hide_axes=True,
            hide_travel=False,
            style="line",
            line_width=3,
            initialization_data={
                "extrusion_width": 0.4,
                "extrusion_height": 0.2,
            },
        ),
    )
