# Implementation Plan

## Goal

Build the app as a loop-based lattice design tool:

1. import a DXF unit cell
2. convert it into a graph
3. create the periodic/self-looping graph
4. discover all loops with non-zero winding
5. let the user choose which loops belong to a layer
6. reject loop combinations that share edges within the same layer
7. tile the selected layer over a grid
8. connect the result into a printable path
9. prepare the path for later G-code export

This plan is intentionally broken into small milestones so each one is easy to implement, inspect, and debug before moving on.

## Milestone 1: Clean up the app flow and state model

### Target

Make the current Dash app structure match the new product direction before porting more algorithm code.

### Tasks

- rename the Step 2 concept from `Eulerian Routing` to something like `Loop Discovery`
- rename any old store IDs or labels that still imply one Eulerian path
- define the minimal app state we need for the next milestones
- keep the app limited to a single editable layer for now

### Small checks

- the tab titles reflect the new loop-based workflow
- no UI text suggests the app is looking for one Eulerian solution
- the app stores are understandable and aligned with the next steps
- current upload and DXF preview still work after the cleanup

### Deliverable

A cleaner app shell that matches the real algorithm direction and is ready for new core modules.

## Milestone 2: Port periodic graph generation into `src/core`

### Target

Move the periodic wrapping logic out of `old_code` and make it a clean reusable backend step.

### Tasks

- create `src/core/periodic_graph.py`
- port `create_periodic_multigraph(...)`
- keep the output explicit:
  - periodic multigraph
  - original-to-periodic node mapping
- preserve original edge metadata such as source node IDs
- keep the implementation independent from Dash

### Small checks

- a parsed DXF graph can be passed into the periodic graph function without UI code
- boundary nodes are merged logically across opposite sides
- internal nodes remain unchanged
- output still preserves enough edge metadata for later winding and loop reconstruction

### Deliverable

A working `periodic_graph.py` module that can be called from the app or from a simple script.

## Milestone 3: Add a periodic multigraph viewer

### Target

Add a small visual validation step so the raw DXF graph and the periodic multigraph can be inspected side by side before loop discovery starts.

### Tasks

- extend `src/core/plot_utils.py` with a periodic-graph preview function
- plot the periodic multigraph as an abstract topology view, not as a final physical toolpath view
- position each periodic node using a deterministic representative original-node position
- draw multiedges with curvature so parallel edges remain visible
- show the original DXF graph and periodic multigraph next to each other in Step 1
- include hover data or labels showing which original nodes were merged into each periodic node
- include edge hover data showing the original edge endpoints that produced each periodic edge
- keep this as a debug-oriented viewer, not a polished final UX

### Small checks

- the DXF graph preview still renders correctly
- the periodic multigraph preview renders from the same uploaded graph
- merged periodic nodes are visually distinguishable from the original graph view
- hover text or labels make it possible to inspect which original nodes were merged
- parallel multiedges do not fully overlap in the periodic view
- the side-by-side layout remains readable for small sample files

### Deliverable

A Step 1 viewer that lets you visually compare the imported unit-cell graph and an abstract periodic/self-looping multigraph for merge/topology validation.

## Milestone 4: Discover loops and compute winding

### Target

Build the first version of loop discovery that returns a catalog of valid loops instead of one global solution.

### Tasks

- create `src/core/loop_finder.py`
- port the useful parts of:
  - loop enumeration
  - winding calculation
  - physical edge reconstruction
- define one canonical loop record shape
- enrich the loop record with UI-ready display fields computed in the backend
- filter out loops with winding `(0, 0)`
- assign each remaining loop a stable display ID for the UI
- precompute a readable path text from the ordered physical edges

### Small checks

- loop discovery runs on at least one sample DXF or one old hard-coded graph
- each discovered loop includes:
  - ordered edges
  - winding
  - a stable ID
- each discovered loop also includes display-ready fields such as:
  - edge count
  - node sequence or equivalent path display data
  - path text for the loop list
- zero-winding loops are excluded from the loop catalog
- duplicate loops are reduced enough that the user is not flooded with obvious repeats

### Deliverable

A backend function that takes a unit-cell graph and returns a list of valid printable loops with frontend-friendly display metadata.

## Milestone 5: Define the layer loop-selection model

### Target

Represent one layer as a user-selected combination of valid loops.

### Tasks

- create `src/core/layer_builder.py`
- define the rule for loop compatibility inside one layer:
  - shared edges are forbidden
  - shared nodes are allowed
- define how a layer selection is represented in code
- implement conflict detection between selected loops
- return clear conflict details for the UI

### Small checks

- selecting one loop is always valid
- two loops that share only nodes are accepted
- two loops that share at least one edge are rejected
- the conflict result is easy to show in the UI

### Deliverable

A clean layer-selection backend that can validate user choices without any tiling yet.

## Milestone 6: Add loop discovery and selection to the app

### Target

Expose the loop catalog in Step 2 and let the user build one layer interactively.

### Tasks

- update the Step 2 UI in `src/components/`
- render Step 2 as a split layout:
  - top preview area
  - bottom loop catalog list
- show the original physical unit-cell graph with node labels in the top-left panel
- show the currently selected loop preview in the top-right panel
- show a discovered loop list after DXF parsing in the bottom panel
- use the backend-precomputed loop display fields directly in the list
- start with simple loop inspection and selection behavior before full layer composition controls
- make it easy to click a loop in the list and update the top-right preview
- defer more complex "add to layer" behavior until the catalog and preview feel correct

### Small checks

