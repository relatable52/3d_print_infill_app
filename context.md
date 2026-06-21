# Project Context

## What this app is for

This project is an FDM toolpath generator for lattice-based prints built from a **custom unit cell** defined in a DXF file.

The intended workflow is:

1. Import a DXF that defines one unit-cell graph.
2. Convert the geometry into a graph representation.
3. Treat the unit cell as **periodic / self-looping** so opposite boundaries connect logically.
4. Find valid loops in that periodic graph that can become continuous printable paths.
5. Let the user choose which loops to include in each layer.
6. Enforce that loops selected within the same layer do **not share edges**.
7. Tile the selected layer content across many unit cells.
8. Stitch disconnected segments into a printable traversal.
9. Stack different layer paths across Z to create a porous scaffold.

An important domain idea in this project is that **a single layer does not need to print the entire unit cell**. That is intentional. Different layer-wise path choices create **porosity**, which is important for the bio-scaffold application.

Another important update is that the app no longer needs to force the problem into either:

- a full Eulerian traversal of the structure on one layer, or
- a 2-factor decomposition

Those were useful earlier because they matched older constraints:

- 2-factors were used when non-crossing path structure was important
- Eulerian traversal was used when trying to print the entire structure in one layer

The current direction is simpler and more flexible:

- find **all loops** with non-zero winding
- let the user choose which loops belong to each layer
- allow node sharing / crossing when needed
- forbid **edge sharing within the same layer**

So the real design unit is now a **library of valid loops**, not a single forced global solution.

## Current repo status

The current `src/` app is an early Dash UI shell. The core production logic is not migrated yet.

What exists now:

- `src/app.py`: Dash app entrypoint. App title is `Eulerian Slicer`.
- `src/components/` and `src/callbacks/`: early multi-step UI scaffold.
- `src/core/dxf_parser.py`: DXF parsing into a `networkx.Graph`.
- `src/core/plot_utils.py`: Plotly preview of the imported unit-cell graph.
- `old_code/`: where the main algorithm experiments and prototypes currently live.

## How the current `src/` app works

### DXF import

`src/core/dxf_parser.py` currently:

- reads a DXF from file path or uploaded bytes
- supports `LINE` and `LWPOLYLINE`
- merges nearby endpoints by rounding coordinates
- stores each node with a `pos=(x, y)` attribute
- normalizes the graph so the unit cell is shifted into a `(0,0)` to `(W,H)` bounding box
- returns:
  - `graph`
  - `width`
  - `height`

This normalization matters because the periodic wrapping logic depends on clean boundary coordinates.

### UI flow

The Dash UI currently has four tabs:

1. `DXF Preview`
2. `Eulerian Routing`
3. `Tiling & Stitching`
4. `Export G-Code`

Only step 1 is partially implemented right now:

- upload DXF
- parse DXF into graph
- store graph in Dash `dcc.Store`
- preview the geometry with Plotly

The later tabs are placeholders.

## Where the core algorithm currently lives

The most complete versions are in:

- `old_code/test.py`
- `old_code/test_one_layer.py`
- `old_code/test_new_one_layer.py`
- `old_code/new_test.py`

These files overlap, but together they show the algorithm evolution.

## Core algorithm concept

### 1. Unit cell as a graph

A unit cell is modeled as a graph where:

- nodes are geometric points
- edges are printable segments
- node positions are stored in `pos`

There are also hard-coded example unit cells in `old_code/unitcell.py`:

- `honeycomb_unit_cell`
- `snake_unit_cell`
- `diamond_unit_cell`
- `reentrant_unit_cell`

### 2. Periodic wrapping / self-looping graph

Main function:

- `create_periodic_multigraph(...)`

Idea:

- nodes on opposite boundaries are treated as equivalent periodic partners
- a temporary merge graph finds connected components of equivalent boundary nodes
- the original graph is collapsed into a periodic `networkx.MultiGraph`
- edges keep metadata like `original_u` and `original_v`

This is the key step that makes one cell behave like an infinite lattice neighborhood.

### 3. Find printable loops

There are several related approaches in `old_code`, but they should now be treated mostly as historical search strategies rather than the final product definition.

Older approaches included:

- finding Eulerian circuits in the periodic graph
- finding 2-factors / degree-2 subgraphs, then validating them

Representative functions/classes:

- `find_all_eulerian_circuits(...)`
- `UnitCellSolver`
- `analyze_solution_validity(...)`
- `calculate_path_winding(...)`

The core filtering idea that still matters is:

- valid loops should **cross the periodic boundaries**
- invalid loops are closed islands trapped inside one cell

This is often checked with a winding / jump analysis:

- non-zero winding -> useful crossing path
- zero winding -> isolated island, usually rejected

So the modern goal is:

