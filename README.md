# 3D Print App

Dash app for designing lattice-based FDM print paths from a DXF-defined unit cell.

The project is aimed at custom porous scaffold generation:

- import one unit-cell sketch from DXF
- convert it into a graph
- build the periodic/self-looping graph
- discover valid loops with non-zero winding
- let the user compose loops into layers
- tile each layer over an `m x n` grid
- stitch and connect the tiled chains into printable paths
- generate and preview G-code

## Current Workflow

The app is organized into 4 tabs:

### 1. DXF Preview

- upload a DXF file
- parse `LINE` and `LWPOLYLINE` entities into a `networkx` graph
- preview the physical DXF graph
- preview the periodic multigraph beside it for debugging

### 2. Loop Discovery

- discover valid periodic loops
- filter out zero-winding loops
- inspect loop previews
- build multiple editable layers by adding or removing loops
- reject loop combinations that share edges within the same layer

### 3. Layer Tiling

- choose one global tiling size `m x n`
- tile and stitch all designed layers
- inspect any tiled layer
- connect disconnected chains into one print path with the current sweep strategy

### 4. Export G-Code

- set basic print parameters
- repeat the designed layer cycle to a requested total number of print layers
- generate G-code with `fullcontrol`
- preview the generated toolpath in 3D
- download the generated `.gcode`

## What This App Is Solving

The important design idea is that one print layer does not need to print the entire unit cell.

Instead:

- each layer can contain only selected loops from the unit cell
- different layers can use different loop combinations
- this creates controlled porosity
- node sharing is allowed
- edge sharing within the same layer is not allowed

This is more flexible than forcing the whole problem into one Eulerian traversal or one 2-factor decomposition.

## Tech Stack

- Python
- Dash
- Plotly
- NetworkX
- ezdxf
- FullControl
- uv for environment and dependency management

## Project Layout

```text
src/
  app.py
  assets/
  callbacks/
  components/
  core/
samples/
old_code/
run_app.bat
run_app.sh
pyproject.toml
uv.lock
```

Important modules:

- [src/app.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/app.py): Dash entrypoint
- [src/core/dxf_parser.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/dxf_parser.py): DXF to graph parsing
- [src/core/periodic_graph.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/periodic_graph.py): periodic multigraph construction
- [src/core/loop_finder.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/loop_finder.py): loop discovery and catalog data
- [src/core/layer_builder.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/layer_builder.py): layer validation / merging
- [src/core/tiling.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/tiling.py): tile + stitch
- [src/core/pathing.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/pathing.py): chain connection logic
- [src/core/gcode.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/gcode.py): FullControl export pipeline
- [src/core/plot_utils.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/core/plot_utils.py): Plotly preview helpers

## Quick Start

### Windows

Double-click:

```text
run_app.bat
```

It will:

- install `uv` if missing
- run `uv sync`
- launch the app

### Linux / macOS

Run:

```bash
chmod +x run_app.sh
./run_app.sh
```

It will:

- install `uv` if missing
- run `uv sync`
- launch the app

### Manual Launch

If you already have `uv`:

```bash
uv sync
uv run -m src.app
```

## Hugging Face Spaces Deployment

This repo can be deployed to a Hugging Face Docker Space without a `requirements.txt`.

Dependencies are installed directly from [pyproject.toml](C:/Users/Chinh/Documents/AIME/3d_print_app/pyproject.toml).

Files used for deployment:

- [Dockerfile](C:/Users/Chinh/Documents/AIME/3d_print_app/Dockerfile)
- [.dockerignore](C:/Users/Chinh/Documents/AIME/3d_print_app/.dockerignore)
- [src/app.py](C:/Users/Chinh/Documents/AIME/3d_print_app/src/app.py)

Deployment steps:

1. Create a new Hugging Face Space.
2. Choose `Docker` as the SDK.
3. Push this repository to the Space repository.
4. Hugging Face will build the image automatically.
5. The app will start on host `0.0.0.0` and port `7860`.

Notes:

- this setup uses Python `3.13`
- the container command is `python -m src.app`
- the app reads `PORT` from the environment and defaults to `7860`

## Requirements

- Python `>= 3.13`
- internet access on first run to install dependencies

## Supported DXF Geometry

Current parser support:

- `LINE`
- `LWPOLYLINE`

Notes:

- some DXF files exported from CAD tools may include proxy/custom objects
- some uploads may fail because of unsupported DXF content, not because the sketch is empty
- detailed DXF read errors are printed to the terminal for debugging

## G-Code Export Parameters

The current export screen exposes a minimal parameter set:

- number of layers
- layer height
- nozzle diameter
- filament diameter
- flow
- print speed
- travel speed
- nozzle temperature
- bed temperature
- XY scale
- XY origin

The export repeats the designed layer cycle until the requested number of print layers is reached.

Example:

- designed layers: `Layer 1`, `Layer 2`, `Layer 3`
- requested print layers: `8`
- final sequence: `1, 2, 3, 1, 2, 3, 1, 2`

## Notes on the Preview

- Step 1 previews the original graph and periodic multigraph
- Step 2 previews loop building blocks and the layer stack
- Step 3 previews tiled/stiched and connected layer results
- Step 4 previews generated G-code using a custom Plotly view built from FullControl plot data

## Development Notes

- `old_code/` still contains earlier algorithm experiments and references
- `context.md` records the evolving project direction and assumptions
- `implementation_plan.md` contains the milestone-based build plan

## Known Limitations

- DXF parsing support is still intentionally narrow
- unusual CAD exports may require cleanup or re-export
- the plotting and connection logic are still evolving
- the G-code preview is intended for inspection, not slicer-grade verification
- no automated installer or packaged desktop build exists yet

## Suggested Usage

1. Start with a simple DXF containing only lines or lightweight polylines.
2. Confirm the periodic graph looks correct in Step 1.
3. Inspect the discovered loops in Step 2 before building layers.
4. Keep layer combinations simple at first and avoid edge-sharing conflicts.
5. Use Step 3 to inspect tiling and path connection behavior before export.
6. Treat the generated G-code preview as a design/debug view, then verify the final G-code in your preferred external viewer if needed.

## License / Status

This project is currently a research/prototype codebase under active development.
