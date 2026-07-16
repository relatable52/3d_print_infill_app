# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "matplotlib",
#     "numpy",
# ]
# ///

import sys
import os
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib import cm

# Enable LaTeX text rendering and set academic fonts
plt.rcParams.update({
    # "text.usetex": True,
    # "font.family": "serif",
    # "font.serif": ["Computer Modern Roman"],
    "font.size": 10,
    "axes.labelsize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
})

def extract_first_layer(filepath):
    """
    Reads a G-code file line-by-line to extract the first layer toolpath.
    Filters out zero-length/dummy moves to prevent visual breaks.
    """
    x_coords, y_coords = [], []
    last_x, last_y, current_z = 0.0, 0.0, None
    first_layer_z = None
    temp_moves = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.split(';')[0].strip()
            if not line:
                continue
                
            if line.startswith('G0') or line.startswith('G1'):
                parts = line.split()
                x, y, z, e = None, None, None, None
                
                for part in parts:
                    if part.startswith('X'): x = float(part[1:])
                    elif part.startswith('Y'): y = float(part[1:])
                    elif part.startswith('Z'): z = float(part[1:])
                    elif part.startswith('E'): e = float(part[1:])
                
                if z is not None:
                    current_z = z
                    
                current_x = x if x is not None else last_x
                current_y = y if y is not None else last_y
                
                if e is not None and e > 0 and first_layer_z is None:
                    first_layer_z = current_z
                    
                if first_layer_z is not None and current_z is not None and current_z > first_layer_z:
                    break
                    
                if first_layer_z is None:
                    if current_z is not None:
                        temp_moves.append((current_x, current_y, current_z))
                else:
                    if temp_moves:
                        for tx, ty, tz in temp_moves:
                            if tz == first_layer_z:
                                # Ensure we don't append a coordinate if it's identical to the last one
                                if not x_coords or (tx != x_coords[-1] or ty != y_coords[-1]):
                                    x_coords.append(tx)
                                    y_coords.append(ty)
                        temp_moves = []
                        
                    if current_z == first_layer_z:
                        # Prevent zero-length dummy segments from breaking the visual tube
                        if not x_coords or (current_x != x_coords[-1] or current_y != y_coords[-1]):
                            x_coords.append(current_x)
                            y_coords.append(current_y)

                last_x, last_y = current_x, current_y

    if not x_coords:
        raise ValueError("Could not detect any first layer extrusion in the provided file.")

    return x_coords, y_coords

def plot_toolpath(x, y, output_name="first_layer"):
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    N = len(segments)

    # 1. Generate the true colors from the colormap
    cmap = plt.get_cmap('autumn')
    norm = plt.Normalize(0, N)
    mapped_colors = cmap(norm(np.arange(N)))

    # 2. Build your exact stacking sequence
    indices = []
    types = []

    for i in range(N+1):
        if i < N:
            # Add the background segment
            indices.append(i)
            types.append(0)  # (i)-background

        if i > 0:
            # Add the foreground segment
            indices.append(i-1)
            types.append(1)  # (i-1)-true
        
    # Close out the very last segment's true color
    indices.append(N - 1)
    types.append(1) # (N-1)-true

    # Convert to numpy arrays for fast indexing
    indices = np.array(indices)
    types = np.array(types)

    # 3. Construct the interleaved arrays using the sequence
    ordered_segments = segments[indices]
    
    ordered_linewidths = np.zeros(len(indices))
    ordered_linewidths[types == 0] = 3.5  # Background thickness
    ordered_linewidths[types == 1] = 1.5  # Foreground thickness
    
    ordered_colors = np.zeros((len(indices), 4))
    ordered_colors[types == 0] = [0, 0, 0, 1]  # Black for bg
    # Map the foreground colors according to their original segment index
    ordered_colors[types == 1] = mapped_colors[indices[types == 1]]

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    # 4. Create the LineCollection with your sequenced arrays
    lc = LineCollection(
        ordered_segments,
        colors=ordered_colors,
        linewidths=ordered_linewidths,
        capstyle='round',
        joinstyle='round'
    )

    ax.add_collection(lc)

    ax.set_xlim(min(x) - 0.5, max(x) + 0.5)
    ax.set_ylim(min(y) - 0.5, max(y) + 0.5)
    ax.set_aspect('equal')
    ax.set_xlabel(r'X Position (mm)')
    ax.set_ylabel(r'Y Position (mm)')
    ax.grid(True, linestyle=':', alpha=0.5)

    # Set zorder to ensure markers draw on top of the thick lines
    ax.plot(x[0], y[0], 'ko', markersize=4, label='Start', zorder=5)
    ax.plot(x[-1], y[-1], 'ks', markersize=4, label='End', zorder=5)
    
    # Move the legend outside and above the plot (centered, 2 columns)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.02), ncol=2, frameon=False)

    # Rebuild the colorbar
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(r'Print Sequence $\rightarrow$')

    plt.tight_layout(pad=0.5)
    
    pdf_path = f"{output_name}.pdf"
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight', dpi=300)
    print(f"Extraction complete! Saved figure to {pdf_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Fallback if the user runs it without an argument
        filepath = input("Enter the path to your G-code file: ").strip()
        # Remove quotes if dragged and dropped into terminal
        filepath = filepath.strip("\"'") 
    else:
        filepath = sys.argv[1]
        
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)
        
    print(f"Parsing first layer from {os.path.basename(filepath)}...")
    try:
        x, y = extract_first_layer(filepath)
        print(f"Found {len(x)} coordinates in the first layer. Generating plot...")
        
        # Use the original filename to name the output images
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        plot_toolpath(x, y, output_name=base_name + "_first_layer")
        
    except Exception as e:
        print(f"Failed: {e}")
