"""
xross.gui.image_window — Image Analysis (512-tone heatmap & CSV export).
Adapted from f3_tone.py by Naoki Hayase.
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import colors, cm

def open_image_window(root, icon_path, current_dir, log_fn, place_near_root):
    """Open Image Analysis window as a Toplevel."""

    win = tk.Toplevel(root)
    if icon_path and os.path.exists(icon_path):
        try: win.iconbitmap(icon_path)
        except: pass
    win.title("Image Analysis (512 tones / Heatmap & CSV)")
    win.geometry("1200x800")
    place_near_root(win)

    pil_img = [None]
    img_array = [None]
    tk_img = [None]
    img_on_canvas = [None]
    rect_id = [None]
    current_path = [None]

    # Top bar
    top = ttk.Frame(win, padding=(8, 8, 8, 4))
    top.pack(side=tk.TOP, fill=tk.X)

    def load_image():
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showerror("Error", "Pillow is required.\npip install Pillow")
            return
        path = filedialog.askopenfilename(
            title="Select image files",
            filetypes=[("image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff"), ("All files", "*.*")])
        if not path: return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot Open:\n{e}"); return
        pil_img[0] = img; current_path[0] = path
        img_array[0] = np.array(img, dtype=np.uint8)
        tk_img[0] = ImageTk.PhotoImage(pil_img[0])
        canvas.delete("all")
        img_on_canvas[0] = canvas.create_image(0, 0, anchor="nw", image=tk_img[0])
        rect_id[0] = None
        w, h = img.size
        canvas.config(scrollregion=(0, 0, w, h), width=min(1000, w), height=min(700, h))
        entry_x.delete(0, tk.END); entry_x.insert(0, "0")
        entry_y.delete(0, tk.END); entry_y.insert(0, "0")
        entry_w.delete(0, tk.END); entry_w.insert(0, str(min(256, w)))
        entry_h.delete(0, tk.END); entry_h.insert(0, str(min(256, h)))
        log_fn(f"Image loaded: {path}")

    ttk.Button(top, text="Load", command=load_image).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Label(top, text="X").pack(side=tk.LEFT)
    entry_x = ttk.Entry(top, width=6); entry_x.insert(0, "0"); entry_x.pack(side=tk.LEFT, padx=(2, 8))
    ttk.Label(top, text="Y").pack(side=tk.LEFT)
    entry_y = ttk.Entry(top, width=6); entry_y.insert(0, "0"); entry_y.pack(side=tk.LEFT, padx=(2, 8))
    ttk.Label(top, text="Width").pack(side=tk.LEFT)
    entry_w = ttk.Entry(top, width=6); entry_w.insert(0, "100"); entry_w.pack(side=tk.LEFT, padx=(2, 8))
    ttk.Label(top, text="Height").pack(side=tk.LEFT)
    entry_h = ttk.Entry(top, width=6); entry_h.insert(0, "100"); entry_h.pack(side=tk.LEFT, padx=(2, 8))

    def confirm_roi():
        if img_array[0] is None: messagebox.showwarning("Caution", "Load an image first."); return
        try: x,y,w,h = int(entry_x.get()),int(entry_y.get()),int(entry_w.get()),int(entry_h.get())
        except ValueError: messagebox.showerror("Error", "Enter integers."); return
        H, W = img_array[0].shape[:2]
        x=max(0,min(x,W-1)); y=max(0,min(y,H-1)); w=max(1,w); h=max(1,h)
        if x+w>W: w=W-x
        if y+h>H: h=H-y
        entry_x.delete(0,tk.END); entry_x.insert(0,str(x))
        entry_y.delete(0,tk.END); entry_y.insert(0,str(y))
        entry_w.delete(0,tk.END); entry_w.insert(0,str(w))
        entry_h.delete(0,tk.END); entry_h.insert(0,str(h))
        if rect_id[0] is None:
            rect_id[0] = canvas.create_rectangle(x,y,x+w,y+h, outline="yellow", width=2)
        else:
            canvas.coords(rect_id[0], x,y,x+w,y+h)

    ttk.Button(top, text="Confirm", command=confirm_roi).pack(side=tk.LEFT, padx=(8, 8))

    def run_analysis():
        if img_array[0] is None: messagebox.showwarning("Caution", "Load an image first."); return
        try: x,y,w,h = int(entry_x.get()),int(entry_y.get()),int(entry_w.get()),int(entry_h.get())
        except ValueError: messagebox.showerror("Error", "Enter integers."); return
        H, W = img_array[0].shape[:2]
        if x<0 or y<0 or w<=0 or h<=0 or x+w>W or y+h>H:
            messagebox.showerror("Error", "ROI exceeds image size."); return
        roi = img_array[0][y:y+h, x:x+w, :]
        gray = (0.299*roi[...,0] + 0.587*roi[...,1] + 0.114*roi[...,2]).astype(np.float64)
        quant512 = np.clip(np.rint(gray/255.0*511.0).astype(np.int32), 0, 511)
        initial_name = "intensity_map.csv"
        if current_path[0]:
            base = os.path.splitext(os.path.basename(current_path[0]))[0]
            initial_name = f"{base}_roi_{x}_{y}_{w}x{h}_512levels.csv"
        csv_path = filedialog.asksaveasfilename(title="Save CSV", defaultextension=".csv",
                                                 initialfile=initial_name, filetypes=[("CSV","*.csv")])
        if csv_path:
            try: np.savetxt(csv_path, quant512, fmt="%d", delimiter=",")
            except Exception as e: messagebox.showerror("Error", f"CSV write failed:\n{e}"); return
            log_fn(f"Image analysis CSV saved: {csv_path}")
        # Heatmap
        base_cmap = cm.get_cmap("viridis", 512)
        boundaries = np.arange(-0.5, 511.5+1, 1)
        norm = colors.BoundaryNorm(boundaries, base_cmap.N)
        hw = tk.Toplevel(win)
        hw.title("Heatmap"); hw.geometry("800x700")
        fig = Figure(figsize=(6,5), dpi=100); ax = fig.add_subplot(111)
        im = ax.imshow(quant512, cmap=base_cmap, norm=norm, origin="upper")
        ax.set_xlabel("X"); ax.set_ylabel("Y")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label("Level (0-511)")
        FigureCanvasTkAgg(fig, master=hw).get_tk_widget().pack(fill=tk.BOTH, expand=True)

    ttk.Button(top, text="Run", command=run_analysis).pack(side=tk.LEFT, padx=(0, 8))

    # Canvas
    cf = ttk.Frame(win); cf.pack(fill=tk.BOTH, expand=True)
    hbar = ttk.Scrollbar(cf, orient=tk.HORIZONTAL)
    vbar = ttk.Scrollbar(cf, orient=tk.VERTICAL)
    canvas = tk.Canvas(cf, bg="#333333", xscrollcommand=hbar.set, yscrollcommand=vbar.set, highlightthickness=0)
    hbar.config(command=canvas.xview); vbar.config(command=canvas.yview)
    canvas.grid(row=0, column=0, sticky="nsew"); vbar.grid(row=0, column=1, sticky="ns"); hbar.grid(row=1, column=0, sticky="ew")
    cf.rowconfigure(0, weight=1); cf.columnconfigure(0, weight=1)

    def canvas_click(event):
        if img_array[0] is None: return
        x = int(canvas.canvasx(event.x)); y = int(canvas.canvasy(event.y))
        entry_x.delete(0,tk.END); entry_x.insert(0,str(x))
        entry_y.delete(0,tk.END); entry_y.insert(0,str(y))
        confirm_roi()
    canvas.bind("<Button-1>", canvas_click)