- enumerate loops
- compute their winding
- keep loops with winding not equal to `(0, 0)`
- expose them to the user as selectable building blocks for layers

The app does **not** need to require that all accepted loops come from one Eulerian or one 2-factor solution anymore.

### 4. Convert loop into a threaded visit graph

Main function:

- `create_threaded_visit_graph(...)`

Purpose:

- annotate repeated visits to periodic-equivalent nodes
- distinguish cases like `1_0`, `1_1`, etc.
- preserve continuity when the same merged periodic node is visited multiple times

This is what allows later tiling/stitching to match the correct boundary crossings.

### 5. Build a layer from selected loops

The intended layer workflow is now:

1. user selects any subset of valid loops
2. the app checks that no two selected loops in the same layer share an edge
3. node sharing is allowed
4. once the layer definition is valid, tile it across the print region

This gives the user much more freedom to define porosity and path families layer by layer.

### 6. Tile the selected loop set over a grid

Representative functions:

- `tile_and_stitch_threads(...)`
- `create_tiled_layer_graph(...)`
- `create_tiled_graph(...)`

Purpose:

- instantiate the chosen unit-cell path at each row/column offset
- connect neighboring cells across left/right and top/bottom boundaries
- either:
  - stitch by matching visit IDs, or
  - union/merge periodic boundary nodes directly

This creates one graph for an entire print layer.

### 7. Connect remaining loose ends into a print path

Representative functions:

- `connect_boundaries_robust(...)`
- `robust_connect(...)`

Purpose:

- find degree-1 endpoints after tiling
- greedily connect components into a longer printable route
- avoid connecting nodes already in the same component
- some newer versions also prefer top-left progression and try to avoid self-intersection first

This step turns multiple disconnected stripes/loops into a more usable continuous print sequence.

### 8. Convert graph to ordered path(s)

Representative functions:

- `graph_to_ordered_paths(...)`
- `extract_printing_path(...)`

Purpose:

- walk the stitched graph in order
- recover coordinates for printing
- choose start nodes from odd-degree endpoints when available

### 9. Multi-layer build strategy

Representative functions:

- `generate_lattice_gcode(...)`
- `generate_multilayer_gcode(...)`
- `generate_and_plot(...)`

Important idea:

- each layer can be composed from any user-selected combination of valid loops
- the only hard compatibility rule inside one layer is: **no shared edges**
- repeated, alternating, or custom layer recipes create the desired scaffold morphology
- this is the mechanism that supports partial-cell printing per layer and controlled porosity

Example pattern used in experiments:

- alternating solution indices across layers, such as `[0, 3, 0, 3] * 5`

In the new design, that kind of sequence is just one special case of a broader layer recipe system.

## G-code generation

The old prototypes use `fullcontrol` to:

- create motion points
- toggle extrusion on/off
- emit startup and shutdown G-code
- visualize paths
- export `.gcode`

Representative functions:

- `generate_gcode_from_graph(...)`
- `generate_multilayer_gcode(...)`
- `export_to_gcode_fullcontrol(...)`
- `generate_lattice_gcode(...)`

## Files that matter most right now

If we continue development, these are the highest-value references:

- `src/core/dxf_parser.py`
  - current DXF-to-graph entry point
- `src/callbacks/tab_1_callbacks.py`
  - current upload and preview wiring
- `old_code/test.py`
  - strongest high-level version of solution filtering + layer sequence generation
- `old_code/test_one_layer.py`
  - one-layer tiling/stitching and plotting flow
- `old_code/test_new_one_layer.py`
  - newer boundary-connection and export ideas
- `old_code/unitcell.py`
  - sample unit-cell definitions

## Current gaps

The app is not finished yet. Based on the current codebase, the main missing work is:

- migrate the proven graph/path logic from `old_code/` into `src/core/`
- replace the old "pick one global solution type" mindset with loop enumeration + layer composition
- expose loop discovery and loop selection in the Dash UI
- add a compatibility check that rejects loops sharing edges inside the same layer
- expose tiling/grid controls in the Dash UI
- support custom per-layer loop combinations, not just a single repeated path
- integrate G-code export into the app flow
- add tests around periodic wrapping, validity filtering, stitching, and path ordering

## Notes and observations

- `old_code/graph.py` is currently empty.
- `README.md` is currently empty.
- The current app architecture suggests `src/` is being prepared as the cleaned-up product version, while `old_code/` contains the research/prototype logic.

## Suggested next migration direction

The cleanest next step would likely be to move the algorithm into new `src/core/` modules such as:

- `src/core/periodic_graph.py`
- `src/core/solver.py`
- `src/core/tiling.py`
- `src/core/pathing.py`
- `src/core/gcode_export.py`

Then wire the UI tabs to those modules in order:

1. DXF import
2. valid path discovery
3. tiling + stitching preview
4. layer sequencing
5. G-code export