- Step 2 becomes available after a successful DXF upload
- the app can display discovered loops without crashing
- the top-left graph keeps node labels visible
- clicking a loop row updates the top-right preview to the correct loop
- the loop list shows readable path text without frontend parsing logic
- the selected loop state updates correctly
- the layout remains readable with multiple discovered loops

### Deliverable

A usable Step 2 loop catalog screen with top preview panels and a backend-driven loop list.

## Milestone 7: Preview the selected unit-cell layer

### Target

Show what the chosen loop combination looks like before tiling.

### Tasks

- merge the selected compatible loops into one layer graph
- add a visualization function for the selected layer
- display the selected loops differently from the raw imported geometry if helpful
- keep the preview simple and inspection-friendly

### Small checks

- one selected loop previews correctly
- multiple compatible loops preview as one combined unit-cell layer
- invalid selections never produce a misleading preview
- the preview is visually understandable enough for manual inspection

### Deliverable

A unit-cell layer preview driven by the current loop selection.

## Milestone 8: Tile the selected layer over a grid

### Target

Turn one selected layer into a repeated 2D lattice layer while preserving path continuity across periodic boundaries.

### Tasks

- create `src/core/tiling.py`
- add a layer-level threaded representation builder from the selected loops
- port the simpler threaded tiling and stitching path from the old code first
- tile the threaded layer by row and column offsets
- stitch periodic neighbors across cell boundaries only when the threaded visit identity matches
- keep the plain merged `layer_graph` as a preview structure only, not the authoritative tiling input
- add a geometric debug plot for the tiled stitched graph
- color each connected component differently in the debug plot so each chain is easy to inspect

### Manual check

- add a simple `if __name__ == "__main__"` path or equivalent debug entry point for Milestone 8
- allow manual changes to `m` and `n` grid size in that debug path
- tile and stitch the selected layer for the chosen `m x n` grid
- plot the tiled stitched graph in geometric coordinates
- render each connected component in a different color so each continuous chain can be visually inspected
- verify manually on at least one known sample that the number and shape of chains look correct before moving to Milestone 9

### Deliverable

A tiled stitched graph for one layer where repeated boundary visits remain distinct chains and can be visually inspected component-by-component.

## Milestone 9: Connect loose ends into a printable traversal

### Target

Convert the tiled layer graph into something closer to a continuous print path.

### Tasks

- create `src/core/pathing.py` or add a path-connection function there
- port the simpler robust connection strategy from `old_code`
- find loose ends after tiling
- connect components while avoiding obviously bad self-connections
- keep the first strategy simple and inspectable

### Small checks

- disconnected components get reduced after connection
- the function does not connect nodes already in the same component
- the result is more printable than the raw tiled graph
- the logic works on at least one of the old sample structures

### Deliverable

A connected or more-connected graph suitable for path extraction and preview.

## Milestone 10: Extract ordered print paths

### Target

Turn the connected graph into ordered point sequences for visual inspection and future G-code export.

### Tasks

- add ordered path extraction to `src/core/pathing.py`
- choose a simple path start rule
- support the case where there are still multiple components
- return coordinates in a shape that later export code can use directly

### Small checks

- the app can generate ordered coordinate paths from the connected graph
- the path order is stable enough to inspect visually
- if multiple components remain, each becomes its own path sequence
- the output format is straightforward to pass into a future G-code module

### Deliverable

Ordered printable path data for one tiled layer.

## Milestone 11: Add tiled-layer and path preview to the app

### Target

Make Step 3 show the full tiled layer and the extracted path information.

### Tasks

- wire rows and columns inputs into the new tiling backend
- render the tiled graph preview
- optionally overlay the connected path order if useful
- keep the visualization responsive enough for small and medium examples

### Small checks

- changing rows or columns updates the preview
- the preview reflects the currently selected loops
- the app still behaves correctly when the loop selection changes
- the user can manually inspect whether the tiling and pathing make sense

### Deliverable

A usable lattice preview stage that shows what one chosen layer will actually look like across the grid.

## Milestone 12: Prepare export inputs

### Target

Stop at a clean handoff point for future G-code work.

### Tasks

- define the data shape that export will consume
- keep export separate from UI state as much as possible
- confirm the ordered path data includes the information needed for later multi-layer composition
- leave the actual G-code export as the next implementation phase

### Small checks

- one selected layer can be represented as ordered printable paths
- the same data could later be repeated or sequenced across many layers
- no UI-specific objects leak into the export boundary

### Deliverable

A stable backend output boundary for future G-code generation.

## Recommended implementation order

Implement in this order:

1. Milestone 1
2. Milestone 2
3. Milestone 3
4. Milestone 4
5. Milestone 5
6. Milestone 6
7. Milestone 7
8. Milestone 8
9. Milestone 9
10. Milestone 10
11. Milestone 11
12. Milestone 12

## Notes for implementation

- prefer small pure functions in `src/core`
- keep Dash callbacks thin
- avoid over-optimizing early
- avoid building multi-layer authoring yet
- avoid depending on the threaded-visit representation unless the simpler tiling approach clearly fails
- use `old_code/test.py` as the main reference first, then borrow from the other old files only where needed

## Definition of “good enough” for this phase

This phase is successful when:

- the app can discover valid non-zero-winding loops from a DXF-defined unit cell
- the user can select loops for one layer
- the app rejects edge-sharing loop combinations
- the selected layer can be tiled across a grid
- the tiled layer can be turned into ordered printable path data
- the result is inspectable in the UI, even if G-code export is not finished yet
