import networkx as nx
import numpy as np
import fullcontrol as fc

from unitcell import snake_unit_cell, honeycomb_unit_cell

# ==========================================
# 1. GRAPH ALGORITHMS (Your Logic)
# ==========================================
# (Condensed versions of the robust functions we built)

def create_periodic_multigraph(original_graph, width, height, tolerance=1e-5):
    merge_logic = nx.Graph()
    merge_logic.add_nodes_from(original_graph.nodes())
    nodes = list(original_graph.nodes(data=True))
    for i in range(len(nodes)):
        u, data_u = nodes[i]
        for j in range(i + 1, len(nodes)):
            v, data_v = nodes[j]
            dx, dy = abs(data_u['pos'][0] - data_v['pos'][0]), abs(data_u['pos'][1] - data_v['pos'][1])
            if (((abs(dx - width) < tolerance or dx < tolerance) and 
                 (abs(dy - height) < tolerance or dy < tolerance)) and not (dx < tolerance and dy < tolerance)):
                merge_logic.add_edge(u, v)
    mapping = {}
    for c in nx.connected_components(merge_logic):
        new_id = "_".join(map(str, sorted(list(c))))
        for oid in c: mapping[oid] = new_id
    for n in original_graph.nodes():
        if n not in mapping: mapping[n] = str(n)
    P_G = nx.MultiGraph()
    for u, v, data in original_graph.edges(data=True):
        P_G.add_edge(mapping[u], mapping[v], key=f"{u}-{v}", original_u=u, original_v=v, **data)
    return P_G, mapping

class UnitCellSolver:
    def __init__(self, periodic_graph):
        self.graph = periodic_graph
        self.solutions = []
    def solve(self):
        self._backtrack(0, [], list(self.graph.edges(keys=True, data=True)))
        return self.solutions
    def _backtrack(self, idx, selected, all_edges):
        if not self._valid(selected): return
        if idx == len(all_edges):
            if self._complete(selected): self.solutions.append(list(selected))
            return
        self._backtrack(idx + 1, selected + [all_edges[idx]], all_edges)
        self._backtrack(idx + 1, selected, all_edges)
    def _valid(self, edges):
        d = {}
        for u, v, k, _ in edges:
            d[u] = d.get(u, 0) + 1; d[v] = d.get(v, 0) + 1
            if d[u] > 2 or d[v] > 2: return False
        return True
    def _complete(self, edges):
        d = {n: 0 for n in self.graph.nodes()}
        for u, v, k, _ in edges: d[u] += 1; d[v] += 1
        return all(x == 2 for x in d.values())

def get_valid_solutions(solutions, original_graph, mapping, width, height):
    valid = []
    for sol in solutions:
        sg = nx.MultiGraph()
        edb = {}
        for u, v, k, d in sol:
            sg.add_edge(u, v, key=k)
            edb[(u, v, k)] = d; edb[(v, u, k)] = d
        is_bad = False
        for c in nx.connected_components(sg):
            try: cycle = list(nx.eulerian_circuit(sg.subgraph(c), keys=True))
            except: is_bad = True; break
            wx, wy = 0, 0
            path_seq = []
            for u_m, v_m, k in cycle:
                d = edb[(u_m, v_m, k)]
                u0, v0 = d['original_u'], d['original_v']
                if mapping[u0] == u_m and mapping[v0] == v_m: ps, pe = u0, v0
                elif mapping[v0] == u_m and mapping[u0] == v_m: ps, pe = v0, u0
                else: ps, pe = u0, v0
                path_seq.append((ps, pe))
            for i in range(len(path_seq)):
                curr_s, _ = path_seq[i]
                _, prev_e = path_seq[(i-1)%len(path_seq)]
                if curr_s == prev_e: continue
                p_prev = np.array(original_graph.nodes[prev_e]['pos'])
                p_curr = np.array(original_graph.nodes[curr_s]['pos'])
                if p_curr[0] > p_prev[0] + 1e-4: wx += 1
                elif p_curr[0] < p_prev[0] - 1e-4: wx -= 1
                if p_curr[1] > p_prev[1] + 1e-4: wy += 1
                elif p_curr[1] < p_prev[1] - 1e-4: wy -= 1
            if wx == 0 and wy == 0: is_bad = True; break
        if not is_bad: valid.append(sol)
    return valid

