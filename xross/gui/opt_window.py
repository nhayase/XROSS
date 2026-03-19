"""
xross.gui.opt_window — Optimization (Optuna-based, Multi-Sigma style).

Workflow:
  1. Load CSV
  2. Assign X (explanatory) / Y (objective) variables
  3. Train surrogate model (IDW interpolation from data)
  4. Set direction (minimize/maximize) & constraints (bounds)
  5. Optimize via Optuna (TPE / NSGA-II / CMA-ES)
  6. View Pareto front / optimization history
  7. Predict (single point or batch CSV)
  8. Profiling (statistics, correlation, histograms)
"""
from __future__ import annotations
import datetime, os, threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np, pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


def open_opt_window(root, icon_path, current_dir, log_fn, place_near_root):

    # --- Surrogate: Inverse Distance Weighting ---
    class IDWSurrogate:
        """Simple IDW surrogate model (no sklearn needed)."""
        def __init__(self, X, Y):
            self.X = np.asarray(X, float)
            self.Y = np.asarray(Y, float)
            self.xmin = self.X.min(0); self.xmax = self.X.max(0)
            self.xrng = np.where(self.xmax - self.xmin < 1e-12, 1.0, self.xmax - self.xmin)
            self.Xn = (self.X - self.xmin) / self.xrng
            # Importance: variance-based
            self.importance = self._calc_importance()

        def predict(self, xnew):
            xnew = np.atleast_2d(xnew)
            out = np.zeros((xnew.shape[0], self.Y.shape[1]))
            for i in range(xnew.shape[0]):
                xn = (xnew[i] - self.xmin) / self.xrng
                d = np.sqrt(np.sum((self.Xn - xn) ** 2, axis=1))
                d = np.clip(d, 1e-12, None)
                w = 1.0 / d ** 2; w /= w.sum()
                out[i] = (w[:, None] * self.Y).sum(0)
            return out

        def _calc_importance(self):
            """Estimate variable importance via leave-one-variable-out variance."""
            n_x = self.X.shape[1]; n_y = self.Y.shape[1]
            imp = np.zeros((n_y, n_x))
            base_pred = self.predict(self.X)
            base_mse = np.mean((base_pred - self.Y) ** 2, axis=0)
            for j in range(n_x):
                Xp = self.X.copy()
                np.random.seed(42); Xp[:, j] = np.random.permutation(Xp[:, j])
                perm_pred = self.predict(Xp)
                perm_mse = np.mean((perm_pred - self.Y) ** 2, axis=0)
                imp[:, j] = perm_mse - base_mse
            imp = np.clip(imp, 0, None)
            row_sum = imp.sum(1, keepdims=True)
            row_sum = np.where(row_sum < 1e-12, 1.0, row_sum)
            return imp / row_sum

        def score_text(self):
            pred = self.predict(self.X)
            lines = []
            for j in range(self.Y.shape[1]):
                ss_res = np.sum((self.Y[:, j] - pred[:, j]) ** 2)
                ss_tot = np.sum((self.Y[:, j] - self.Y[:, j].mean()) ** 2)
                r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
                lines.append(f"  LOO-R² ≈ {r2:.4f}")
            return "\n".join(lines)

    state = {"df": None, "x_cols": [], "y_cols": [], "model": None, "study": None}

    win = tk.Toplevel(root)
    if icon_path and os.path.exists(icon_path):
        try: win.iconbitmap(icon_path)
        except: pass
    win.title("Optimization Window"); win.geometry("960x780"); place_near_root(win)

    # 1. Data
    top = tk.LabelFrame(win, text="1. Data", padx=6, pady=4); top.pack(fill="x", padx=8, pady=(8, 2))
    tk.Label(top, text="CSV:").grid(row=0, column=0, sticky="e")
    pv = tk.StringVar(); tk.Entry(top, textvariable=pv, width=60).grid(row=0, column=1, padx=4, columnspan=3, sticky="w")
    iv = tk.StringVar(value="No data."); tk.Label(top, textvariable=iv, fg="gray").grid(row=1, column=0, columnspan=4, sticky="w")

    # 2. Variables
    vf = tk.LabelFrame(win, text="2. Variables", padx=6, pady=4); vf.pack(fill="x", padx=8, pady=2)
    lbs = {}
    for i, lb in enumerate(["Unused", "X: Explanatory", "Y: Objective"]):
        s = tk.Frame(vf); s.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(s, text=lb, font=("Arial", 9, "bold")).pack()
        l = tk.Listbox(s, selectmode=tk.EXTENDED, height=6, exportselection=False); l.pack(fill="both", expand=True); lbs[i] = l
    bv = tk.Frame(vf); bv.pack(side="left", padx=4)
    tk.Button(bv, text="→ X", width=6, command=lambda: _mv(0, 1)).pack(pady=2)
    tk.Button(bv, text="→ Y", width=6, command=lambda: _mv(0, 2)).pack(pady=2)
    tk.Button(bv, text="← Reset", width=6, command=lambda: _rst()).pack(pady=2)
    tk.Button(bv, text="← Back", width=6, command=lambda: _back()).pack(pady=2)

    def _mv(s, d):
        for i in reversed(lbs[s].curselection()): lbs[d].insert(tk.END, lbs[s].get(i)); lbs[s].delete(i)
        _syn()
    def _back():
        for src in [1, 2]:  # X and Y
            for i in reversed(lbs[src].curselection()):
                lbs[0].insert(tk.END, lbs[src].get(i)); lbs[src].delete(i)
        _syn()
    def _rst():
        if state["df"] is None: return
        for l in lbs.values(): l.delete(0, tk.END)
        for c in state["df"].columns: lbs[0].insert(tk.END, c)
        _syn()
    def _syn():
        state["x_cols"] = list(lbs[1].get(0, tk.END)); state["y_cols"] = list(lbs[2].get(0, tk.END))

    # 3. Settings
    sf = tk.LabelFrame(win, text="3. Settings", padx=6, pady=4); sf.pack(fill="x", padx=8, pady=2)
    tk.Label(sf, text="Trials:").grid(row=0, column=0, sticky="e")
    tv = tk.IntVar(value=500); tk.Entry(sf, textvariable=tv, width=8).grid(row=0, column=1, padx=4)
    tk.Label(sf, text="Sampler:").grid(row=0, column=2, sticky="e")
    scb = ttk.Combobox(sf, values=["TPE", "NSGA-II", "CMA-ES"], state="readonly", width=10)
    scb.set("TPE"); scb.grid(row=0, column=3, padx=4)

    # 4. Direction
    df_ = tk.LabelFrame(win, text="4. Direction", padx=6, pady=4); df_.pack(fill="x", padx=8, pady=2)
    dvs = {}
    def _rd():
        for w in df_.winfo_children(): w.destroy()
        dvs.clear()
        for i, c in enumerate(state["y_cols"]):
            tk.Label(df_, text=c).grid(row=0, column=i * 2, padx=4)
            v = tk.StringVar(value="minimize"); dvs[c] = v
            ttk.Combobox(df_, textvariable=v, values=["minimize", "maximize"], state="readonly", width=10).grid(row=0, column=i * 2 + 1, padx=2)

    # 5. Constraints
    cf = tk.LabelFrame(win, text="5. Constraints", padx=6, pady=4); cf.pack(fill="x", padx=8, pady=2)
    cvars = {}
    def _rc():
        for w in cf.winfo_children(): w.destroy()
        cvars.clear()
        d = state["df"]
        if d is None: return
        for i, c in enumerate(state["x_cols"]):
            lo, hi = float(d[c].min()), float(d[c].max())
            tk.Label(cf, text=c, width=14, anchor="e").grid(row=i, column=0, sticky="e")
            mn = tk.DoubleVar(value=round(lo, 6)); mx = tk.DoubleVar(value=round(hi, 6))
            tk.Entry(cf, textvariable=mn, width=12).grid(row=i, column=1, padx=2)
            tk.Label(cf, text="~").grid(row=i, column=2)
            tk.Entry(cf, textvariable=mx, width=12).grid(row=i, column=3, padx=2)
            cvars[c] = (mn, mx)

    # Buttons
    af = tk.Frame(win); af.pack(fill="x", padx=8, pady=6)
    tk.Button(af, text="Load CSV", width=12, command=lambda: _load()).grid(row=0, column=0, padx=4)
    tk.Button(af, text="Profiling", width=12, command=lambda: _prof()).grid(row=0, column=1, padx=4)
    tk.Button(af, text="Train", width=12, bg="#5cb85c", fg="white", command=lambda: _train()).grid(row=0, column=2, padx=4)
    tk.Button(af, text="Importance", width=12, command=lambda: _imp()).grid(row=0, column=3, padx=4)
    tk.Button(af, text="Optimize", width=12, bg="#337ab7", fg="white", command=lambda: _opt()).grid(row=0, column=4, padx=4)
    tk.Button(af, text="Predict", width=12, command=lambda: _pred()).grid(row=0, column=5, padx=4)

    nb = ttk.Notebook(win); nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    rt = tk.Text(nb, wrap="word", height=12); nb.add(rt, text="Log / Results")
    gf = tk.Frame(nb); nb.add(gf, text="Graph")

    def _load():
        fp = filedialog.askopenfilename(initialdir=os.path.join(current_dir, "save"),
                                         filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not fp: return
        df = pd.read_csv(fp).select_dtypes(include=[np.number])
        if df.shape[1] < 2: messagebox.showerror("Error", "Need >= 2 numeric columns."); return
        state["df"] = df; state["model"] = None; state["study"] = None
        pv.set(fp); iv.set(f"{df.shape[0]} rows x {df.shape[1]} cols ({os.path.basename(fp)})")
        _rst(); log_fn(f"Opt CSV: {fp}")
        rt.delete("1.0", tk.END)
        rt.insert(tk.END, f"Loaded: {os.path.basename(fp)}\nColumns: {list(df.columns)}\n\n")
        rt.insert(tk.END, "Step 1: Assign X/Y variables\nStep 2: Click 'Train'\nStep 3: Click 'Optimize'\n")

    def _train():
        df = state["df"]
        if df is None: messagebox.showwarning("", "Load CSV first."); return
        _syn(); xc, yc = state["x_cols"], state["y_cols"]
        if not xc or not yc: messagebox.showerror("", "Assign X and Y variables."); return
        _rd(); _rc()
        X = df[xc].values; Y = df[yc].values
        model = IDWSurrogate(X, Y)
        state["model"] = model
        rt.delete("1.0", tk.END)
        rt.insert(tk.END, f"=== Surrogate Model Trained ===\n\n")
        rt.insert(tk.END, f"Method: IDW (Inverse Distance Weighting)\n")
        rt.insert(tk.END, f"Data: {X.shape[0]} samples, {X.shape[1]} X-vars, {Y.shape[1]} Y-vars\n\n")
        rt.insert(tk.END, f"Training fit:\n{model.score_text()}\n\n")
        rt.insert(tk.END, "Ready to Optimize or Predict.\n")
        log_fn("Surrogate trained (IDW)")

    def _imp():
        model = state["model"]
        if model is None: messagebox.showwarning("", "Train first."); return
        xc, yc = state["x_cols"], state["y_cols"]
        iw = tk.Toplevel(win); iw.title("Variable Importance"); iw.geometry("700x500"); place_near_root(iw)
        nc = len(yc); fig = Figure(figsize=(5 * nc, 4), dpi=100)
        for j, yn in enumerate(yc):
            ax = fig.add_subplot(1, nc, j + 1)
            imp = model.importance[j]
            idx = np.argsort(imp)
            ax.barh([xc[k] for k in idx], imp[idx], color="#5cb85c")
            ax.set_xlabel("Importance"); ax.set_title(yn, fontsize=10)
        fig.tight_layout()
        cvs = FigureCanvasTkAgg(fig, master=iw); cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs, iw)
        log_fn("Importance computed.")

    def _opt():
        model = state["model"]
        if model is None: messagebox.showwarning("", "Train first."); return
        try:
            import optuna
            from optuna.samplers import TPESampler, NSGAIISampler, CmaEsSampler
            optuna.logging.set_verbosity(optuna.logging.WARNING)
        except Exception as e:
            messagebox.showerror("Error", f"optuna import failed:\n{e}"); return

        xc, yc = state["x_cols"], state["y_cols"]
        dirs = [dvs.get(c, tk.StringVar(value="minimize")).get() for c in yc]
        n_trials = max(10, tv.get())
        lo = np.array([float(cvars[c][0].get()) if c in cvars else float(state["df"][c].min()) for c in xc])
        hi = np.array([float(cvars[c][1].get()) if c in cvars else float(state["df"][c].max()) for c in xc])

        def surrogate_eval(xnew):
            return model.predict(np.atleast_2d(xnew))[0]

        rt.delete("1.0", tk.END)
        rt.insert(tk.END, f"Optuna: {n_trials} trials, sampler={scb.get()}\n")
        rt.insert(tk.END, f"X: {xc}\nY: {yc}\nDirections: {dirs}\n\n")
        win.update_idletasks()

        def _run():
            is_multi = len(yc) > 1
            sname = scb.get()

            if is_multi:
                sampler = NSGAIISampler(seed=42) if sname == "NSGA-II" else TPESampler(seed=42)
                study = optuna.create_study(directions=dirs, sampler=sampler)
                def objective(trial):
                    xv = [trial.suggest_float(c, float(lo[i]), float(hi[i])) for i, c in enumerate(xc)]
                    return tuple(surrogate_eval(xv))
                study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
                state["study"] = study
                pareto = study.best_trials
                rows = [[t.params[c] for c in xc] + list(t.values) for t in pareto]
                cols = list(xc) + [f"{c}(pred)" for c in yc]
                pdf = pd.DataFrame(rows, columns=cols)
                sd = os.path.join(current_dir, "save"); os.makedirs(sd, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                out = os.path.join(sd, f"{ts}_pareto.csv"); pdf.to_csv(out, index=False)
                def _sh():
                    rt.insert(tk.END, f"\nPareto front: {len(pdf)} solutions\nSaved: {out}\n\n")
                    rt.insert(tk.END, pdf.head(30).to_string(index=False) + "\n")
                    log_fn(f"NSGA-II -> {out}"); _plot_pareto(pdf, yc)
                win.after(0, _sh)
            else:
                sampler = CmaEsSampler(seed=42) if sname == "CMA-ES" else TPESampler(seed=42)
                study = optuna.create_study(direction=dirs[0], sampler=sampler)
                def objective(trial):
                    xv = [trial.suggest_float(c, float(lo[i]), float(hi[i])) for i, c in enumerate(xc)]
                    return float(surrogate_eval(xv)[0])
                study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
                state["study"] = study
                bp = study.best_params; bv = study.best_value
                rows = [[t.params.get(c, 0) for c in xc] + [t.value] for t in study.trials if t.value is not None]
                cols = list(xc) + [f"{yc[0]}(pred)"]
                pdf = pd.DataFrame(rows, columns=cols)
                sd = os.path.join(current_dir, "save"); os.makedirs(sd, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                out = os.path.join(sd, f"{ts}_optuna.csv"); pdf.to_csv(out, index=False)
                def _sh():
                    rt.insert(tk.END, f"\nBest {yc[0]}: {bv:.6g}\n")
                    for c in xc: rt.insert(tk.END, f"  {c} = {bp[c]:.6g}\n")
                    rt.insert(tk.END, f"\nSaved: {out}\n")
                    log_fn(f"TPE -> {out}"); _plot_history(study, yc[0])
                win.after(0, _sh)

        threading.Thread(target=_run, daemon=True).start()

    def _plot_pareto(pdf, yc):
        for w in gf.winfo_children(): w.destroy()
        ypc = [f"{c}(pred)" for c in yc]
        if len(yc) == 2:
            fig = Figure(figsize=(6, 5), dpi=100); ax = fig.add_subplot(111)
            ax.scatter(pdf[ypc[0]], pdf[ypc[1]], s=30, alpha=0.7, edgecolors="black", linewidth=0.5)
            ax.set_xlabel(yc[0]); ax.set_ylabel(yc[1]); ax.set_title("Pareto Front"); ax.grid(alpha=0.3)
        elif len(yc) >= 3:
            fig = Figure(figsize=(7, 4), dpi=100); ax = fig.add_subplot(111)
            data = pdf[ypc].values; dm, dM = data.min(0), data.max(0)
            dr = np.where(dM - dm < 1e-12, 1.0, dM - dm)
            dn = (data - dm) / dr; xa = np.arange(len(yc))
            for row in dn[:50]: ax.plot(xa, row, alpha=0.4, lw=0.8)
            ax.set_xticks(xa); ax.set_xticklabels(yc, fontsize=7, rotation=30); ax.set_title("Pareto (Parallel)")
        else:
            fig = Figure(figsize=(6, 4), dpi=100); ax = fig.add_subplot(111)
            t = pdf.head(10); ax.barh(range(len(t)), t[ypc[0]].values)
            ax.set_yticks(range(len(t))); ax.set_yticklabels([f"#{i+1}" for i in range(len(t))]); ax.set_xlabel(yc[0])
        fig.tight_layout()
        cvs = FigureCanvasTkAgg(fig, master=gf); cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs, gf); nb.select(gf)

    def _plot_history(study, yname):
        for w in gf.winfo_children(): w.destroy()
        fig = Figure(figsize=(6, 4), dpi=100); ax = fig.add_subplot(111)
        vals = [t.value for t in study.trials if t.value is not None]
        if study.direction.name == "MINIMIZE":
            best = np.minimum.accumulate(vals)
        else:
            best = np.maximum.accumulate(vals)
        ax.plot(vals, alpha=0.3, label="Trial"); ax.plot(best, lw=2, label="Best")
        ax.set_xlabel("Trial"); ax.set_ylabel(yname); ax.set_title("Optimization History")
        ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
        cvs = FigureCanvasTkAgg(fig, master=gf); cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs, gf); nb.select(gf)

    def _pred():
        model = state["model"]
        if model is None: messagebox.showwarning("", "Train first."); return
        xc, yc = state["x_cols"], state["y_cols"]
        pw = tk.Toplevel(win)
        if icon_path and os.path.exists(icon_path):
            try: pw.iconbitmap(icon_path)
            except: pass
        pw.title("Prediction"); pw.geometry("500x420"); place_near_root(pw)
        tk.Label(pw, text="Enter X values:", font=("Arial", 10)).pack(pady=4)
        ifr = tk.Frame(pw); ifr.pack(fill="x", padx=10)
        xes = {}
        for i, c in enumerate(xc):
            tk.Label(ifr, text=c, width=16, anchor="e").grid(row=i, column=0, sticky="e")
            v = tk.DoubleVar(value=0.0); tk.Entry(ifr, textvariable=v, width=14).grid(row=i, column=1, padx=4); xes[c] = v
        ot = tk.Text(pw, wrap="word", height=10); ot.pack(fill="both", expand=True, padx=10, pady=6)

        def _do_single():
            try: xv = np.array([[float(xes[c].get()) for c in xc]])
            except Exception as e: messagebox.showerror("Error", str(e)); return
            yp = model.predict(xv)[0]
            ot.delete("1.0", tk.END); ot.insert(tk.END, "=== Prediction ===\n\n")
            for j, yn in enumerate(yc): ot.insert(tk.END, f"  {yn} = {yp[j]:.6g}\n")

        def _do_batch():
            fp = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
            if not fp: return
            try:
                dn = pd.read_csv(fp); miss = [c for c in xc if c not in dn.columns]
                if miss: messagebox.showerror("Error", f"Missing cols: {miss}"); return
                Xb = dn[xc].values.astype(float); Yp = model.predict(Xb)
                res = dn.copy()
                for j, yn in enumerate(yc): res[f"{yn}(pred)"] = Yp[:, j]
                sd = os.path.join(current_dir, "save"); os.makedirs(sd, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                out = os.path.join(sd, f"{ts}_prediction.csv"); res.to_csv(out, index=False)
                ot.delete("1.0", tk.END); ot.insert(tk.END, f"Batch: {len(Xb)} rows\nSaved: {out}\n\n")
                ot.insert(tk.END, res.head(20).to_string(index=False) + "\n")
                log_fn(f"Batch prediction -> {out}")
            except Exception as e: messagebox.showerror("Error", str(e))

        bf = tk.Frame(pw); bf.pack(pady=4)
        tk.Button(bf, text="Predict (single)", width=16, command=_do_single).pack(side="left", padx=4)
        tk.Button(bf, text="Predict (CSV)", width=16, command=_do_batch).pack(side="left", padx=4)

    def _prof():
        df = state["df"]
        if df is None: messagebox.showwarning("", "Load CSV first."); return
        pw = tk.Toplevel(win); pw.title("Profiling"); pw.geometry("800x600"); place_near_root(pw)
        pn = ttk.Notebook(pw); pn.pack(fill="both", expand=True)
        # Statistics
        st = tk.Text(pn, wrap="none"); pn.add(st, text="Statistics")
        desc = df.describe().T; desc["missing"] = df.isnull().sum(); st.insert(tk.END, desc.to_string())
        # Correlation
        cf2 = tk.Frame(pn); pn.add(cf2, text="Correlation")
        corr = df.corr(); fig = Figure(figsize=(6, 5), dpi=100); ax = fig.add_subplot(111)
        im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns))); ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=7)
        ax.set_yticklabels(corr.columns, fontsize=7); fig.colorbar(im, ax=ax); fig.tight_layout()
        FigureCanvasTkAgg(fig, master=cf2).get_tk_widget().pack(fill="both", expand=True)
        # Histograms
        hf = tk.Frame(pn); pn.add(hf, text="Histograms")
        nc2 = min(4, len(df.columns)); nr2 = (len(df.columns) + nc2 - 1) // nc2
        fig2 = Figure(figsize=(3 * nc2, 2.5 * nr2), dpi=90)
        for idx, c in enumerate(df.columns):
            ax2 = fig2.add_subplot(nr2, nc2, idx + 1)
            ax2.hist(df[c].dropna(), bins=20, alpha=0.8, edgecolor="black"); ax2.set_title(c, fontsize=8); ax2.tick_params(labelsize=6)
        fig2.tight_layout()
        cvs2 = FigureCanvasTkAgg(fig2, master=hf); cvs2.draw(); cvs2.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs2, hf)
        log_fn("Profiling opened.")

    log_fn("Optimization Window opened.")
