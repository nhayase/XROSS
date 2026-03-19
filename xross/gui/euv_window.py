"""
xross.gui.euv_window — EUV Optics reflectivity window.
ALL calculations use build_full_stack() which includes every layer
(Orphan and Subroutine) in the exact GUI order (top = surface).
"""
import datetime, os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np, pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from xross.core import reflectivity_matrix

def open_euv_window(root, icon_path, current_dir, subroutines, orphan_layers,
                    log_fn, place_near_root, Cell, Subroutine):

    COL_NAME,COL_N,COL_K,COL_THICK,COL_DENS,COL_ROUGH = range(6)

    def _read_cell(cell):
        n   = float(cell.entries[COL_N].get())
        k   = float(cell.entries[COL_K].get())
        d   = float(cell.entries[COL_THICK].get())
        sig = float(cell.entries[COL_ROUGH].get())
        return (n, k, d, sig)

    def build_full_stack():
        """Build complete layer stack from subroutines list (top→bottom).
        Returns (stack, all_cells) where stack is list of (n,k,d,sigma)."""
        stack = []; all_cells = []
        for obj in subroutines:
            if isinstance(obj, Subroutine):
                rep = max(1, int(obj.loop_count))
                log_fn(f"  Subroutine '{obj.name}' x{rep} ({len(obj.cells)} layers)")
                for _ in range(rep):
                    for c in obj.cells:
                        stack.append(_read_cell(c)); all_cells.append(c)
            elif isinstance(obj, Cell):
                nm = (obj.entries[COL_NAME].get() or "").strip()
                log_fn(f"  Layer '{nm}' (orphan)")
                stack.append(_read_cell(obj)); all_cells.append(obj)
        log_fn(f"Stack total: {len(stack)} layers")
        return stack, all_cells

    def _get_sub_info():
        """Get first Subroutine's pair template for Pairs scan."""
        for obj in subroutines:
            if isinstance(obj, Subroutine):
                tpl = [_read_cell(c) for c in obj.cells]
                return tpl, max(1, int(obj.loop_count)), obj.cells
        # No Subroutine: treat all as single pair
        stack, cells = build_full_stack()
        return stack, 1, cells

    def perform_calculation():
        Vac = (1.0, 0.0, 0.0, 0.0)

        # Phase (Zeff)
        if var_phase.get():
            if any((var_pairs.get(), var_wl.get(), var_aoi.get(), var_dx.get())):
                return
            try:
                stack, _ = build_full_stack()
            except ValueError as err:
                messagebox.showerror("Model error", str(err)); return
            if len(stack) < 2:
                messagebox.showerror("Model error", "At least two layers required."); return
            try:
                lam_nm = float(wavelength_var.get())
                a_s    = float(aoi_start_var.get())
                a_e    = float(aoi_end_var.get())
                if a_s >= a_e: raise ValueError
            except ValueError:
                messagebox.showerror("Input error", "AOI start / AOI end"); return
            aoi = np.linspace(a_s, a_e, 200)
            phase = [reflectivity_matrix(stack, lam_nm, a)[1] for a in aoi]
            phase = np.unwrap(phase)
            fig = Figure(figsize=(5,4), dpi=100); ax = fig.add_subplot(111)
            ax.plot(aoi, phase, marker='o')
            ax.set_xlabel("AOI (deg)"); ax.set_ylabel("Phase (rad)"); ax.grid()
            _show_graph(fig, "Phase")
            df = pd.DataFrame({"AOI(deg)": aoi, "Phase(rad)": phase})
            _save_csv(df, "phase")
            return

        # Reflectivity
        try:
            stack, all_cells = build_full_stack()
        except ValueError as err:
            messagebox.showerror("Model error", str(err)); return
        if len(stack) < 2:
            messagebox.showerror("Model error", "At least two layers required."); return

        if var_pairs.get() or var_wl.get() or var_aoi.get():
            try:
                lam_nm  = float(wavelength_var.get())
                inc_deg = float(angle_var.get())
            except ValueError:
                messagebox.showerror("Input error", "Wavelength / Angle"); return
            plot_marker = 'o'

            # Pairs scan (uses Subroutine repeat count)
            if var_pairs.get():
                pair_tpl, n_pairs, _ = _get_sub_info()
                # Collect non-subroutine layers (orphans before and after)
                pre = []; post = []; found_sub = False
                for obj in subroutines:
                    if isinstance(obj, Subroutine):
                        found_sub = True
                    elif isinstance(obj, Cell):
                        if not found_sub: pre.append(_read_cell(obj))
                        else: post.append(_read_cell(obj))
                x = list(range(1, n_pairs+1))
                y = []
                for m in x:
                    full = pre + pair_tpl * m + post
                    y.append(reflectivity_matrix(full, lam_nm, inc_deg)[0]*100)
                xlabel, fname_tag = "Pairs", "pairs"

            # Wavelength scan (uses full stack, interpolates nk)
            elif var_wl.get():
                # Check nk data for all cells
                if not all(getattr(c, "nk_data", None) is not None for c in all_cells):
                    messagebox.showerror("nk required", "Load nk file for ALL layers."); return
                try:
                    lam_s = float(lam_start_var.get()); lam_e = float(lam_end_var.get())
                    if lam_s <= 0 or lam_e <= 0 or lam_s >= lam_e: raise ValueError
                except ValueError:
                    messagebox.showerror("Input error", "λ start / λ end"); return
                n_layer = len(all_cells)
                lam_mins = [float(np.min(c.nk_data["lam_nm"])) for c in all_cells]
                lam_maxs = [float(np.max(c.nk_data["lam_nm"])) for c in all_cells]
                eval_lo = max(lam_s, max(lam_mins)); eval_hi = min(lam_e, min(lam_maxs))
                if eval_lo >= eval_hi:
                    messagebox.showerror("Range error", "λ range outside nk data."); return
                NPTS = 600
                x_uniform = np.linspace(eval_lo, eval_hi, NPTS)
                specials = []
                for c in all_cells:
                    la = np.asarray(c.nk_data["lam_nm"], float)
                    specials.append(la[(la >= eval_lo) & (la <= eval_hi)])
                specials = np.concatenate(specials) if specials else np.array([], float)
                x = np.unique(np.round(np.concatenate([x_uniform, specials]), 12))
                x = x[(x >= eval_lo) & (x <= eval_hi)]
                n_interp = [np.interp(x, np.asarray(c.nk_data["lam_nm"], float),
                                         np.asarray(c.nk_data["n"], float)) for c in all_cells]
                k_interp = [np.interp(x, np.asarray(c.nk_data["lam_nm"], float),
                                         np.asarray(c.nk_data["k"], float)) for c in all_cells]
                y = []
                for i, lam in enumerate(x):
                    s = [(float(n_interp[j][i]), float(k_interp[j][i]),
                          stack[j][2], stack[j][3]) for j in range(n_layer)]
                    R = reflectivity_matrix(s, float(lam), inc_deg)[0] * 100.0
                    y.append(R)
                xlabel, fname_tag = "Wavelength (nm)", "wl_linear_nk"
                plot_marker = None

            # AOI scan (full stack)
            else:
                try:
                    a_s, a_e = float(aoi_start_var.get()), float(aoi_end_var.get())
                    if a_s >= a_e: raise ValueError
                except ValueError:
                    messagebox.showerror("Input error", "AOI start / end"); return
                x = np.linspace(a_s, a_e, 200)
                y = [reflectivity_matrix(stack, lam_nm, a)[0]*100 for a in x]
                xlabel, fname_tag = "AOI (deg)", "aoi"

            df = pd.DataFrame({xlabel: x, "Reflectivity(%)": y})
            fig = Figure(figsize=(5,4), dpi=100); ax = fig.add_subplot(111)
            if plot_marker is None: ax.plot(x, y, lw=1.5)
            else: ax.plot(x, y, marker=plot_marker)
            ax.set_xlabel(xlabel); ax.set_ylabel("Reflectivity (%)"); ax.grid()

        # Heatmap (full stack, vary first two layer thicknesses)
        elif var_dx.get():
            try:
                lam_nm  = float(wavelength_var.get()); inc_deg = float(angle_var.get())
                dx0, dx1 = float(dx_start_var.get()), float(dx_end_var.get())
                dy0, dy1 = float(dy_start_var.get()), float(dy_end_var.get())
                if lam_nm<=0 or dx0<=0 or dy0<=0 or dx0>=dx1 or dy0>=dy1: raise ValueError
            except ValueError:
                messagebox.showerror("Input error", "λ / d_x, d_y Range"); return
            if len(stack) < 2:
                messagebox.showerror("Error", "Need ≥2 layers for heatmap."); return
            n_mesh = 60
            dx_vec = np.linspace(dx0, dx1, n_mesh); dy_vec = np.linspace(dy0, dy1, n_mesh)
            z = np.zeros((n_mesh, n_mesh))
            lx = all_cells[0].entries[COL_NAME].get().strip() or "dx"
            ly = all_cells[1].entries[COL_NAME].get().strip() or "dy"
            for iy, dy in enumerate(dy_vec):
                for ix, dx in enumerate(dx_vec):
                    s_mod = list(stack)
                    n0, k0, _, s0 = s_mod[0]; s_mod[0] = (n0, k0, dx, s0)
                    n1, k1, _, s1 = s_mod[1]; s_mod[1] = (n1, k1, dy, s1)
                    z[iy, ix] = reflectivity_matrix(s_mod, lam_nm, inc_deg)[0]*100
            records = [[dx_vec[ix], dy_vec[iy], z[iy,ix]] for iy in range(n_mesh) for ix in range(n_mesh)]
            df = pd.DataFrame(records, columns=[f"{lx} (nm)", f"{ly} (nm)", "Reflectivity (%)"])
            fname_tag = "heatmap"
            fig = Figure(figsize=(5.4,4.4), dpi=100); ax = fig.add_subplot(111)
            im = ax.imshow(z, origin="lower", aspect="auto",
                           extent=[dx_vec[0], dx_vec[-1], dy_vec[0], dy_vec[-1]], cmap="viridis")
            ax.set_xlabel(f"{lx} (nm)"); ax.set_ylabel(f"{ly} (nm)")
            fig.colorbar(im, ax=ax).set_label("Reflectivity (%)")
        else:
            messagebox.showinfo("Info", "Select a scan type."); return

        _show_graph(fig, fname_tag)
        _save_csv(df, fname_tag)

    def _show_graph(fig, title):
        gwin = tk.Toplevel(root)
        if icon_path and os.path.exists(icon_path):
            try: gwin.iconbitmap(icon_path)
            except: pass
        gwin.title("EUV Optics Graphics"); place_near_root(gwin)
        cvs = FigureCanvasTkAgg(fig, master=gwin); cvs.draw()
        cvs.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs, gwin)

    def _save_csv(df, fname_tag):
        save_dir = os.path.join(current_dir, "save"); os.makedirs(save_dir, exist_ok=True)
        default = datetime.datetime.now().strftime(f"%Y%m%d_%H%M%S_{fname_tag}.csv")
        path = filedialog.asksaveasfilename(initialdir=save_dir, defaultextension=".csv",
                                            initialfile=default, filetypes=[("CSV files","*.csv")])
        if path:
            df.to_csv(path, index=False)
            log_fn(f"{fname_tag.upper()} saved: {path}")

    def open_multi_csv():
        save_dir = os.path.join(current_dir, "save"); os.makedirs(save_dir, exist_ok=True)
        paths = filedialog.askopenfilenames(title="Select CSV files", initialdir=save_dir, filetypes=[("CSV files", "*.csv")])
        if not paths: return
        try:
            dfs = []; header_list = []; ncols_set = set()
            for p in paths:
                d = pd.read_csv(p)
                if d.shape[1] < 2: messagebox.showerror("Error", f"'{os.path.basename(p)}' has <2 columns."); return
                dfs.append((p, d)); header_list.append(tuple(map(str, d.columns.tolist()))); ncols_set.add(len(d.columns))
            if len(ncols_set) != 1: messagebox.showerror("Error", "All files must have same column count."); return
            n_cols = next(iter(ncols_set)); ref_headers = header_list[0]
            if n_cols == 2:
                xcol, ycol = ref_headers
                mwin = tk.Toplevel(root); mwin.title("EUV Multi-CSV"); place_near_root(mwin)
                fig = Figure(figsize=(5.8, 4.4), dpi=100); ax = fig.add_subplot(111)
                for p, d in dfs:
                    xv = pd.to_numeric(d[xcol], errors="coerce"); yv = pd.to_numeric(d[ycol], errors="coerce")
                    mask = xv.notna() & yv.notna()
                    if mask.any(): ax.plot(xv[mask].to_numpy(), yv[mask].to_numpy(), lw=1.4, label=os.path.basename(p))
                ax.set_xlabel(xcol); ax.set_ylabel(ycol); ax.grid(True, alpha=.35); ax.legend(loc="best", fontsize=8)
                cvs = FigureCanvasTkAgg(fig, master=mwin); cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)
                NavigationToolbar2Tk(cvs, mwin)
            elif n_cols == 3:
                xcol, ycol, zcol = ref_headers
                mwin = tk.Toplevel(root); mwin.title("EUV Multi-CSV (Heatmaps)"); place_near_root(mwin)
                nb = ttk.Notebook(mwin); nb.pack(fill="both", expand=True)
                for p, d in dfs:
                    tab = ttk.Frame(nb); nb.add(tab, text=os.path.basename(p))
                    xv = pd.to_numeric(d[xcol], errors="coerce"); yv = pd.to_numeric(d[ycol], errors="coerce"); zv = pd.to_numeric(d[zcol], errors="coerce")
                    mask = xv.notna() & yv.notna() & zv.notna()
                    xv, yv, zv = xv[mask].to_numpy(), yv[mask].to_numpy(), zv[mask].to_numpy()
                    if xv.size == 0: tk.Label(tab, text="No data.").pack(); continue
                    xu = np.unique(np.round(xv, 12)); yu = np.unique(np.round(yv, 12))
                    if xu.size < 2 or yu.size < 2: tk.Label(tab, text="Not enough data.").pack(); continue
                    Z = np.full((len(yu), len(xu)), np.nan, float)
                    lut = {(round(xi,12), round(yi,12)): zi for xi,yi,zi in zip(xv,yv,zv)}
                    for iy, yy in enumerate(yu):
                        for ix, xx in enumerate(xu): Z[iy,ix] = lut.get((round(xx,12), round(yy,12)), np.nan)
                    fig = Figure(figsize=(5.8, 4.4), dpi=100); ax = fig.add_subplot(111)
                    im = ax.imshow(Z, origin="lower", aspect="auto", extent=[xu[0],xu[-1],yu[0],yu[-1]])
                    ax.set_xlabel(xcol); ax.set_ylabel(ycol); fig.colorbar(im, ax=ax).set_label(zcol)
                    cvs = FigureCanvasTkAgg(fig, master=tab); cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)
                    NavigationToolbar2Tk(cvs, tab)
            else: messagebox.showerror("Error", "Only 2 or 3 column CSVs.")
        except Exception as e: messagebox.showerror("Multi-CSV error", str(e))

    # ---- Window layout ----
    win = tk.Toplevel(root)
    if icon_path and os.path.exists(icon_path):
        try: win.iconbitmap(icon_path)
        except: pass
    win.title("EUV Optics Window"); win.geometry("500x280"); place_near_root(win)
    ctrl = tk.LabelFrame(win, text="Parameters", padx=6, pady=6); ctrl.pack(fill="x", padx=8, pady=(10, 4))
    tk.Button(ctrl, text="Calculation", width=12, bg="#5cb85c", fg="white",
              command=perform_calculation).grid(row=0, column=4, padx=(20, 4))
    tk.Button(ctrl, text="Multi-CSV", width=12, bg="#5bc0de", fg="white",
              command=open_multi_csv).grid(row=1, column=4, padx=(20, 4))
    tk.Label(ctrl, text="Angle of incidence (deg)").grid(row=0, column=0, sticky="e")
    angle_var = tk.DoubleVar(value=6.0)
    tk.Entry(ctrl, textvariable=angle_var, width=8).grid(row=0, column=1, padx=(2, 12))
    tk.Label(ctrl, text="Wavelength (nm)").grid(row=0, column=2, sticky="e")
    wavelength_var = tk.DoubleVar(value=13.5)
    tk.Entry(ctrl, textvariable=wavelength_var, width=8).grid(row=0, column=3, padx=2)
    tk.Label(ctrl, text="λ start (nm)").grid(row=1, column=0, sticky="e")
    lam_start_var = tk.DoubleVar(value=12.5)
    tk.Entry(ctrl, textvariable=lam_start_var, width=8).grid(row=1, column=1, padx=(2, 12))
    tk.Label(ctrl, text="λ end (nm)").grid(row=1, column=2, sticky="e")
    lam_end_var = tk.DoubleVar(value=14.5)
    tk.Entry(ctrl, textvariable=lam_end_var, width=8).grid(row=1, column=3, padx=2)
    tk.Label(ctrl, text="AOI start (deg)").grid(row=2, column=0, sticky="e")
    aoi_start_var = tk.DoubleVar(value=0)
    tk.Entry(ctrl, textvariable=aoi_start_var, width=8).grid(row=2, column=1, padx=(2, 12))
    tk.Label(ctrl, text="AOI end (deg)").grid(row=2, column=2, sticky="e")
    aoi_end_var = tk.DoubleVar(value=40.0)
    tk.Entry(ctrl, textvariable=aoi_end_var, width=8).grid(row=2, column=3, padx=2)
    tk.Label(ctrl, text="dx start (nm)").grid(row=3, column=0, sticky="e")
    dx_start_var = tk.DoubleVar(value=1.0)
    tk.Entry(ctrl, textvariable=dx_start_var, width=8).grid(row=3, column=1, padx=(2, 12))
    tk.Label(ctrl, text="dx end (nm)").grid(row=3, column=2, sticky="e")
    dx_end_var = tk.DoubleVar(value=5.0)
    tk.Entry(ctrl, textvariable=dx_end_var, width=8).grid(row=3, column=3, padx=2)
    tk.Label(ctrl, text="dy start (nm)").grid(row=4, column=0, sticky="e")
    dy_start_var = tk.DoubleVar(value=1.0)
    tk.Entry(ctrl, textvariable=dy_start_var, width=8).grid(row=4, column=1, padx=(2, 12))
    tk.Label(ctrl, text="dy end (nm)").grid(row=4, column=2, sticky="e")
    dy_end_var = tk.DoubleVar(value=5.0)
    tk.Entry(ctrl, textvariable=dy_end_var, width=8).grid(row=4, column=3, padx=2)
    tk.Label(win, text="Fulfill parameters & Click the Calculation button", font=("Arial", 10)).pack(pady=(8, 4))
    opt_frame = tk.Frame(win); opt_frame.pack(pady=(0, 8))
    var_pairs = tk.BooleanVar(); var_wl = tk.BooleanVar(); var_aoi = tk.BooleanVar(); var_dx = tk.BooleanVar()
    tk.Checkbutton(opt_frame, text="Pairs scan",      variable=var_pairs).pack(side="left", padx=10)
    tk.Checkbutton(opt_frame, text="Wavelength scan", variable=var_wl).pack(side="left", padx=10)
    tk.Checkbutton(opt_frame, text="AOI scan",        variable=var_aoi).pack(side="left", padx=10)
    tk.Checkbutton(opt_frame, text="Heatmap",         variable=var_dx).pack(side="left", padx=10)
    opt2_frame = tk.Frame(win); opt2_frame.pack(pady=(0, 10))
    var_phase = tk.BooleanVar()
    tk.Checkbutton(opt2_frame, text="Phase (Zeff)", variable=var_phase).pack(side="left", padx=10)