def create_tiled_graph(original_graph, solution, width, height, rows, cols):
    G = nx.Graph()
    for r in range(rows):
        for c in range(cols):
            ox, oy = c * width, r * height
            for _, _, _, d in solution:
                u, v = d['original_u'], d['original_v']
                pu, pv = original_graph.nodes[u]['pos'], original_graph.nodes[v]['pos']
                nu, nv = f"{u}_{r}_{c}", f"{v}_{r}_{c}"
                G.add_node(nu, pos=(pu[0]+ox, pu[1]+oy))
                G.add_node(nv, pos=(pv[0]+ox, pv[1]+oy))
                G.add_edge(nu, nv)
    orig_pos = nx.get_node_attributes(original_graph, 'pos')
    h_pairs = [(u, v) for u, pu in orig_pos.items() for v, pv in orig_pos.items() 
               if abs(pu[0]) < 1e-4 and abs(pv[0]-width) < 1e-4 and abs(pu[1]-pv[1]) < 1e-4]
    v_pairs = [(b, t) for b, pb in orig_pos.items() for t, pt in orig_pos.items() 
               if abs(pb[1]) < 1e-4 and abs(pt[1]-height) < 1e-4 and abs(pb[0]-pt[0]) < 1e-4]
    uf = {n: n for n in G.nodes()}
    def find(n):
        if uf[n] != n: uf[n] = find(uf[n])
        return uf[n]
    def union(n1, n2):
        r1, r2 = find(n1), find(n2)
        if r1 != r2: uf[r2] = r1
    for r in range(rows):
        for c in range(cols):
            if c < cols - 1:
                for l, r_n in h_pairs:
                    n1, n2 = f"{r_n}_{r}_{c}", f"{l}_{r}_{c+1}"
                    if n1 in G and n2 in G: union(n1, n2)
            if r < rows - 1:
                for b, t in v_pairs:
                    n1, n2 = f"{t}_{r}_{c}", f"{b}_{r+1}_{c}"
                    if n1 in G and n2 in G: union(n1, n2)
    final_G = nx.Graph()
    for n in G.nodes():
        root = find(n)
        if root not in final_G: final_G.add_node(root, pos=G.nodes[n]['pos'])
    for u, v in G.edges():
        ru, rv = find(u), find(v)
        if ru != rv: final_G.add_edge(ru, rv)
    return final_G

def robust_connect(grid_graph):
    ports = [n for n, d in grid_graph.degree() if d == 1]
    pos = nx.get_node_attributes(grid_graph, 'pos')
    cands = []
    for i in range(len(ports)):
        for j in range(i+1, len(ports)):
            u, v = ports[i], ports[j]
            dist = np.linalg.norm(np.array(pos[u]) - np.array(pos[v]))
            cands.append((dist, u, v))
    cands.sort(key=lambda x: x[0])
    used = set()
    for _, u, v in cands:
        if u in used or v in used: continue
        if not nx.has_path(grid_graph, u, v):
            grid_graph.add_edge(u, v)
            used.add(u); used.add(v)
    return grid_graph

def graph_to_paths(G):
    paths = []
    for c in [G.subgraph(c).copy() for c in nx.connected_components(G)]:
        start = [n for n, d in c.degree() if d % 2 == 1]
        start = start[0] if start else list(c.nodes())[0]
        ordered = list(nx.dfs_preorder_nodes(c, source=start))
        pos = nx.get_node_attributes(c, 'pos')
        paths.append([pos[n] for n in ordered])
    return paths

# ==========================================
# 2. FULLCONTROL INTEGRATION
# ==========================================
def generate_and_plot(original_graph, valid_solutions, layer_sequence, width, height, grid_rows, grid_cols):
    
    print(f"Generating steps for {len(layer_sequence)} layers...")
    steps = []
    
    # Optional: Add setup G-code (not needed for just plotting)
    # steps.append(fc.ManualGcode(text="; Start of print"))
    
    layer_height = 0.2
    
    # We cache the geometry to avoid re-calculating identical layers
    geometry_cache = {}
    
    for i, sol_idx in enumerate(layer_sequence):
        if sol_idx not in geometry_cache:
            # 1. Tile & Stitch
            tiled = create_tiled_graph(original_graph, valid_solutions[sol_idx], width, height, grid_rows, grid_cols)
            stitched = robust_connect(tiled)
            # 2. Get ordered coordinates
            geometry_cache[sol_idx] = graph_to_paths(stitched)
            
        paths = geometry_cache[sol_idx]
        z_level = (i + 1) * layer_height
        
        for path in paths:
            # Move to start of path (Travel)
            sx, sy = path[0]
            steps.append(fc.Point(x=sx, y=sy, z=z_level))
            
            # Print the path (Extrude)
            steps.append(fc.Extruder(on=True))
            for px, py in path[1:]:
                steps.append(fc.Point(x=px, y=py, z=z_level))
                
            # Turn off extrusion at end of path
            steps.append(fc.Extruder(on=False))
            
    # ==========================================
    # 3. PLOT WITH FULLCONTROL
    # ==========================================
    print("Launching FullControl Plotter...")
    # This generates an interactive HTML plot with sliders for layers/steps
    fc.transform(steps, 'plot')
    
    # To save G-code:
    # gcode_text = fc.transform(steps, 'gcode')
    # with open('lattice.gcode', 'w') as f: f.write(gcode_text)

# ==========================================
# 3. RUN IT
# ==========================================
if __name__ == "__main__":
    # Setup Unit Cell
    W = honeycomb_unit_cell.W
    H = honeycomb_unit_cell.H
    G = honeycomb_unit_cell.graph

    # Solve
    p_G, mapping = create_periodic_multigraph(G, W, H)
    valid_sols = get_valid_solutions(UnitCellSolver(p_G).solve(), G, mapping, W, H)
    
    if valid_sols:
        # Define a sequence (e.g. 5 layers alternating solutions)
        # Use first 3 valid solutions cyclically
        seq = [0, 2, 3]*6 
        
        generate_and_plot(G, valid_sols, seq, W, H, grid_rows=4, grid_cols=5)
    else:
        print("No valid solutions found.")