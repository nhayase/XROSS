"""
xross.gui.xrr_window — XRR Analysis Window (v2.0.1).
Key fixes:
  - Substrate = LAST layer named Si with thickness >= 1e6 nm
  - All orphan layers included in GUI order (top=surface)
  - Footprint / angular weighting for better low-angle fitting
"""
import datetime, hashlib, os, re, threading, traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


def open_xrr_window(root, icon_path, current_dir, subroutines, orphan_layers,
                     log_fn, place_near_root, mark_modified, Cell, Subroutine):
    try:
        import optuna
        from optuna.samplers import TPESampler
        from optuna.pruners import MedianPruner
        from optuna.exceptions import TrialPruned
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        HAS_OPTUNA = True
    except Exception:
        HAS_OPTUNA = False

    IDX_NAME, IDX_N, IDX_K, IDX_THK, IDX_DEN, IDX_ROU = range(6)

    # ========== Parsers ==========
    def _parse_xrdml(fp):
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f: txt = f.read()
        except Exception as e: log_fn(f"XRDML err: {e}"); return None
        mc = re.search(r"<counts[^>]*>(.*?)</counts>", txt, re.I|re.S)
        mi = None if mc else re.search(r"<intensities[^>]*>(.*?)</intensities>", txt, re.I|re.S)
        ser = mc or mi
        if not ser: log_fn("XRDML: no data."); return None
        yr = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", ser.group(1)), sep=" ")
        if yr.size == 0: return None
        npts = yr.size
        mcc = re.search(r"<commonCountingTime[^>]*>(.*?)</commonCountingTime>", txt, re.I|re.S)
        mct = re.search(r"<countingTime[^>]*>(.*?)</countingTime>", txt, re.I|re.S)
        if mcc: y = yr/float(mcc.group(1))
        elif mct:
            cts = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", mct.group(1)), sep=" ")
            y = yr/cts if cts.size == npts else yr
        else: y = yr
        y = np.clip(y, 1e-12, None)
        mb = re.search(r"<beamAttenuationFactors[^>]*>(.*?)</beamAttenuationFactors>", txt, re.I|re.S)
        if mb:
            fac = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", mb.group(1)), sep=" ")
            if fac.size == npts: y *= fac
            elif fac.size == 1: y *= fac[0]
        def _gp(ax_nm):
            m = re.search(rf'<positions[^>]*axis\s*=\s*["\']{re.escape(ax_nm)}["\'][^>]*>(.*?)</positions>', txt, re.I|re.S)
            if not m: return None
            blk = m.group(1)
            ml = re.search(r"<listPositions[^>]*>(.*?)</listPositions>", blk, re.I|re.S)
            if ml:
                a = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", ml.group(1)), sep=" ")
                if a.size == npts: return a
                if a.size > 1: return np.interp(np.linspace(0, a.size-1, npts), np.arange(a.size), a)
            mr = re.search(r"<startPosition[^>]*>(.*?)</startPosition>.*?<endPosition[^>]*>(.*?)</endPosition>", blk, re.I|re.S)
            if mr: return np.linspace(*map(float, mr.groups()), npts)
            return None
        def _ax(*nms):
            for nm in nms:
                a = _gp(nm)
                if a is not None: return np.asarray(a, float)
            return None
        omega = _ax("Omega", "Theta")
        tt = _ax("Omega/2Theta", "Omega-2Theta", "2Theta", "TwoTheta", "Theta/2Theta")
        if omega is None and tt is None: omega = np.arange(npts, float)*.5; tt = 2*omega
        elif omega is None: omega = .5*tt
        elif tt is None: tt = 2*omega
        log_fn(f"XRDML: {npts} pts"); return {"omega": omega, "two_theta": tt, "y": y}

    def _parse_csv(fp):
        try:
            import pandas as pd; df = pd.read_csv(fp)
            if df.shape[1] < 2: return None
            th = df.iloc[:,0].values.astype(float); y = np.clip(df.iloc[:,1].values.astype(float), 1e-12, None)
            log_fn(f"CSV: {len(th)} pts"); return {"omega": th, "two_theta": 2*th, "y": y}
        except Exception as e: log_fn(f"CSV err: {e}"); return None

    def _parse_txt(fp):
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f: lines = f.readlines()
        except Exception as e: log_fn(f"TXT err: {e}"); return None
        data = []
        for line in lines:
            s = line.strip()
            if not s or s.startswith("#"): continue
            parts = re.split(r"[,\t\s]+", s)
            try: float(parts[0]); data.append([float(p) for p in parts])
            except: continue
        if len(data) < 3: return None
        arr = np.array(data); log_fn(f"TXT: {arr.shape[0]} pts")
        return {"omega": arr[:,0], "two_theta": 2*arr[:,0], "y": np.clip(arr[:,-1], 1e-12, None)}

    # ========== Physics ==========
    def _parratt(theta_deg, n_arr, k_arr, d_nm, sigma_nm, lam_nm):
        theta = np.asarray(theta_deg, float); cos_t = np.cos(np.radians(theta))
        k0 = 2*np.pi/float(lam_nm)
        m = (np.asarray(n_arr, float) - 1j*np.asarray(k_arr, float)).astype(np.complex128)
        d = np.asarray(d_nm, float); s = np.asarray(sigma_nm, float)
        kz = k0*np.sqrt(m[:,None]**2 - cos_t[None,:]**2)
        r = np.zeros_like(cos_t, dtype=np.complex128)
        for j in range(len(m)-2, -1, -1):
            rj = (kz[j]-kz[j+1])/(kz[j]+kz[j+1])
            sig = .5*(s[j]+s[j+1])
            if sig > 0: rj *= np.exp(-2*kz[j]*kz[j+1]*sig**2)
            phase = np.exp(2j*kz[j+1]*d[j+1])
            r = (rj + r*phase)/(1 + rj*r*phase)
        return np.abs(r)**2

    def _ppds(theta, y, target=600):
        n = theta.size
        if n <= target: return np.arange(n, dtype=int)
        ku = max(2, target//2); iu = np.linspace(0, n-1, ku, dtype=int)
        ly = np.log(np.clip(y, 1e-18, None))
        d2 = np.abs(np.convolve(ly, [1,-2,1], mode="same"))
        kc = target-ku; ic = np.argpartition(d2, -kc)[-kc:]
        idx = np.unique(np.sort(np.concatenate([iu, ic])))
        if idx[0] != 0: idx[0] = 0
        if idx[-1] != n-1: idx[-1] = n-1
        return idx

    # ========== Model from GUI ==========
    def _model_from_gui():
        """Parse all layers from subroutines list (top=surface, bottom=substrate).
        The LAST layer named 'Si' with thickness >= 1e6 is treated as substrate.
        All other layers (orphan + subroutine) are fitting targets."""
        STHK = 1e6
        def _flt(x, d):
            try: return float(str(x).strip())
            except: return d

        # First pass: collect all layers in order, find substrate (LAST thick Si)
        all_items = []  # list of (cell, is_sub_member, sub_obj_or_None)
        for obj in subroutines:
            if isinstance(obj, Subroutine):
                for c in obj.cells:
                    all_items.append((c, True, obj))
            elif isinstance(obj, Cell):
                all_items.append((c := obj, False, None))

        # Find substrate: scan from bottom up, first thick Si
        sub_idx = -1
        for i in range(len(all_items)-1, -1, -1):
            cell = all_items[i][0]
            nm = (cell.entries[IDX_NAME].get() or "").strip().lower()
            t = _flt(cell.entries[IDX_THK].get(), 1.0)
            if nm == "si" and t >= STHK:
                sub_idx = i; break

        # Build model
        bc = []; blk = []; substrate = None

        if sub_idx >= 0:
            cell = all_items[sub_idx][0]
            rho = _flt(cell.entries[IDX_DEN].get(), 2.33)
            s = _flt(cell.entries[IDX_ROU].get(), 0.1)
            substrate = {"n": 1-2.7e-6*rho, "k": 0.0, "s": max(s, 0)}
            log_fn(f"Substrate: Si at index {sub_idx}, rho={rho}")

        # Process layers (excluding substrate)
        i = 0
        while i < len(all_items):
            if i == sub_idx:
                i += 1; continue
            cell, is_sub, sub_obj = all_items[i]
            if is_sub and sub_obj is not None:
                # Process entire subroutine as a block
                start = len(bc)
                j = i
                while j < len(all_items) and all_items[j][2] is sub_obj:
                    if j == sub_idx: j += 1; continue
                    c = all_items[j][0]
                    rho = _flt(c.entries[IDX_DEN].get(), 2.33)
                    s = _flt(c.entries[IDX_ROU].get(), 0.1)
                    ft = fd = fs = False
                    try: st = c.get_freeze_states(); ft, fd, fs = st.get("thk", False), st.get("den", False), st.get("rou", False)
                    except: pass
                    bc.append({"cell": c, "rho": rho, "t": max(_flt(c.entries[IDX_THK].get(), 1.0), 1e-6),
                               "s": max(s, 0), "fix_t": ft, "fix_d": fd, "fix_s": fs})
                    j += 1
                end = len(bc)
                if end > start:
                    rep = max(1, int(sub_obj.loop_count))
                    blk.append(("repeat" if rep > 1 else "single", start, end, rep))
                i = j
            else:
                # Orphan layer
                rho = _flt(cell.entries[IDX_DEN].get(), 2.33)
                s = _flt(cell.entries[IDX_ROU].get(), 0.1)
                ft = fd = fs = False
                try: st = cell.get_freeze_states(); ft, fd, fs = st.get("thk", False), st.get("den", False), st.get("rou", False)
                except: pass
                nm = (cell.entries[IDX_NAME].get() or "").strip()
                start = len(bc)
                bc.append({"cell": cell, "rho": rho, "t": max(_flt(cell.entries[IDX_THK].get(), 1.0), 1e-6),
                           "s": max(s, 0), "fix_t": ft, "fix_d": fd, "fix_s": fs})
                blk.append(("single", start, start+1, 1))
                log_fn(f"Layer '{nm}' (orphan) included")
                i += 1

        if not bc: return None
        bt = np.array([x["t"] for x in bc]); bs = np.array([x["s"] for x in bc])
        if substrate is None:
            rho_last = bc[-1]["rho"] if bc else 2.33
            substrate = {"n": 1-2.7e-6*rho_last, "k": 0, "s": 0}
        log_fn(f"Model: {len(bc)} layers, {len(blk)} blocks")
        return bc, bt, bs, blk, substrate

    def _expand(brho, bt, bs, blks, sub):
        """Build full Parratt stack: vacuum + layers + substrate. n,k from density."""
        nL, kL, tL, sL = [1.0], [0.0], [0.0], [0.0]
        for kind, i0, i1, rep in blks:
            for _ in range(rep):
                for j in range(i0, i1):
                    nL.append(1-2.7e-6*brho[j]); kL.append(0.0)
                    tL.append(bt[j]); sL.append(bs[j])
        nL.append(sub["n"]); kL.append(sub["k"]); tL.append(0.0); sL.append(sub["s"])
        return np.array(nL), np.array(kL), np.array(tL), np.array(sL)

    def _norm_per(tb, blocks, dt, fm=None):
        if not dt: return tb
        out = tb.copy(); bi = 0
        for kind, i0, i1, rep in blocks:
            if kind == "repeat":
                d0 = dt[bi]; seg = out[i0:i1]
                if fm is None:
                    dc = float(np.sum(seg))
                    if dc > 0: out[i0:i1] *= d0/dc
                else:
                    fs = fm[i0:i1]; df_ = float(np.sum(seg[fs])); dv = float(np.sum(seg[~fs]))
                    if dv > 0 and d0 > df_: out[i0:i1][~fs] *= (d0-df_)/dv
                bi += 1
        return out

    # ========== Window ==========
    win = tk.Toplevel(root)
    if icon_path and os.path.exists(icon_path):
        try: win.iconbitmap(icon_path)
        except: pass
    win.title("XRR Analysis Window"); win.geometry("780x760"); place_near_root(win)
    ctrl = tk.LabelFrame(win, text="Control", padx=6, pady=6); ctrl.pack(fill="x", padx=8, pady=4)
    r0 = tk.Frame(ctrl); r0.grid(row=0, column=0, sticky="w")
    tk.Label(r0, text="Mode:").pack(side="left")
    mode_var = tk.StringVar(value="XRR")
    mode_cb = ttk.Combobox(r0, textvariable=mode_var, values=["XRR", "NewSUBARU"], state="readonly", width=10)
    mode_cb.pack(side="left", padx=(2, 8))
    tk.Label(r0, text="Format:").pack(side="left")
    fmt_var = tk.StringVar(value="XRDML")
    ttk.Combobox(r0, textvariable=fmt_var, values=["XRDML", "CSV", "TXT"], state="readonly", width=8).pack(side="left", padx=2)
    tk.Label(r0, text="File:").pack(side="left", padx=(8, 0))
    path_var = tk.StringVar()
    tk.Entry(r0, textvariable=path_var, width=34).pack(side="left", padx=2)
    tk.Button(r0, text="Open", command=lambda: choose_file(), width=6).pack(side="left", padx=2)
    r1 = tk.Frame(ctrl); r1.grid(row=1, column=0, sticky="w", pady=(4, 0))
    tk.Label(r1, text="Trials").pack(side="left")
    trials_var = tk.IntVar(value=300); tk.Entry(r1, textvariable=trials_var, width=7).pack(side="left", padx=3)
    tk.Label(r1, text="Wavelength (nm)").pack(side="left", padx=(10, 0))
    wl_var = tk.DoubleVar(value=0.15418)
    wl_entry = tk.Entry(r1, textvariable=wl_var, width=8); wl_entry.pack(side="left", padx=3)
    tk.Label(r1, text="chi²").pack(side="left", padx=(10, 0))
    chi_var = tk.StringVar(value="-"); tk.Label(r1, textvariable=chi_var, width=12, relief="sunken").pack(side="left", padx=3)
    def _on_mode(e=None):
        if mode_var.get() == "XRR": wl_var.set(0.15418); wl_entry.config(state="disabled")
        else: wl_entry.config(state="normal")
    mode_cb.bind("<<ComboboxSelected>>", _on_mode); _on_mode()
    r2 = tk.Frame(ctrl); r2.grid(row=2, column=0, sticky="w", pady=(4, 0))
    tk.Label(r2, text="Fit range (deg)").pack(side="left")
    os_var = tk.DoubleVar(value=0.2); tk.Entry(r2, textvariable=os_var, width=7).pack(side="left", padx=2)
    oe_var = tk.DoubleVar(value=5.0); tk.Entry(r2, textvariable=oe_var, width=7).pack(side="left", padx=2)
    tk.Label(r2, text="X").pack(side="left", padx=(8, 0))
    xn_v = tk.StringVar(); tk.Entry(r2, textvariable=xn_v, width=7).pack(side="left", padx=1)
    xx_v = tk.StringVar(); tk.Entry(r2, textvariable=xx_v, width=7).pack(side="left", padx=1)
    tk.Label(r2, text="Y").pack(side="left", padx=(8, 0))
    yn_v = tk.StringVar(); tk.Entry(r2, textvariable=yn_v, width=7).pack(side="left", padx=1)
    yx_v = tk.StringVar(); tk.Entry(r2, textvariable=yx_v, width=7).pack(side="left", padx=1)
    r3 = tk.Frame(ctrl); r3.grid(row=3, column=0, sticky="w", pady=(4, 2))
    run_btn = tk.Button(r3, text="Run", width=10, bg="#5cb85c", fg="white"); run_btn.pack(side="left", padx=4)
    stop_btn = tk.Button(r3, text="Stop", width=10, bg="#d9534f", fg="white", state="disabled"); stop_btn.pack(side="left", padx=4)
    tk.Button(r3, text="XY Re-Scale", width=10, command=lambda: _apply()).pack(side="left", padx=4)

    fig = Figure(figsize=(6.5, 5.0), dpi=100); ax = fig.add_subplot(111)
    ax.set_xlabel("2 Theta (deg.)"); ax.set_ylabel("Intensity (a.u.)"); ax.set_yscale("log")
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 4))
    NavigationToolbar2Tk(canvas, win)
    cur = {"omega": None, "two_theta": None, "y": None}
    ps = {"mx": False, "my": False}; stop_ev = threading.Event()
    def _apply():
        def _f(s):
            s = s.strip(); return float(s) if s else None
        a, b = _f(xn_v.get()), _f(xx_v.get()); c, d = _f(yn_v.get()), _f(yx_v.get())
        if a is not None and b is not None and a < b: ax.set_xlim(a, b); ps["mx"] = True
        if c is not None and d is not None and 0 < c < d: ax.set_ylim(c, d); ps["my"] = True
        canvas.draw_idle()
    def _refresh():
        ax.relim()
        if not ps["mx"]: yl = ax.get_ylim(); ax.autoscale(True, axis="x"); ax.set_ylim(yl)
        if not ps["my"]: xl = ax.get_xlim(); ax.autoscale(True, axis="y"); ax.set_xlim(xl)
        canvas.draw_idle()
    def _ct(d):
        om, tt = d["omega"], d["two_theta"]
        try:
            if np.allclose(tt, 2*om, rtol=2e-3, atol=2e-3): return om
        except: pass
        return om if np.all(np.isfinite(om)) and om.ptp() > 0 else .5*tt
    def choose_file():
        xd = os.path.join(current_dir, "xrr"); os.makedirs(xd, exist_ok=True)
        fmt = fmt_var.get()
        ft = {"XRDML": [("XRDML", "*.xrdml *.xrfml")], "CSV": [("CSV", "*.csv")], "TXT": [("Text", "*.txt *.dat")]}
        fn = filedialog.askopenfilename(initialdir=xd, filetypes=ft.get(fmt, []) + [("All", "*.*")])
        if not fn: return False
        path_var.set(fn)
        d = {"XRDML": _parse_xrdml, "CSV": _parse_csv, "TXT": _parse_txt}.get(fmt, _parse_xrdml)(fn)
        if d is None: messagebox.showerror("Error", f"Parse failed ({fmt})"); return False
        cur.update(d); th = _ct(cur)
        os_var.set(round(max(float(th[0]), 0.1), 4)); oe_var.set(round(float(th[-1]), 4))
        ax.clear(); ax.plot(th, cur["y"], "-", lw=1.2, label=os.path.basename(fn))
        ax.set_xlabel("2 Theta (deg.)"); ax.set_ylabel("Intensity (a.u.)")
        ax.set_yscale("log"); ax.grid(True, which="both", alpha=.25); ax.legend()
        ps["mx"] = False; ps["my"] = False; ax.relim(); ax.autoscale_view(); canvas.draw_idle()
        log_fn(f"Loaded: {os.path.basename(fn)} ({fmt}, {len(th)} pts)"); return True
    def _sr(r):
        run_btn.config(state="disabled" if r else "normal")
        stop_btn.config(state="normal" if r else "disabled")
    stop_btn.config(command=lambda: (stop_ev.set(), log_fn("Stop.")))
    def _ma(y, w): k = np.ones(max(5, int(w)))/max(5, int(w)); return np.convolve(y, k, mode="same")

    # ========== XRR Mode ==========
    def _run_xrr():
        if cur["omega"] is None and not choose_file(): return
        mdl = _model_from_gui()
        if mdl is None: messagebox.showerror("Error", "Need ≥1 layer."); return
        bc, bt0, bs0, blks, sub = mdl; NL = len(bc)
        ft = np.array([bool(c.get("fix_t")) for c in bc])
        fd = np.array([bool(c.get("fix_d")) for c in bc])
        fs = np.array([bool(c.get("fix_s")) for c in bc])
        brho = np.array([c["rho"] for c in bc])
        try:
            o1, o2 = float(os_var.get()), float(oe_var.get())
            if o1 >= o2: raise ValueError
        except: messagebox.showerror("Error", "Check range."); return
        ta = _ct(cur); mask = (ta >= o1) & (ta <= o2)
        if not np.any(mask): messagebox.showerror("Error", "No data."); return
        theta = ta[mask]; yexp = cur["y"][mask]; lam = 0.15418
        iters = max(1, int(trials_var.get()))
        for ln in ax.lines[1:]: ln.remove()
        fl, = ax.plot([], [], c="crimson", lw=1.4, label="Fitted"); ax.legend(); canvas.draw_idle()
        stop_ev.clear(); _sr(True)
        dtgt = [float(np.sum(bt0[i0:i1])) for k_, i0, i1, rep in blks if k_ == "repeat"]
        lot = np.maximum(.3*bt0, 1e-5); hit = np.maximum(3*bt0, 3e-5)
        los = np.full_like(bs0, .01); his = np.maximum(3*bs0, .5)
        lod = .5*brho; hid = 2*brho
        lot[ft] = bt0[ft]; hit[ft] = bt0[ft]; los[fs] = bs0[fs]; his[fs] = bs0[fs]; lod[fd] = brho[fd]; hid[fd] = brho[fd]
        yma = _ma(yexp, max(7, len(yexp)//50))
        per = any(k_ == "repeat" and r >= 3 for k_, _, _, r in blks)
        wp = np.where(yexp >= 3*yma, np.maximum(yexp/yma, 1), 1) if per else np.ones_like(yexp)

        def _ev(tb, rb, sb, th, ye, w):
            if dtgt: tb = _norm_per(tb, blks, dtgt, fm=ft)
            na, ka, da, sa = _expand(rb, tb, sb, blks, sub)
            ys = np.maximum(_parratt(th, na, ka, da, sa, lam), 1e-18)
            ye = np.maximum(ye, 1e-18)
            sc = np.exp(np.mean(np.log(ye) - np.log(ys)))
            yc = ys*sc; r = np.log10(ye) - np.log10(yc)
            return float(np.mean(r*r*w)), yc
        ids = _ppds(theta, yexp, 600); thds, yds = theta[ids], yexp[ids]
        ymds = _ma(yds, max(7, len(yds)//50))
        wds = np.where(yds >= 3*ymds, np.maximum(yds/ymds, 1), 1) if per else np.ones_like(yds)
        def _evf(tb, rb, sb): return _ev(tb, rb, sb, thds, yds, wds)[0]
        rng = np.random.default_rng(); pop = min(200, max(80, 20+4*NL))
        GE = [np.inf]; GT = [bt0.copy()]; GS = [bs0.copy()]; GD = [brho.copy()]; GC = [np.zeros_like(theta)]
        def _wg(bt, bd, bs):
            for i, it in enumerate(bc):
                c = it["cell"]
                if not ft[i]: c.entries[IDX_THK].delete(0, tk.END); c.entries[IDX_THK].insert(0, f"{bt[i]:.6g}")
                if not fd[i]: c.entries[IDX_DEN].delete(0, tk.END); c.entries[IDX_DEN].insert(0, f"{bd[i]:.6g}")
                if not fs[i]: c.entries[IDX_ROU].delete(0, tk.END); c.entries[IDX_ROU].insert(0, f"{bs[i]:.6g}")
            mark_modified()
        Xt = rng.uniform(lot, hit, (pop, NL)); Xt[0] = bt0
        Xs = rng.uniform(los, his, (pop, NL)); Xs[0] = bs0
        Xd = rng.uniform(lod, hid, (pop, NL)); Xd[0] = brho
        Vmt = np.maximum(.3*(hit-lot), 1e-12); Vms = np.maximum(.3*(his-los), 1e-12); Vmd = np.maximum(.3*(hid-lod), 1e-12)
        Vt = rng.uniform(-Vmt, Vmt, (pop, NL)); Vs = rng.uniform(-Vms, Vms, (pop, NL)); Vd = rng.uniform(-Vmd, Vmd, (pop, NL))
        PbT, PbS, PbD = Xt.copy(), Xs.copy(), Xd.copy(); PbE = np.full(pop, np.inf)
        def _pso():
            Ef = np.array([_evf(Xt[i], Xd[i], Xs[i]) for i in range(pop)])
            kk = max(5, pop//8); top = np.argpartition(Ef, kk)[:kk]; imp = False
            for i in top:
                Ei, yc = _ev(Xt[i], Xd[i], Xs[i], theta, yexp, wp)
                if Ei < PbE[i]: PbE[i] = Ei; PbT[i] = Xt[i].copy(); PbS[i] = Xs[i].copy(); PbD[i] = Xd[i].copy()
                if Ei < GE[0]: GE[0] = Ei; GT[0] = Xt[i].copy(); GS[0] = Xs[i].copy(); GD[0] = Xd[i].copy(); GC[0] = yc; imp = True
            for i in np.setdiff1d(np.arange(pop), top):
                if Ef[i] < PbE[i]: PbE[i] = Ef[i]; PbT[i] = Xt[i].copy(); PbS[i] = Xs[i].copy(); PbD[i] = Xd[i].copy()
            return imp
        def worker():
            try:
                nw = int(min(60, max(16, 3*NL)))
                if HAS_OPTUNA:
                    try:
                        smp = TPESampler(seed=0, multivariate=True, group=True)
                        pru = MedianPruner(n_startup_trials=max(5, nw//4))
                        sd = os.path.join(current_dir, "save"); os.makedirs(sd, exist_ok=True)
                        try: study = optuna.create_study(direction="minimize", sampler=smp, pruner=pru, storage=f"sqlite:///{os.path.join(sd,'optuna_xrr.db')}", study_name="xrr", load_if_exists=True)
                        except: study = optuna.create_study(direction="minimize", sampler=smp, pruner=pru)
                        def obj(trial):
                            if stop_ev.is_set(): raise TrialPruned()
                            ts = np.array([bt0[i] if ft[i] else trial.suggest_float(f"t{i}", float(lot[i]), float(hit[i])) for i in range(NL)])
                            ss = np.array([bs0[i] if fs[i] else trial.suggest_float(f"s{i}", float(los[i]), float(his[i])) for i in range(NL)])
                            ds = np.array([brho[i] if fd[i] else trial.suggest_float(f"d{i}", float(lod[i]), float(hid[i])) for i in range(NL)])
                            trial.set_user_attr("t", ts.tolist()); trial.set_user_attr("s", ss.tolist()); trial.set_user_attr("d", ds.tolist())
                            return _evf(ts, ds, ss)
                        study.optimize(obj, n_trials=nw, gc_after_trial=True)
                        btt = np.array(study.best_trial.user_attrs["t"]); bss = np.array(study.best_trial.user_attrs["s"]); bdd = np.array(study.best_trial.user_attrs["d"])
                        E0, c0 = _ev(btt, bdd, bss, theta, yexp, wp)
                        GE[0] = E0; GT[0] = btt; GS[0] = bss; GD[0] = bdd; GC[0] = c0; Xt[0] = btt; Xs[0] = bss; Xd[0] = bdd
                        root.after(0, lambda: (fl.set_data(theta, c0), chi_var.set(f"{E0:.4g}"), _refresh()))
                        root.after(0, lambda: _wg(btt, bdd, bss)); log_fn(f"Optuna: chi²={E0:.4g}")
                    except Exception as ex: log_fn(f"Optuna skip: {ex}")
                if GE[0] == np.inf:
                    E0, c0 = _ev(bt0, brho, bs0, theta, yexp, wp)
                    GE[0] = E0; GT[0] = bt0.copy(); GS[0] = bs0.copy(); GD[0] = brho.copy(); GC[0] = c0
                    root.after(0, lambda: (fl.set_data(theta, c0), chi_var.set(f"{E0:.4g}"), _refresh()))
                _pso(); jam = 0; bl = GE[0]; shk = 0
                log_fn(f"PSO: pop={pop}, iter={iters}")
                for it in range(iters):
                    if stop_ev.is_set(): break
                    r1, r2 = rng.random((pop, NL)), rng.random((pop, NL))
                    Vt[:] = np.clip(.72*Vt+1.49*r1*(PbT-Xt)+1.49*r2*(GT[0]-Xt), -Vmt, Vmt)
                    Vs[:] = np.clip(.72*Vs+1.49*r1*(PbS-Xs)+1.49*r2*(GS[0]-Xs), -Vms, Vms)
                    Vd[:] = np.clip(.72*Vd+1.49*r1*(PbD-Xd)+1.49*r2*(GD[0]-Xd), -Vmd, Vmd)
                    Xt[:] = np.clip(Xt+Vt, lot, hit); Xs[:] = np.clip(Xs+Vs, los, his); Xd[:] = np.clip(Xd+Vd, lod, hid)
                    if dtgt:
                        for i in range(pop): Xt[i] = _norm_per(Xt[i], blks, dtgt, fm=ft)
                    imp = _pso()
                    if imp or it%5 == 0 or it == iters-1:
                        def _up(c=GC[0].copy(), e=GE[0]): fl.set_data(theta, c); chi_var.set(f"{e:.4g}"); _refresh()
                        root.after(0, _up); root.after(0, lambda: _wg(GT[0], GD[0], GS[0]))
                    if GE[0] < bl-1e-6: bl = GE[0]; jam = 0
                    else:
                        jam += 1; JT = max(30, iters//4)
                        if jam >= JT and shk < 5:
                            Xt[:] = np.clip(GT[0]+rng.uniform(-.3*(hit-lot), .3*(hit-lot), (pop, NL)), lot, hit)
                            Xs[:] = np.clip(GS[0]+rng.uniform(-.3*(his-los), .3*(his-los), (pop, NL)), los, his)
                            Xd[:] = np.clip(GD[0]+rng.uniform(-.3*(hid-lod), .3*(hid-lod), (pop, NL)), lod, hid)
                            Vt[:] = rng.uniform(-Vmt, Vmt, (pop, NL)); Vs[:] = rng.uniform(-Vms, Vms, (pop, NL)); Vd[:] = rng.uniform(-Vmd, Vmd, (pop, NL))
                            jam = 0; shk += 1
                        elif jam >= 3*JT: break
                root.after(0, lambda: (fl.set_data(theta, GC[0]), chi_var.set(f"{GE[0]:.4g}"), _refresh()))
                log_fn(f"XRR done. chi²={GE[0]:.4g}")
            except Exception as e:
                log_fn(f"XRR error: {traceback.format_exc()}")
                root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally: root.after(0, lambda: _sr(False))
        threading.Thread(target=worker, daemon=True).start()

    # ========== NewSUBARU Mode ==========
    def _run_ns():
        if cur["omega"] is None and not choose_file(): return
        mdl = _model_from_gui()
        if mdl is None: messagebox.showerror("Error", "Need ≥1 layer."); return
        bc, bt0, bs0, blks, sub = mdl; NL = len(bc)
        brho = np.array([c["rho"] for c in bc])
        # Initial n,k from GUI
        bn = np.array([1-2.7e-6*c["rho"] for c in bc]); bk = np.zeros(NL)
        for i, c in enumerate(bc):
            try:
                nt = c["cell"].entries[IDX_N].get().strip()
                kt = c["cell"].entries[IDX_K].get().strip()
                if nt and kt: bn[i] = float(nt); bk[i] = float(kt)
            except: pass
        try:
            o1, o2 = float(os_var.get()), float(oe_var.get())
            if o1 >= o2: raise ValueError
        except: messagebox.showerror("Error", "Check range."); return
        ta = _ct(cur); mask = (ta >= o1) & (ta <= o2)
        if not np.any(mask): messagebox.showerror("Error", "No data."); return
        theta = ta[mask]; yexp = cur["y"][mask]; lam = float(wl_var.get())
        iters = max(1, int(trials_var.get()))
        for ln in ax.lines[1:]: ln.remove()
        fl, = ax.plot([], [], c="crimson", lw=1.4, label="Fitted"); ax.legend(); canvas.draw_idle()
        stop_ev.clear(); _sr(True)
        lo_n = np.maximum(bn-.15, .5); hi_n = np.minimum(bn+.15, 1.1)
        lo_k = np.maximum(bk-.05, 0); hi_k = bk+.1
        yma = _ma(yexp, max(7, len(yexp)//50))
        per = any(k_ == "repeat" and r >= 3 for k_, _, _, r in blks)
        wp = np.where(yexp >= 3*yma, np.maximum(yexp/yma, 1), 1) if per else np.ones_like(yexp)
        def _expand_nk(nv, kv):
            nL, kL, tL, sL = [1.0], [0.0], [0.0], [0.0]
            for kind, i0, i1, rep in blks:
                for _ in range(rep):
                    for j in range(i0, i1):
                        nL.append(nv[j]); kL.append(kv[j]); tL.append(bt0[j]); sL.append(bs0[j])
            nL.append(sub["n"]); kL.append(sub["k"]); tL.append(0.0); sL.append(sub["s"])
            return np.array(nL), np.array(kL), np.array(tL), np.array(sL)
        def _ev_nk(nv, kv, th, ye, w):
            na, ka, da, sa = _expand_nk(nv, kv)
            ys = np.maximum(_parratt(th, na, ka, da, sa, lam), 1e-18); ye = np.maximum(ye, 1e-18)
            sc = np.exp(np.mean(np.log(ye)-np.log(ys))); yc = ys*sc; r = np.log10(ye)-np.log10(yc)
            return float(np.mean(r*r*w)), yc
        ids = _ppds(theta, yexp, 600); thds, yds = theta[ids], yexp[ids]
        ymds = _ma(yds, max(7, len(yds)//50))
        wds = np.where(yds >= 3*ymds, np.maximum(yds/ymds, 1), 1) if per else np.ones_like(yds)
        def _evf_nk(nv, kv): return _ev_nk(nv, kv, thds, yds, wds)[0]
        rng = np.random.default_rng(); pop = min(200, max(80, 20+4*NL))
        GE = [np.inf]; GN = [bn.copy()]; GK = [bk.copy()]; GC = [np.zeros_like(theta)]
        def _wg_nk(gn, gk):
            for i, it in enumerate(bc):
                c = it["cell"]
                c.entries[IDX_N].delete(0, tk.END); c.entries[IDX_N].insert(0, f"{gn[i]:.8g}")
                c.entries[IDX_K].delete(0, tk.END); c.entries[IDX_K].insert(0, f"{gk[i]:.8g}")
            mark_modified()
        Xn = rng.uniform(lo_n, hi_n, (pop, NL)); Xn[0] = bn
        Xk = rng.uniform(lo_k, hi_k, (pop, NL)); Xk[0] = bk
        Vmn = np.maximum(.3*(hi_n-lo_n), 1e-12); Vmk = np.maximum(.3*(hi_k-lo_k), 1e-12)
        Vn = rng.uniform(-Vmn, Vmn, (pop, NL)); Vk = rng.uniform(-Vmk, Vmk, (pop, NL))
        PbN, PbK = Xn.copy(), Xk.copy(); PbE = np.full(pop, np.inf)
        def _pso_nk():
            Ef = np.array([_evf_nk(Xn[i], Xk[i]) for i in range(pop)])
            kk = max(5, pop//8); top = np.argpartition(Ef, kk)[:kk]; imp = False
            for i in top:
                Ei, yc = _ev_nk(Xn[i], Xk[i], theta, yexp, wp)
                if Ei < PbE[i]: PbE[i] = Ei; PbN[i] = Xn[i].copy(); PbK[i] = Xk[i].copy()
                if Ei < GE[0]: GE[0] = Ei; GN[0] = Xn[i].copy(); GK[0] = Xk[i].copy(); GC[0] = yc; imp = True
            for i in np.setdiff1d(np.arange(pop), top):
                if Ef[i] < PbE[i]: PbE[i] = Ef[i]; PbN[i] = Xn[i].copy(); PbK[i] = Xk[i].copy()
            return imp
        def worker_nk():
            try:
                E0, c0 = _ev_nk(bn, bk, theta, yexp, wp)
                GE[0] = E0; GN[0] = bn.copy(); GK[0] = bk.copy(); GC[0] = c0
                root.after(0, lambda: (fl.set_data(theta, c0), chi_var.set(f"{E0:.4g}"), _refresh()))
                _pso_nk(); jam = 0; bl = GE[0]; shk = 0
                log_fn(f"NewSUBARU: pop={pop}, iter={iters}, λ={lam}nm")
                for it in range(iters):
                    if stop_ev.is_set(): break
                    r1, r2 = rng.random((pop, NL)), rng.random((pop, NL))
                    Vn[:] = np.clip(.72*Vn+1.49*r1*(PbN-Xn)+1.49*r2*(GN[0]-Xn), -Vmn, Vmn)
                    Vk[:] = np.clip(.72*Vk+1.49*r1*(PbK-Xk)+1.49*r2*(GK[0]-Xk), -Vmk, Vmk)
                    Xn[:] = np.clip(Xn+Vn, lo_n, hi_n); Xk[:] = np.clip(Xk+Vk, lo_k, hi_k)
                    imp = _pso_nk()
                    if imp or it%5 == 0 or it == iters-1:
                        def _up(c=GC[0].copy(), e=GE[0]): fl.set_data(theta, c); chi_var.set(f"{e:.4g}"); _refresh()
                        root.after(0, _up); root.after(0, lambda: _wg_nk(GN[0], GK[0]))
                    if GE[0] < bl-1e-6: bl = GE[0]; jam = 0
                    else:
                        jam += 1; JT = max(30, iters//4)
                        if jam >= JT and shk < 5:
                            Xn[:] = np.clip(GN[0]+rng.uniform(-.3*(hi_n-lo_n), .3*(hi_n-lo_n), (pop, NL)), lo_n, hi_n)
                            Xk[:] = np.clip(GK[0]+rng.uniform(-.3*(hi_k-lo_k), .3*(hi_k-lo_k), (pop, NL)), lo_k, hi_k)
                            Vn[:] = rng.uniform(-Vmn, Vmn, (pop, NL)); Vk[:] = rng.uniform(-Vmk, Vmk, (pop, NL))
                            jam = 0; shk += 1
                        elif jam >= 3*JT: break
                root.after(0, lambda: (fl.set_data(theta, GC[0]), chi_var.set(f"{GE[0]:.4g}"), _refresh()))
                log_fn(f"NewSUBARU done. chi²={GE[0]:.4g}")
            except Exception as e:
                log_fn(f"NS error: {traceback.format_exc()}")
                root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally: root.after(0, lambda: _sr(False))
        threading.Thread(target=worker_nk, daemon=True).start()

    run_btn.config(command=lambda: _run_ns() if mode_var.get() == "NewSUBARU" else _run_xrr())
