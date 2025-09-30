"""
title: XROSS - X-Ray Optics Simulation Software
tags:
    - multilayer
    - EUV optics
    - X-ray reflectivity
    - deposition optimization
authors: 
    - name: Naoki Hayase
      orcid: 0009-0005-4310-7961
      equal-contrib: first author
      affiliation: 1
affiliations:
    - University of Hyogo, Japan
      index: 1
date: 1st September 2025
bibliography: https://github.com/nhayase/XROSS
"""

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, ttk
import csv
import ctypes
import datetime
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from matplotlib import pyplot as plt
import numpy as np
import os
import optuna
import pandas as pd
from pathlib import Path
from itertools import zip_longest
import webbrowser
import re
from functools import lru_cache  

# XROSS main window
root = tk.Tk()
root.geometry('610x400')
root.title('XROSS - X-Ray Optics Simulation Software')

# ICON
current_dir = os.path.dirname(os.path.abspath(__file__)) 
icon_path = os.path.join(current_dir, 'favicon.ico') 
root.iconbitmap(icon_path)
myappid = 'mycompany.myproduct.subproduct.version'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# Global variables
subroutines = []
orphan_layers = []
current_subroutine = None
current_layer = None
results = []
csv_data = pd.DataFrame()
current_file_path = None
is_modified = False
external_parameters = {}
log_window = None   
console = None 
load_header_label = None  
nk_header_label = None
header_labels = []

# Position
def place_near_root(toplevel: tk.Toplevel, dx: int = 610, dy: int = -50) -> None:
    root.update_idletasks()
    x = root.winfo_rootx() + dx
    y = root.winfo_rooty() + dy
    toplevel.geometry(f"+{x}+{y}")

COLUMN_HEADERS = [
    '', 
    'Name',
    'n',
    'k',
    'Thickness (nm)',
    'Density (g/cm³)',
    'Roughness (nm)',
]
ORIGINAL_COLUMN_HEADERS = COLUMN_HEADERS.copy()

# Layer width
LAYER_PADX = 0
CHAR_PX = 7.5

COLUMN_WIDTHS = [5, 10, 10, 10, 15, 15, 15]
SELECT_COL_CHARS = 3
LOAD_COL_CHARS   = 6
NAME_COL_CHARS   = 20
SELECT_COL_PX = SELECT_COL_CHARS * CHAR_PX

def _entry_index_for(header: str):
    try:
        i = COLUMN_HEADERS.index(header) - 1  
        return i if i >= 0 else None
    except ValueError:
        return None

def _widths_px_all():
    base = [SELECT_COL_CHARS * CHAR_PX] + [w * CHAR_PX for w in COLUMN_WIDTHS[1:]]
    return base + [LOAD_COL_CHARS * CHAR_PX, NAME_COL_CHARS * CHAR_PX]

_recalc_pending = False
def recalc_column_widths():
    global _recalc_pending
    if _recalc_pending:
        return
    _recalc_pending = True

    def _do():
        global _recalc_pending
        _recalc_pending = False
        try:
            if 'label_frame' not in globals():
                return
            px = list(map(int, _widths_px_all()))
            col_load = len(COLUMN_WIDTHS)
            col_name = col_load + 1

            # Header
            for c, w in enumerate(px):
                label_frame.grid_columnconfigure(c, weight=(1 if c == col_name else 0), minsize=w)

            # Cells
            for obj in subroutines:
                if isinstance(obj, Subroutine):
                    for cell in obj.cells:
                        for c, w in enumerate(px):
                            cell.cell_frame.grid_columnconfigure(c, weight=(1 if c == col_name else 0), minsize=w)
                elif isinstance(obj, Cell):
                    for c, w in enumerate(px):
                        obj.cell_frame.grid_columnconfigure(c, weight=(1 if c == col_name else 0), minsize=w)
        except Exception:
            pass

    root.after_idle(_do)

def ensure_load_header():
    global load_header_label, nk_header_label
    if 'label_frame' not in globals():
        return

    col_load = len(COLUMN_WIDTHS)
    col_name = col_load + 1

    if len(header_labels) <= col_name:
        header_labels.extend([None] * (col_name + 1 - len(header_labels)))

    try:
        if load_header_label and load_header_label.winfo_exists():
            load_header_label.grid_forget()
        load_header_label = tk.Label(label_frame, text="Load", relief='solid', bd=1, width=8)
        load_header_label.grid(row=0, column=col_load, sticky='nsew', padx=0)
        header_labels[col_load] = load_header_label
    except Exception:
        pass

    try:
        if nk_header_label and nk_header_label.winfo_exists():
            nk_header_label.grid_forget()
        nk_header_label = tk.Label(label_frame, text="nk file name", relief='solid', bd=1, highlightthickness=0)
        nk_header_label.grid(row=0, column=col_name, sticky='nsew', padx=0)
        header_labels[col_name] = nk_header_label
    except Exception:
        pass

    recalc_column_widths()

def refresh_load_buttons_layout():
    ensure_load_header()
    col_load = len(COLUMN_WIDTHS)
    col_name = col_load + 1

    def _cells():
        for obj in subroutines:
            if isinstance(obj, Subroutine):
                for c in obj.cells:
                    yield c
            elif isinstance(obj, Cell):
                yield obj

    for cell in _cells():
        if hasattr(cell, "cell_frame"):
            try:
                cell.cell_frame.grid_columnconfigure(col_load, weight=0, minsize=LOAD_COL_CHARS * CHAR_PX)
                if hasattr(cell, "load_button"):
                    cell.load_button.grid(row=0, column=col_load, sticky='nsew', padx=0)
                cell.cell_frame.grid_columnconfigure(col_name, weight=1, minsize=NAME_COL_CHARS * CHAR_PX)
                if hasattr(cell, "nk_entry"):
                    cell.nk_entry.grid(row=0, column=col_name, sticky='nsew', padx=0)
            except Exception:
                pass

        if hasattr(cell, "place_freeze_checkboxes"):
            try:
                cell.place_freeze_checkboxes()
            except Exception:
                pass

    recalc_column_widths()

@lru_cache(maxsize=64)
def _parse_nk_file_cached_impl(path: str):
    lamA, n_list, k_list = [], [], []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            s = s.split('#')[0].split('//')[0].split(';')[0].strip()
            if not s:
                continue
            parts = re.split(r'[,\s]+', s)
            if len(parts) < 3:
                continue
            try:
                la = float(parts[0]); n_val = float(parts[1]); k_val = float(parts[2])
            except ValueError:
                continue
            lamA.append(la); n_list.append(n_val); k_list.append(k_val)
    if not lamA:
        raise ValueError("No numeric rows like 'lambda[Å] n k' were found.")
    lamA = np.asarray(lamA, float)
    n_arr = np.asarray(n_list, float)
    k_arr = np.asarray(k_list, float)
    lam_nm = lamA / 10.0  # Å → nm
    idx = np.argsort(lam_nm)
    lam_nm = lam_nm[idx]; n_arr = n_arr[idx]; k_arr = k_arr[idx]
    uniq, inv = np.unique(lam_nm, return_index=True)
    lam_nm = lam_nm[inv]; n_arr = n_arr[inv]; k_arr = k_arr[inv]
    return lam_nm, n_arr, k_arr

class Cell:
    def __init__(self, parent):
        self.layer_frames = []
        self.entries = []
        self.selected = False
        
        self.cell_frame = tk.Frame(parent, bd=1, relief='solid')
        self.cell_frame.pack(fill='x', padx=LAYER_PADX)
        self.layer_frames.append(self.cell_frame)
        self.cell_frame.grid_columnconfigure(0, weight=0, minsize=SELECT_COL_PX)

        self.select_button = tk.Label(self.cell_frame, text=' ', bg='lightgrey', relief='solid', bd=1, highlightthickness=0)
        self.select_button.grid(row=0, column=0, sticky='nsew')
        self.select_button.bind("<Button-1>", self.on_click)
        
        for col, width in enumerate(COLUMN_WIDTHS[1:], start=1):
            e = tk.Entry(self.cell_frame, width=width, bd=1, relief='solid', justify='left', highlightthickness=0)
            e.grid(row=0, column=col, sticky='nsew')
            e.bind("<KeyRelease>", lambda e: mark_as_modified())
            self.entries.append(e)

        self.freeze_vars = {
            'thk': tk.BooleanVar(value=False),
            'den': tk.BooleanVar(value=False),
            'rou': tk.BooleanVar(value=False),
        }
        self.freeze_cbs = {}  

        self.nk_data = None   
        self.nk_path = None

        # Load
        self.load_button = tk.Button(self.cell_frame, text='Click', width=7, command=self.load_nk, bd=1, highlightthickness=0)
        # nk file 
        self.nk_var = tk.StringVar(value="")
        self.nk_entry = tk.Entry(
            self.cell_frame, textvariable=self.nk_var,
            bd=1, relief='solid', justify='left', highlightthickness=0,
            state='disabled', disabledbackground='white', disabledforeground='black'
        )

        self.place_load_button()
        self.place_freeze_checkboxes()
        recalc_column_widths()

    def place_load_button(self):
        col_load = len(COLUMN_WIDTHS)
        col_name = col_load + 1
        try:
            self.cell_frame.grid_columnconfigure(col_load, weight=0, minsize=LOAD_COL_CHARS * CHAR_PX)
            self.load_button.grid(row=0, column=col_load, sticky='nsew', padx=0)
            self.cell_frame.grid_columnconfigure(col_name, weight=1, minsize=NAME_COL_CHARS * CHAR_PX)
            self.nk_entry.grid(row=0, column=col_name, sticky='nsew', padx=0)
        except Exception:
            pass

    def place_freeze_checkboxes(self):
        idx_thk = _entry_index_for('Thickness (nm)')
        idx_den = _entry_index_for('Density (g/cm³)')
        idx_rou = _entry_index_for('Roughness (nm)')

        mapping = [('thk', idx_thk), ('den', idx_den), ('rou', idx_rou)]
        for key, idx in mapping:
            if idx is None or idx >= len(self.entries) or self.entries[idx] is None:
                if key in self.freeze_cbs and self.freeze_cbs[key].winfo_exists():
                    try:
                        self.freeze_cbs[key].place_forget()
                        self.freeze_cbs[key].destroy()
                    except Exception:
                        pass
                self.freeze_cbs.pop(key, None)
                continue

            ent = self.entries[idx]
            cb = self.freeze_cbs.get(key)
            if cb is None or not cb.winfo_exists():
                cb = tk.Checkbutton(
                    self.cell_frame,
                    variable=self.freeze_vars[key],
                    padx=0, pady=0,
                    bd=0, highlightthickness=0,
                    takefocus=False
                )
                cb.bind("<ButtonRelease-1>", lambda _e: mark_as_modified())
                self.freeze_cbs[key] = cb

            try:
                cb.place(in_=ent, relx=1.0, x=-14, rely=0.5, anchor='e')
            except Exception:
                pass

    def get_freeze_states(self):
        return {
            'thk': bool(self.freeze_vars['thk'].get()),
            'den': bool(self.freeze_vars['den'].get()),
            'rou': bool(self.freeze_vars['rou'].get()),
        }

    def load_nk(self):
        path = filedialog.askopenfilename(
            title="Select nk file (λ[Å] n k)",
            filetypes=[("nk files","*.nk *.txt *.dat *.csv"), ("All files","*.*")]
        )
        if not path:
            return
        try:
            lam_nm, n, k = self._parse_nk_file(path)
            self.nk_data = {"lam_nm": lam_nm, "n": n, "k": k}
            self.nk_path = path

            if not (self.entries and self.entries[0].get().strip()):
                base = os.path.splitext(os.path.basename(path))[0]
                self.entries[0].insert(0, base)

            self.nk_entry.config(state='normal')
            self.nk_var.set(os.path.basename(path))
            self.nk_entry.config(state='disabled')

            ts = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            if console is None or not console.winfo_exists():
                create_log_window()
            console.insert(tk.END, f"{ts} Loaded nk: {os.path.basename(path)} (N={len(lam_nm)}). Unit Å→nm.\n")
            console.see(tk.END)
            recalc_column_widths()
        except Exception as e:
            messagebox.showerror("nk load error", f"Failed to read nk file:\n{path}\n\n{e}")

    def _parse_nk_file(self, path):
        # --- REPLACE: use cached parser ---
        return _parse_nk_file_cached_impl(path)

    def on_click(self, event):
        global current_layer, current_subroutine
        if self.selected:
            self.select_button.config(bg='lightgrey')
            self.selected = False
            current_layer = None
        else:
            if current_layer is not None:
                current_layer.select_button.config(bg='lightgrey')
                current_layer.selected = False
            if current_subroutine is not None:
                current_subroutine.label.config(bg='lightgrey')
                current_subroutine.selected = False
            self.select_button.config(bg='blue')
            self.selected = True
            current_layer = self
            current_subroutine = None

    def to_dict(self):
        return {
            'entries': [entry.get() for entry in self.entries]
        }

class Subroutine:
    def __init__(self, name, parent):
        self.name = name
        self.loop_count = 1
        self.frame = tk.Frame(parent)
        self.frame.pack(fill='x', pady=10)
        
        self.header_frame = tk.Frame(self.frame)
        self.header_frame.pack(fill='x')

        self.toggle_button = tk.Button(self.header_frame, text='+', width=2, command=self.toggle)
        self.toggle_button.pack(side=tk.LEFT)

        self.up_button = tk.Button(self.header_frame, text='↑', width=2, command=self.move_layer_up)
        self.up_button.pack(side=tk.LEFT)  

        self.down_button = tk.Button(self.header_frame, text='↓', width=2, command=self.move_layer_down)
        self.down_button.pack(side=tk.LEFT)  

        self.label = tk.Label(self.header_frame, text=f"{name}({self.loop_count})", font=('Arial', 14), bg='lightgrey')
        self.label.pack(side=tk.LEFT, fill='x')
        self.label.bind("<Button-1>", self.on_click)
        self.label.bind("<Button-3>", self.on_right_click)  

        self.cells_frame = tk.Frame(self.frame)
        self.cells_frame.pack(fill='x')

        self.cells = []
        self.selected = False
        self.collapsed = False

    def add_cell(self):
        cell = Cell(self.cells_frame)
        self.cells.append(cell)
        refresh_load_buttons_layout()  

    def move_layer_up(self):
        if current_layer and current_layer.selected:
            index = self.cells.index(current_layer)
            if index > 0:
                self.cells[index], self.cells[index - 1] = self.cells[index - 1], self.cells[index]
                self.repack_layers()
            mark_as_modified()
            recalc_column_widths()

    def move_layer_down(self):
        if current_layer and current_layer.selected:
            index = self.cells.index(current_layer)
            if index < len(self.cells) - 1:
                self.cells[index], self.cells[index + 1] = self.cells[index + 1], self.cells[index]
                self.repack_layers()
            mark_as_modified()
            recalc_column_widths()

    def repack_layers(self):
        for cell in self.cells:
            cell.cell_frame.pack_forget()
            cell.cell_frame.pack(fill='x', padx=LAYER_PADX)

    def on_click(self, event):
        global current_subroutine, current_layer
        if current_subroutine == self:
            self.label.config(bg='lightgrey')
            self.selected = False
            current_subroutine = None
        else:
            if current_subroutine is not None:
                current_subroutine.label.config(bg='lightgrey')
                current_subroutine.selected = False
            if current_layer is not None:
                current_layer.select_button.config(bg='lightgrey')
                current_layer.selected = False
            self.label.config(bg='blue')
            self.selected = True
            current_subroutine = self
            current_layer = None

    def on_right_click(self, event):
        new_name = simpledialog.askstring("Rename Subroutine", "Enter new subroutine name:", initialvalue=self.name)
        if new_name:
            self.name = new_name
            mark_as_modified()

        loop_count = simpledialog.askinteger("Set Loop Count", "Enter loop count:", initialvalue=self.loop_count)
        if loop_count:
            self.loop_count = loop_count
            mark_as_modified()

        self.label.config(text=f"{self.name}({self.loop_count})")

    def toggle(self):
        self.collapsed = not self.collapsed
        self.toggle_button.config(text='+' if self.collapsed else '-')
        if self.collapsed:
            self.cells_frame.pack_forget()
        else:
            self.cells_frame.pack(fill='x')

    def to_dict(self):
        return {
            'name': self.name,
            'loop_count': self.loop_count,
            'cells': [cell.to_dict() for cell in self.cells]
        }

def mark_as_modified():
    global is_modified
    is_modified = True
    update_title()

def mark_as_unmodified():
    global is_modified
    is_modified = False
    update_title()

def update_title():
    if current_file_path:
        title = f"XROSS - {os.path.basename(current_file_path)}"
        if is_modified:
            title += " *"
    else:
        title = "XROSS"
    root.title(title)

def add_subroutine():
    name = simpledialog.askstring("Input", "Enter subroutine name:")
    if name:
        subroutine = Subroutine(name, param_frame)
        subroutines.append(subroutine)
        subroutine.label.bind("<Button-1>", lambda event, s=subroutine: select_subroutine(s))
        mark_as_modified()
        recalc_column_widths()

def delete_subroutine():
    global current_subroutine
    if current_subroutine and current_subroutine.selected:
        current_subroutine.frame.destroy()
        subroutines.remove(current_subroutine)
        current_subroutine = None
        mark_as_modified()
        recalc_column_widths()

def select_subroutine(subroutine):
    global current_subroutine, current_layer
    if current_subroutine == subroutine:
        current_subroutine.label.config(bg='lightgrey')
        current_subroutine.selected = False
        current_subroutine = None
    else:
        if current_subroutine:
            current_subroutine.label.config(bg='lightgrey')
            current_subroutine.selected = False
        if current_layer:
            current_layer.select_button.config(bg='lightgrey')
            current_layer.selected = False
            current_layer = None
        subroutine.label.config(bg='blue')
        subroutine.selected = True
        current_subroutine = subroutine

def add_layer():
    if current_subroutine and current_subroutine.selected:
        current_subroutine.add_cell()
        mark_as_modified()
    else:
        cell = Cell(param_frame)
        orphan_layers.append(cell)
        subroutines.append(cell)
        mark_as_modified()
    refresh_load_buttons_layout()  # layout + width recalc

def delete_layer():
    global current_layer
    if current_layer and current_layer.selected:
        for subroutine in subroutines:
            if isinstance(subroutine, Subroutine) and current_layer in subroutine.cells:
                subroutine.cells.remove(current_layer)
                break
        if current_layer in orphan_layers:
            orphan_layers.remove(current_layer)
        for frame in current_layer.layer_frames:
            frame.destroy()
        current_layer = None  
        update_cells_list()
        mark_as_modified()
        recalc_column_widths()

def move_selected_down():
    global current_layer, current_subroutine
    if current_layer and current_layer.selected:
        move_layer_down(current_layer)
    elif current_subroutine and current_subroutine.selected:
        move_subroutine_down(current_subroutine)
    mark_as_modified()
    recalc_column_widths()

def move_selected_up():
    global current_layer, current_subroutine
    if current_layer and current_layer.selected:
        move_layer_up(current_layer)
    elif current_subroutine and current_subroutine.selected:
        move_subroutine_up(current_subroutine)
    mark_as_modified()
    recalc_column_widths()

def move_layer_down(layer):
    index = subroutines.index(layer)
    if index < len(subroutines) - 1:
        subroutines[index], subroutines[index + 1] = subroutines[index + 1], subroutines[index]
        for item in subroutines:
            if isinstance(item, Subroutine):
                item.frame.pack_forget()
                item.frame.pack(fill='x', pady=10)
            elif isinstance(item, Cell):
                item.cell_frame.pack_forget()
                item.cell_frame.pack(fill='x', padx=LAYER_PADX)

def move_layer_up(layer):
    index = subroutines.index(layer)
    if index > 0:
        subroutines[index], subroutines[index - 1] = subroutines[index - 1], subroutines[index]
        for item in subroutines:
            if isinstance(item, Subroutine):
                item.frame.pack_forget()
                item.frame.pack(fill='x', pady=10)
            elif isinstance(item, Cell):
                item.cell_frame.pack_forget()
                item.cell_frame.pack(fill='x', padx=LAYER_PADX)

def move_subroutine_down(subroutine):
    index = subroutines.index(subroutine)
    if index < len(subroutines) - 1:
        subroutines[index], subroutines[index + 1] = subroutines[index + 1], subroutines[index]
        for item in subroutines:
            if isinstance(item, Subroutine):
                item.frame.pack_forget()
                item.frame.pack(fill='x', pady=10)
            elif isinstance(item, Cell):
                item.cell_frame.pack_forget()
                item.cell_frame.pack(fill='x', padx=LAYER_PADX)

def move_subroutine_up(subroutine):
    index = subroutines.index(subroutine)
    if index > 0:
        subroutines[index], subroutines[index - 1] = subroutines[index - 1], subroutines[index]
        for item in subroutines:
            if isinstance(item, Subroutine):
                item.frame.pack_forget()
                item.frame.pack(fill='x', pady=10)
            elif isinstance(item, Cell):
                item.cell_frame.pack_forget()
                item.cell_frame.pack(fill='x', padx=LAYER_PADX)

def _cell_alive(cell) -> bool:
    return bool(cell.layer_frames) and cell.layer_frames[0].winfo_exists()

def update_cells_list() -> None:
    global subroutines, orphan_layers
    new_subs, new_orphans = [], []
    for obj in subroutines:
        if isinstance(obj, Subroutine):
            obj.cells = [c for c in obj.cells if _cell_alive(c)]
            if obj.cells or obj.selected:
                new_subs.append(obj)
        elif isinstance(obj, Cell) and _cell_alive(obj):
            new_orphans.append(obj)
    subroutines = new_subs + new_orphans
    orphan_layers = new_orphans

def all_clear():
    if messagebox.askyesno("Confirm", "Are you sure you want to clear all Layers and Subroutines?"):
        clear_current_state()
        timestamp = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        console.insert(tk.END, f"{timestamp} All Layers and Subroutines cleared.\n")
        mark_as_modified()
        recalc_column_widths()

def create_log_window() -> None:
    global log_window, console
    if log_window and log_window.winfo_exists():
        return                                   

    log_window = tk.Toplevel(root)
    log_window.iconbitmap(icon_path)
    log_window.title("Log Window")
    log_window.geometry("610x200")
    place_near_root(log_window)

    log_window.protocol("WM_DELETE_WINDOW", lambda: log_window.withdraw())

    sb_x = tk.Scrollbar(log_window, orient="horizontal")
    sb_y = tk.Scrollbar(log_window, orient="vertical")
    sb_x.pack(side="bottom", fill="x")
    sb_y.pack(side="right",  fill="y")

    console = tk.Text(log_window,
                      wrap="none",
                      xscrollcommand=sb_x.set,
                      yscrollcommand=sb_y.set)
    console.pack(side="left", fill="both", expand=True)

    sb_x.config(command=console.xview)
    sb_y.config(command=console.yview)

def record():
    if not (log_window and log_window.winfo_exists()):
        create_log_window()
    else:
        place_near_root(log_window)
    log_window.deiconify()
    log_window.lift()
    
def depict_layer():

    layer_colors = {}                    
    draw_layers  = []                    
    brackets     = []                    
    single_labels = []                   
    z_curr = 0.0

    cmap  = plt.cm.get_cmap('tab20', 20)
    color_counter = 0

    for obj in subroutines:
        if isinstance(obj, Subroutine):
            base_cols = []
            for cell in obj.cells:
                if cell not in layer_colors:
                    layer_colors[cell] = color_counter
                    color_counter += 1
                base_cols.append(layer_colors[cell])

            z_start = z_curr
            for _ in range(max(1, int(obj.loop_count))):
                for cell, cidx in zip(obj.cells, base_cols):
                    try:
                        thk = max(float(cell.entries[3].get()), 1e-3)
                    except Exception:
                        thk = 1.0
                    draw_layers.append((thk, cidx))
                    z_curr += thk
            z_end = z_curr
            brackets.append((z_start, z_end, obj.name, obj.loop_count))

        elif isinstance(obj, Cell):
            if obj not in layer_colors:
                layer_colors[obj] = color_counter
                color_counter += 1
            try:
                thk = max(float(obj.entries[3].get()), 1e-3)
            except Exception:
                thk = 1.0
            draw_layers.append((thk, layer_colors[obj]))
            single_labels.append((z_curr + thk / 2,
                                  obj.entries[0].get() or
                                  f"Layer{len(draw_layers)}"))
            z_curr += thk

    if not draw_layers:
        messagebox.showwarning("No Layer", "No Layer to depict.")
        return

    fig = Figure(figsize=(4, 6), dpi=100)
    ax  = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('none')
    fig.patch.set_facecolor('white')
    ax.set_xlim(0, 1.35)
    ax.set_ylim(0, 1)
    ax.set_zlim(0, z_curr * 1.05)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
    ax._axis3don = False

    z0 = 0.0
    for thk, cidx in draw_layers:
        ax.bar3d(0, 0, z0, 1, 1, thk,
                 color=cmap(cidx % cmap.N), shade=True, alpha=0.9)
        z0 += thk

    for z_mid, txt in single_labels:
        ax.text(1.05, 0.5, z_mid, txt,
                ha='left', va='center', fontsize=8, zdir=None)

    for z0, z1, name, lp in brackets:
        z_mid = 0.5 * (z0 + z1)
        height_frac = (z1 - z0) / z_curr
        b_font = max(8, int(35 * height_frac))
        ax.text(1.02, 0.5, z_mid, "}", fontsize=b_font,
                ha='left', va='center', zdir=None)
        ax.text(1.10, 0.5, z_mid, f"{name} ({lp})",
                ha='left', va='center', fontsize=8, zdir=None)

    win = tk.Toplevel(root)
    win.iconbitmap(icon_path)
    win.title("Depiction Window")
    place_near_root(win)
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)
    NavigationToolbar2Tk(canvas, win)


# Log
def log_message_to_file(message):
    log_file_path = os.path.join(current_dir, 'log.txt')
    with open(log_file_path, 'a') as log_file:
        log_file.write(message)

# Save function
def save_state(file_path: str) -> None:
    update_cells_list()
    rows, max_param = [], 0
    for obj in subroutines:
        if isinstance(obj, Subroutine):
            for c in obj.cells:
                if not _cell_alive(c):
                    continue
                params = [e.get() for e in c.entries]
                rows.append([obj.name, str(obj.loop_count)] + params)
                max_param = max(max_param, len(params))
        elif isinstance(obj, Cell) and _cell_alive(obj):
            params = [e.get() for e in obj.entries]
            rows.append(["Orphan", ""] + params)
            max_param = max(max_param, len(params))
    header = ["Subroutine", "Loop Count"] + [f"Param{i+1}" for i in range(max_param)]
    fixed = [(r + [""] * (len(header) - len(r)))[:len(header)] for r in rows]
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(fixed)
    ts = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    msg = f"{ts} Save {file_path}\n"
    console.insert(tk.END, msg)
    log_message_to_file(msg)
    mark_as_unmodified()


# Load csv files
def load_state(file_path: str) -> None:

    global subroutines, orphan_layers
    df = pd.read_csv(file_path, dtype=str).fillna("")

    clear_current_state()

    for _, row in df.iterrows():
        name = row["Subroutine"]
        loop = row["Loop Count"]
        params = [v for v in row[2:].values]     

        # Orphan layer
        if name == "Orphan":
            cell = Cell(param_frame)
            for ent, val in zip_longest(cell.entries, params, fillvalue=""):
                ent.delete(0, tk.END)
                ent.insert(0, val)
            orphan_layers.append(cell)
            subroutines.append(cell)
            continue

        # Subroutine
        sub = next((s for s in subroutines
                    if isinstance(s, Subroutine) and s.name == name), None)
        if sub is None:
            sub = Subroutine(name, param_frame)
            subroutines.append(sub)

        # loop_count
        try:
            sub.loop_count = int(loop) if str(loop).strip() else 1
        except ValueError:
            sub.loop_count = 1
        sub.label.config(text=f"{sub.name}({sub.loop_count})")

        # add layer cell
        cell = Cell(sub.cells_frame)
        for ent, val in zip_longest(cell.entries, params, fillvalue=""):
            ent.delete(0, tk.END)
            ent.insert(0, val)
        sub.cells.append(cell)

    refresh_load_buttons_layout() 
    mark_as_unmodified()
    recalc_column_widths()

# Save csv files
def save_file() -> None:
    global current_file_path
    try:
        if current_file_path:
            save_state(current_file_path)
        else:
            save_as_file()
    except Exception as e:
        messagebox.showerror("Save error", f"Failed to save:\n{e}")

# Save as... csv files
def save_as_file() -> None:
    global current_file_path
    geo_dir = os.path.join(current_dir, 'geo')   
    path = filedialog.asksaveasfilename(
        initialdir=geo_dir,                      
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")])
    if not path:
        return
    try:
        save_state(path)
        current_file_path = path
        update_title()
    except Exception as e:
        messagebox.showerror("Save error", f"Failed to save:\n{e}")

def clear_current_state():
    global subroutines, orphan_layers, current_subroutine, current_layer
    for subroutine in subroutines:
        if isinstance(subroutine, Subroutine):
            subroutine.frame.destroy()
        elif isinstance(subroutine, Cell):
            for frame in subroutine.layer_frames:
                frame.destroy()
    subroutines.clear()
    orphan_layers.clear()
    current_subroutine = None
    current_layer = None

def open_file():
    global current_file_path
    geometry_path = os.path.join(current_dir, 'geo')
    if is_modified:
        if not confirm_discard_changes():
            return
    file_path = filedialog.askopenfilename(initialdir=geometry_path, filetypes=[('CSV files', '*.csv')])
    if file_path:
        clear_current_state()
        load_state(file_path)
        current_file_path = file_path
        update_title()
        recalc_column_widths()

def load_csv(file_path):
    global csv_data
    csv_data = pd.read_csv(file_path)
    console.insert(tk.END, f"Loaded {file_path}\n")
    mark_as_unmodified()
        
def confirm_discard_changes():
    result = messagebox.askyesnocancel("Save Changes", f"{os.path.basename(current_file_path) if current_file_path else 'Untitled'} has been changed. Do you want to save changes?")
    if result is None:
        return False
    if result:
        save_file()
    return True

def on_exit():
    if is_modified:
        if not confirm_discard_changes():
            return
    root.destroy()

def open_file_new_window():
    global current_file_path
    geometry_path = os.path.join(current_dir, 'math')
    if is_modified:
        if not confirm_discard_changes():
            return
    file_path = filedialog.askopenfilename(initialdir=geometry_path, filetypes=[('Python files', '*.py')])
    if file_path:
        clear_current_state()
        load_state(file_path)
        current_file_path = file_path
        update_title()
        recalc_column_widths()

def load_py(file_path):
    global csv_data
    csv_data = pd.read_csv(file_path)
    console.insert(tk.END, f"Loaded {file_path}\n")
    mark_as_unmodified()

def save_file_new_window():
    global current_file_path
    if current_file_path:
        save_state(current_file_path)
    else:
        save_as_file()

def save_as_file_new_window():
    global current_file_path
    file_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files', '*.csv')])
    if file_path:
        current_file_path = file_path
        save_state(file_path)
        update_title()


# Parameter
def calculate_thickness(entries):
    try:
        thickness = float(entries[1].get())
    except ValueError:
        tk.messagebox.showerror("Input Error", "Please make sure to enter valid values for all properties.")
        return None

    return thickness

def create_thickness_graph():
    if len(subroutines) < 2:
        tk.messagebox.showerror("Input Error", "Please make sure to select parameters.")
        return
    thickness_values = []
    for subroutine in subroutines:
        if isinstance(subroutine, Subroutine):
            for cell in subroutine.cells:
                thickness = calculate_thickness(cell.entries)
                if thickness is not None:
                    thickness_values.append(thickness)

    # Create New Figures
    fig = Figure(figsize=(5, 4), dpi=1000)
    ax = fig.add_subplot(111)
    
    # Plot thickness values
    ax.plot(thickness_values[0], thickness_values[1], 'ro-')  
    ax.set_xlabel("Thickness of the initial layer")
    ax.set_ylabel("Thickness of the first added layer")
    ax.grid(True)

    # Create a new window and draw the figure in it
    new_window = tk.Toplevel(root)
    new_window.iconbitmap(icon_path)
    new_window.geometry("500x500")
    canvas = FigureCanvasTkAgg(fig, master=new_window)
    canvas.draw()
    canvas.get_tk_widget().pack()
    toolbar = NavigationToolbar2Tk(canvas, new_window)
    toolbar.update()

def save_graph(fig):
    filename = filedialog.asksaveasfilename(defaultextension='.png')
    if fig:
        fig.savefig(filename)

def output_to_csv():
    if not results:
        timestamp = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        log_message = f'{timestamp} No results to output.\n'
        console.insert(tk.END, log_message)
        log_message_to_file(log_message)
        return

    df = pd.DataFrame(results)
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    filename = filedialog.asksaveasfilename(defaultextension='.csv', initialfile=f'{timestamp}_result.csv')
    df.to_csv(filename, index=False)
    log_message = f'Results have been saved to {filename}\n'
    console.insert(tk.END, log_message)
    log_message_to_file(log_message)


# ---------------------------------------------------------------------------
#  Source > EUV Optics
# ---------------------------------------------------------------------------

def load_euvr_file() -> None:

    COL_NAME  = 0   # Material
    COL_N     = 1   # Refractive index
    COL_K     = 2   # Extinction coefficient
    COL_THICK = 3   # Thickness (nm)
    COL_DENS  = 4   # Density (g/cm3) 
    COL_ROUGH = 5   # Roughness (nm)

    def reflectivity_sim(layer_stack, lam_nm, inc_deg):
        theta = np.radians(inc_deg)

        def kz(n, k):
            return (2 * np.pi / lam_nm) * (n - 1j * k) * np.cos(theta)

        def fresnel(n1, k1, s1, n2, k2, s2):
            kz1, kz2 = kz(n1, k1), kz(n2, k2)
            r12 = (kz1 - kz2) / (kz1 + kz2)
            return r12 * np.exp(-2 * (kz1 * kz2 * (s1 + s2)) ** 2)

        M = np.eye(2, dtype=complex)
        for j in range(len(layer_stack) - 1):
            n1, k1, d1, s1 = layer_stack[j]
            n2, k2, _,  s2 = layer_stack[j + 1]

            r12 = fresnel(n1, k1, s1, n2, k2, s2)
            kz1 = kz(n1, k1)

            M_propagate = np.array([[np.exp(-1j * kz1 * d1), 0],
                                    [0, np.exp(+1j * kz1 * d1)]])
            M_boundary  = np.array([[1 / (1 + r12), r12 / (1 + r12)],
                                    [r12 / (1 + r12), 1 / (1 + r12)]])
            M = M_boundary @ M_propagate @ M

        r_tot = -M[1, 0] / M[1, 1]
        return abs(r_tot) ** 2, np.angle(r_tot)

    def build_pair_template_and_repeat():
        sub = next((s for s in subroutines if isinstance(s, Subroutine)), None)
        if sub:
            cells  = sub.cells
            repeat = max(1, int(sub.loop_count))
        else:
            cells  = orphan_layers
            repeat = 1

        if not cells:
            return [], 0, [] 

        pair_tpl = []
        for cell in cells:
            try:
                n   = float(cell.entries[COL_N    ].get())
                k   = float(cell.entries[COL_K    ].get())
                d   = float(cell.entries[COL_THICK].get())
                sig = float(cell.entries[COL_ROUGH].get())
            except ValueError:
                raise ValueError("Please enter values for n, k, thickness, and roughness.")
            pair_tpl.append((n, k, d, sig))

        return pair_tpl, repeat, cells

    def perform_calculation():
        Vac = (1.0, 0.0, 0.0, 0.0)

        # Phase (Zeff)
        if var_phase.get():
            if any((var_pairs.get(), var_wl.get(), var_aoi.get(), var_dx.get())):
                return
            
            try:
                pair_tpl, n_pairs, _ = build_pair_template_and_repeat()
            except ValueError as err:
                messagebox.showerror("Model error", str(err)); return
            if len(pair_tpl) < 2:
                messagebox.showerror("Model error", "At least two Layers are required."); return

            try:
                lam_nm = float(wavelength_var.get())
                a_s    = float(aoi_start_var.get())
                a_e    = float(aoi_end_var.get())
                if a_s >= a_e: raise ValueError
            except ValueError:
                messagebox.showerror("Input error", "AOI start / AOI end"); return

            cap = pair_tpl[0]  
            aoi = np.linspace(a_s, a_e, 200)
            phase = [reflectivity_sim(pair_tpl*n_pairs+[cap], lam_nm, a)[1] for a in aoi]
            phase = np.unwrap(phase)
            
            fig = Figure(figsize=(5,4), dpi=100); ax = fig.add_subplot(111)
            ax.plot(aoi, phase, marker='o')
            ax.set_xlabel("AOI (rad)"); ax.set_ylabel("Phase (rad)"); ax.grid()
            gwin = tk.Toplevel(root); gwin.iconbitmap(icon_path)
            gwin.title("EUV Optics Graphics")
            cvs = FigureCanvasTkAgg(fig, master=gwin)
            cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)
            NavigationToolbar2Tk(cvs, gwin)

            # CSV Output
            df = pd.DataFrame({"AOI(deg)": aoi, "Phase(rad)": phase})
            save_dir = os.path.join(current_dir, "save"); os.makedirs(save_dir, exist_ok=True)
            default = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_phase.csv")
            path = filedialog.asksaveasfilename(initialdir=save_dir,
                                                defaultextension=".csv",
                                                initialfile=default,
                                                filetypes=[("CSV files","*.csv")])            
            
            if path:
                df.to_csv(path, index=False)
                ts = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
                console.insert(tk.END, f"{ts} PHASE calculation executed. Saved: {path}\n")
                log_message_to_file(f"{ts} Saved {path}\n")
                console.see(tk.END)   
            return
        
        # Reflectivity
        try:
            pair_tpl, n_pairs, cells = build_pair_template_and_repeat()
        except ValueError as err:
            messagebox.showerror("Model error", str(err)); return
        if len(pair_tpl) < 2:
            messagebox.showerror("Model error", "At least two Layers are required."); return

        cap = pair_tpl[0]  

        if var_pairs.get() or var_wl.get() or var_aoi.get():
            try:
                lam_nm  = float(wavelength_var.get())
                inc_deg = float(angle_var.get())
            except ValueError:
                messagebox.showerror("Input error", "Wavelength / Angle"); return

            plot_marker = 'o'
            
            # Pairs scan
            if var_pairs.get():
                x = list(range(1, n_pairs+1))
                y = [reflectivity_sim(pair_tpl*m, lam_nm, inc_deg)[0]*100
                     for m in x]
                xlabel, fname_tag = "Pairs", "pairs"
                
            # Wavelength scan
            elif var_wl.get():
                n_layer = len(pair_tpl)

                if not all(getattr(c, "nk_data", None) is not None for c in cells[:n_layer]):
                    messagebox.showerror(
                        "nk required",
                        "please load the nk file for all layers."
                    )
                    return

                try:
                    lam_s = float(lam_start_var.get())
                    lam_e = float(lam_end_var.get())
                    if lam_s <= 0 or lam_e <= 0 or lam_s >= lam_e:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Input error", "λ start / λ end"); return

                lam_mins = [float(np.min(c.nk_data["lam_nm"])) for c in cells[:n_layer]]
                lam_maxs = [float(np.max(c.nk_data["lam_nm"])) for c in cells[:n_layer]]
                lam_lo = max(lam_mins)
                lam_hi = min(lam_maxs)
                eval_lo = max(lam_s, lam_lo)
                eval_hi = min(lam_e, lam_hi)
                if eval_lo >= eval_hi:
                    messagebox.showerror("Range error",
                        "Specified λ range is outside the overlap of nk data across layers.")
                    return

                NPTS = 600
                x_uniform = np.linspace(eval_lo, eval_hi, NPTS)
                specials = []
                for j in range(n_layer):
                    lam_arr_j = np.asarray(cells[j].nk_data["lam_nm"], float)
                    specials.append(lam_arr_j[(lam_arr_j >= eval_lo) & (lam_arr_j <= eval_hi)])
                if specials:
                    specials = np.concatenate(specials)
                else:
                    specials = np.array([], dtype=float)

                x = np.unique(np.round(np.concatenate([x_uniform, specials]), 12))
                x = x[(x >= eval_lo) & (x <= eval_hi)]

                n_vals = []
                k_vals = []
                for j in range(n_layer):
                    lam_arr = np.asarray(cells[j].nk_data["lam_nm"], float)
                    n_arr   = np.asarray(cells[j].nk_data["n"], float)
                    k_arr   = np.asarray(cells[j].nk_data["k"], float)

                    n_interp = np.interp(x, lam_arr, n_arr)  
                    k_interp = np.interp(x, lam_arr, k_arr)  
                    n_vals.append(n_interp)
                    k_vals.append(k_interp)

                y = []
                for i, lam in enumerate(x):
                    tpl_mod = []
                    for j in range(n_layer):
                        d_j, s_j = pair_tpl[j][2], pair_tpl[j][3]
                        tpl_mod.append((float(n_vals[j][i]), float(k_vals[j][i]), d_j, s_j))
                    cap_mod = tpl_mod[0]
                    R = reflectivity_sim([Vac] + tpl_mod * n_pairs + [cap_mod],
                                         float(lam), inc_deg)[0] * 100.0
                    y.append(R)

                xlabel, fname_tag = "Wavelength (nm)", "wl_linear_nk"
                plot_marker = None  

            # AOI scan
            else:
                try:
                    a_s, a_e = float(aoi_start_var.get()), float(aoi_end_var.get())
                    if a_s >= a_e: raise ValueError
                except ValueError:
                    messagebox.showerror("Input error", "AOI start / end"); return
                x = np.linspace(a_s, a_e, 200)
                y = [reflectivity_sim(pair_tpl*n_pairs, lam_nm, a)[0]*100
                     for a in x]
                xlabel, fname_tag = "AOI (deg)", "aoi"

            df = pd.DataFrame({xlabel: x, "Reflectivity(%)": y})

            fig = Figure(figsize=(5,4), dpi=100); ax = fig.add_subplot(111)
            if plot_marker is None:
                ax.plot(x, y, lw=1.5)
            else:
                ax.plot(x, y, marker=plot_marker)
            ax.set_xlabel(xlabel); ax.set_ylabel("Reflectivity (%)"); ax.grid()

        # Heatmap
        else:   
            try:
                lam_nm  = float(wavelength_var.get()); inc_deg = float(angle_var.get())
                dx0, dx1 = float(dx_start_var.get()), float(dx_end_var.get())
                dy0, dy1 = float(dy_start_var.get()), float(dy_end_var.get())
                if lam_nm<=0 or dx0<=0 or dy0<=0 or dx0>=dx1 or dy0>=dy1: raise ValueError
            except ValueError:
                messagebox.showerror("Input error", "λ / d_x, d_y Range"); return

            n_mesh = 60
            dx_vec = np.linspace(dx0, dx1, n_mesh)
            dy_vec = np.linspace(dy0, dy1, n_mesh)
            z = np.zeros((n_mesh, n_mesh))
            
            layer_x = (cells[0].entries[COL_NAME].get().strip()
                       if cells and len(cells) > 0 and cells[0].entries[COL_NAME].get().strip()
                       else "dₓ")
            layer_y = (cells[1].entries[COL_NAME].get().strip()
                       if cells and len(cells) > 1 and cells[1].entries[COL_NAME].get().strip()
                       else "dᵧ")

            (n1,k1,_,s1),(n2,k2,_,s2),*others = pair_tpl
            for iy, dy in enumerate(dy_vec):
                for ix, dx in enumerate(dx_vec):
                    tpl_mod = [(n1,k1,dx,s1),(n2,k2,dy,s2),*others]
                    stack   = tpl_mod*n_pairs  
                    z[iy, ix] = reflectivity_sim(stack, lam_nm, inc_deg)[0]*100

            records = []
            for iy, dy in enumerate(dy_vec):
                for ix, dx in enumerate(dx_vec):
                    records.append([dx, dy, z[iy, ix]])
            df = pd.DataFrame(records, columns=[f"{layer_x} (nm)", f"{layer_y} (nm)", "Reflectivity (%)"])            
            fname_tag = "heatmap"

            fig = Figure(figsize=(5.4,4.4), dpi=100); ax = fig.add_subplot(111)
            im = ax.imshow(z, origin="lower", aspect="auto",
                           extent=[dx_vec[0], dx_vec[-1], dy_vec[0], dy_vec[-1]],
                           cmap="viridis")
            ax.set_xlabel(f"{layer_x} (nm)"); ax.set_ylabel(f"{layer_y} (nm)")
            fig.colorbar(im, ax=ax).set_label("Reflectivity (%)")

        # Draw & Save
        gwin = tk.Toplevel(root); gwin.iconbitmap(icon_path); gwin.title("EUV Optics Graphics")
        cvs = FigureCanvasTkAgg(fig, master=gwin); cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs, gwin)

        save_dir = os.path.join(current_dir, "save")
        os.makedirs(save_dir, exist_ok=True)

        default = datetime.datetime.now().strftime(f"%Y%m%d_%H%M%S_{fname_tag}.csv")
        path = filedialog.asksaveasfilename(initialdir=save_dir,
                                            defaultextension=".csv",
                                            initialfile=default,
                                            filetypes=[("CSV files","*.csv")])
        if path:
            df.to_csv(path, index=False)
            ts = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            console.insert(tk.END, f"{ts} {fname_tag.upper()} calculation executed. Saved: {path}\n")
            log_message_to_file(f"{ts} Saved {path}\n")
            console.see(tk.END)

    # Multi-CSV button
    def open_multi_csv():
        save_dir = os.path.join(current_dir, "save")
        os.makedirs(save_dir, exist_ok=True)

        paths = filedialog.askopenfilenames(
            title="Select CSV files",
            initialdir=save_dir,
            filetypes=[("CSV files", "*.csv")]
        )
        if not paths:
            return

        try:
            dfs = []
            header_list = []
            ncols_set = set()
            for p in paths:
                df = pd.read_csv(p)
                if df.shape[1] < 2:
                    messagebox.showerror(
                        "Multi-CSV error",
                        f"File '{os.path.basename(p)}' has fewer than 2 columns."
                    )
                    return
                dfs.append((p, df))
                headers = tuple(map(str, df.columns.tolist()))
                header_list.append(headers)
                ncols_set.add(len(headers))

            if len(ncols_set) != 1:
                messagebox.showerror(
                    "Multi-CSV error",
                    "All selected CSV files must have the same number of columns "
                    "(either all 2-column or all 3-column files)."
                )
                return

            n_cols = next(iter(ncols_set))

            ref_headers = header_list[0]
            mismatched = []
            for i, hdr in enumerate(header_list[1:], start=1):
                if hdr != ref_headers:
                    mismatched.append((os.path.basename(paths[i]), hdr))

            if mismatched:
                details = "\n".join([f"- {name}: {list(h)}" for name, h in mismatched])
                messagebox.showerror(
                    "Header mismatch",
                    "The parameter names (column headers) differ across selected files.\n\n"
                    "All files must share identical headers to plot together.\n\n"
                    f"Expected: {list(ref_headers)}\nMismatched:\n{details}"
                )
                return

            if n_cols == 2:
                xcol, ycol = ref_headers

                win_lines = tk.Toplevel(root)
                win_lines.iconbitmap(icon_path)
                win_lines.title("EUV Multi-CSV")
                place_near_root(win_lines)

                fig = Figure(figsize=(5.8, 4.4), dpi=100)
                ax = fig.add_subplot(111)

                any_plotted = False
                for p, df in dfs:
                    x = pd.to_numeric(df[xcol], errors="coerce")
                    y = pd.to_numeric(df[ycol], errors="coerce")
                    mask = x.notna() & y.notna()
                    if mask.any():
                        ax.plot(x[mask].to_numpy(), y[mask].to_numpy(),
                                lw=1.4, label=os.path.basename(p))
                        any_plotted = True

                if not any_plotted:
                    messagebox.showerror("Multi-CSV error", "No plottable numeric data found in the selected files.")
                    win_lines.destroy()
                    return

                ax.set_xlabel(xcol)
                ax.set_ylabel(ycol)
                ax.grid(True, alpha=0.35)
                ax.legend(loc="best", fontsize=8)

                cvs = FigureCanvasTkAgg(fig, master=win_lines)
                cvs.draw()
                cvs.get_tk_widget().pack(fill="both", expand=True)
                NavigationToolbar2Tk(cvs, win_lines)

            elif n_cols == 3:
                xcol, ycol, zcol = ref_headers

                win_maps = tk.Toplevel(root)
                win_maps.iconbitmap(icon_path)
                win_maps.title("EUV Multi-CSV (Heatmaps)")
                place_near_root(win_maps)

                nb = ttk.Notebook(win_maps)
                nb.pack(fill="both", expand=True)

                for p, df in dfs:
                    tab = ttk.Frame(nb)
                    nb.add(tab, text=os.path.basename(p))

                    x = pd.to_numeric(df[xcol], errors="coerce")
                    y = pd.to_numeric(df[ycol], errors="coerce")
                    z = pd.to_numeric(df[zcol], errors="coerce")
                    mask = x.notna() & y.notna() & z.notna()
                    x = x[mask].to_numpy()
                    y = y[mask].to_numpy()
                    z = z[mask].to_numpy()

                    if x.size == 0 or y.size == 0 or z.size == 0:
                        msg = f"No numeric data to plot in '{os.path.basename(p)}'."
                        lbl = tk.Label(tab, text=msg)
                        lbl.pack(padx=12, pady=12, anchor="w")
                        continue

                    xu = np.unique(np.round(x, 12))
                    yu = np.unique(np.round(y, 12))
                    if xu.size < 2 or yu.size < 2:
                        msg = f"Not enough unique {xcol}/{ycol} values to render a heatmap in '{os.path.basename(p)}'."
                        lbl = tk.Label(tab, text=msg)
                        lbl.pack(padx=12, pady=12, anchor="w")
                        continue

                    Z = np.full((len(yu), len(xu)), np.nan, float)
                    lut = {(round(xi, 12), round(yi, 12)): zi for xi, yi, zi in zip(x, y, z)}
                    for iy, yy in enumerate(yu):
                        ky = round(yy, 12)
                        for ix, xx in enumerate(xu):
                            Z[iy, ix] = lut.get((round(xx, 12), ky), np.nan)

                    fig = Figure(figsize=(5.8, 4.4), dpi=100)
                    ax = fig.add_subplot(111)
                    im = ax.imshow(
                        Z, origin="lower", aspect="auto",
                        extent=[xu[0], xu[-1], yu[0], yu[-1]]
                    )
                    ax.set_xlabel(xcol)
                    ax.set_ylabel(ycol)
                    cbar = fig.colorbar(im, ax=ax)
                    cbar.set_label(zcol)

                    cvs = FigureCanvasTkAgg(fig, master=tab)
                    cvs.draw()
                    cvs.get_tk_widget().pack(fill="both", expand=True)
                    NavigationToolbar2Tk(cvs, tab)

            else:
                messagebox.showerror(
                    "Unsupported CSV",
                    "Only 2-column (line) or 3-column (heatmap) CSVs are supported."
                )

        except Exception as e:
            messagebox.showerror("Multi-CSV error", str(e))

    # EUV Optics Window
    win = tk.Toplevel(root)
    win.iconbitmap(icon_path)
    win.title("EUV Optics Window")
    win.geometry("500x250")
    place_near_root(win)

    ctrl = tk.LabelFrame(win, text="Parameters", padx=6, pady=6)
    ctrl.pack(fill="x", padx=8, pady=(10, 4))
    
    tk.Button(ctrl, text="Calculation", width=12, bg="#5cb85c", fg="white",
              command=perform_calculation).grid(row=0, column=4, padx=(20, 4))

    # Multi-CSV button
    tk.Button(ctrl, text="Multi-CSV", width=12, bg="#5bc0de", fg="white",
              command=open_multi_csv).grid(row=1, column=4, padx=(20, 4))
    
    # Command 1
    tk.Label(ctrl, text="Angle of incidence (deg)").grid(row=0, column=0, sticky="e")
    angle_var = tk.DoubleVar(value=6.0)
    tk.Entry(ctrl, textvariable=angle_var, width=8).grid(row=0, column=1, padx=(2, 12))

    tk.Label(ctrl, text="Wavelength (nm)").grid(row=0, column=2, sticky="e")
    wavelength_var = tk.DoubleVar(value=13.5)
    tk.Entry(ctrl, textvariable=wavelength_var, width=8).grid(row=0, column=3, padx=2)
    
    # Command 2
    tk.Label(ctrl, text="λ start (nm)").grid(row=1, column=0, sticky="e")
    lam_start_var = tk.DoubleVar(value=12.5)
    tk.Entry(ctrl, textvariable=lam_start_var, width=8).grid(row=1, column=1, padx=(2, 12))

    tk.Label(ctrl, text="λ end (nm)").grid(row=1, column=2, sticky="e")
    lam_end_var = tk.DoubleVar(value=14.5)
    tk.Entry(ctrl, textvariable=lam_end_var, width=8).grid(row=1, column=3, padx=2)
    
    # Command 4
    tk.Label(ctrl, text="AOI start (deg)").grid(row=2, column=0, sticky="e")
    aoi_start_var = tk.DoubleVar(value=0)
    tk.Entry(ctrl, textvariable=aoi_start_var, width=8).grid(row=2, column=1, padx=(2, 12))

    tk.Label(ctrl, text="AOI end (deg)").grid(row=2, column=2, sticky="e")
    aoi_end_var = tk.DoubleVar(value=40.0)
    tk.Entry(ctrl, textvariable=aoi_end_var, width=8).grid(row=2, column=3, padx=2)
    
    # Command 5
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

    # Memo
    tk.Label(win, text="Fulfill parameters & Click the Calculation button", font=("Arial", 10)).pack(pady=(8, 4))

    # Option
    opt_frame = tk.Frame(win); opt_frame.pack(pady=(0, 8))
    var_pairs = tk.BooleanVar(); var_wl = tk.BooleanVar(); var_aoi = tk.BooleanVar(); var_dx = tk.BooleanVar()
    tk.Checkbutton(opt_frame, text="Pairs scan",      variable=var_pairs).pack(side="left", padx=10)
    tk.Checkbutton(opt_frame, text="Wavelength scan", variable=var_wl).pack(side="left", padx=10)
    tk.Checkbutton(opt_frame, text="AOI scan",        variable=var_aoi).pack(side="left", padx=10)
    tk.Checkbutton(opt_frame, text="Heatmap",         variable=var_dx).pack(side="left", padx=10)
    
    opt2_frame = tk.Frame(win); opt2_frame.pack(pady=(0, 10))
    var_phase = tk.BooleanVar()
    tk.Checkbutton(opt2_frame, text="Phase (Zeff)", variable=var_phase).pack(side="left", padx=10)


# ---------------------------------------------------------------------------
#  Source > XRR Analysis
# ---------------------------------------------------------------------------

def load_analysis_file():

    import numpy as np
    import threading
    from tkinter import messagebox

    try:
        import optuna
        from optuna.samplers import TPESampler
        from optuna.pruners import MedianPruner
        from optuna.exceptions import TrialPruned
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except Exception as e:
        messagebox.showerror(
            "Need Optuna",
            f"Detail: {e}"
        )
        return

    # Column in Main Window
    IDX_NAME, IDX_N, IDX_K, IDX_THK, IDX_DEN, IDX_ROU = range(6)

    def _parratt(theta_deg, n_arr, k_arr, d_nm, sigma_nm, lam_nm):
        theta = np.asarray(theta_deg, dtype=float)
        cos_t = np.cos(np.radians(theta))
        k0 = 2.0 * np.pi / float(lam_nm)

        m = (np.asarray(n_arr, float) - 1j * np.asarray(k_arr, float)).astype(np.complex128)
        d = np.asarray(d_nm, float)
        s = np.asarray(sigma_nm, float)

        kz = k0 * np.sqrt(m[:, None]**2 - (cos_t[None, :]**2))  # keep existing convention

        r = np.zeros_like(cos_t, dtype=np.complex128)
        for j in range(len(m) - 2, -1, -1):
            rj = (kz[j] - kz[j + 1]) / (kz[j] + kz[j + 1])
            sig = 0.5 * (s[j] + s[j + 1])
            if sig > 0.0:
                rj *= np.exp(-2.0 * kz[j] * kz[j + 1] * (sig ** 2))
            phase = np.exp(2j * kz[j + 1] * d[j + 1])
            r = (rj + r * phase) / (1.0 + rj * r * phase)

        return (np.abs(r) ** 2).astype(float)

    def _peak_preserving_downsample(theta, y, target=600):
        theta = np.asarray(theta, float)
        y = np.asarray(y, float)
        n = theta.size
        if n <= target:
            return np.arange(n, dtype=int)

        k_uniform = max(2, target // 2)
        idx_uniform = np.linspace(0, n - 1, k_uniform, dtype=int)

        ly = np.log(np.clip(y, 1e-18, None))
        d2 = np.abs(np.convolve(ly, [1.0, -2.0, 1.0], mode="same"))
        k_curv = target - k_uniform
        idx_curv = np.argpartition(d2, -k_curv)[-k_curv:]

        idx = np.unique(np.sort(np.concatenate([idx_uniform, idx_curv])))
        if idx[0] != 0:
            idx[0] = 0
        if idx[-1] != n - 1:
            idx[-1] = n - 1
        return idx

    def _model_from_gui():
        SUBSTRATE_THK_NM = 1.0e6
        base_cells = []
        blocks = []
        substrate = None

        def _flt(x, default):
            try:
                return float(str(x).strip())
            except Exception:
                return default

        def _grab(cell):
            name = (cell.entries[IDX_NAME].get() or "").strip()
            n_txt = (cell.entries[IDX_N].get() or "").strip()
            k_txt = (cell.entries[IDX_K].get() or "").strip()
            t0 = _flt(cell.entries[IDX_THK].get(), 1.0)
            rho0 = _flt(cell.entries[IDX_DEN].get(), 2.33)
            s0 = _flt(cell.entries[IDX_ROU].get(), 0.1)

            fix_t = fix_d = fix_s = False
            try:
                st = cell.get_freeze_states()
                fix_t = bool(st.get('thk', False))
                fix_d = bool(st.get('den', False))
                fix_s = bool(st.get('rou', False))
            except Exception:
                pass

            # Si substrate detection 
            if (name.lower() == "si" or "si" == name.lower()) and t0 >= SUBSTRATE_THK_NM and substrate is None:
                if n_txt and k_txt:
                    n_val, k_val = float(n_txt), float(k_txt)
                else:
                    n_val, k_val = 1.0 - 2.7e-6 * rho0, 0.0
                return None, {"n": n_val, "k": k_val, "s": max(s0, 0.0)}

            if n_txt and k_txt:
                n_val, k_val, has = float(n_txt), float(k_txt), True
            else:
                n_val, k_val, has = 1.0 - 2.7e-6 * rho0, 0.0, False

            return ({"cell": cell, "n": n_val, "k": k_val,
                     "t": max(t0, 1e-6), "s": max(s0, 0.0),
                     "rho": rho0, "has_nk": has,
                     "fix_t": fix_t, "fix_d": fix_d, "fix_s": fix_s}, None)

        for obj in subroutines:
            if isinstance(obj, Subroutine):
                start = len(base_cells)
                for c in obj.cells:
                    item, sub = _grab(c)
                    if sub is not None:
                        substrate = sub
                    elif item is not None:
                        base_cells.append(item)
                end = len(base_cells)
                if end > start:
                    rep = max(1, int(obj.loop_count))
                    blocks.append(("repeat" if rep > 1 else "single", start, end, rep))
            elif isinstance(obj, Cell):
                start = len(base_cells)
                item, sub = _grab(obj)
                if sub is not None:
                    substrate = sub
                elif item is not None:
                    base_cells.append(item)
                    end = len(base_cells)
                    blocks.append(("single", start, end, 1))

        if not base_cells and substrate is None:
            return None

        base_n = np.array([x["n"] for x in base_cells], float)
        base_k = np.array([x["k"] for x in base_cells], float)
        base_t = np.array([x["t"] for x in base_cells], float)
        base_s = np.array([x["s"] for x in base_cells], float)
        has_nk = [x["has_nk"] for x in base_cells]

        if substrate is None:
            rho_last = base_cells[-1]["rho"] if base_cells else 2.33
            substrate = {"n": 1.0 - 2.7e-6 * rho_last, "k": 0.0, "s": 0.0}

        return base_cells, base_n, base_k, base_t, base_s, has_nk, blocks, substrate

    def _expand_full(base_n, base_k, base_t, base_s, blocks, substrate):
        nL, kL, tL, sL = [1.0], [0.0], [0.0], [0.0]
        for kind, i0, i1, rep in blocks:
            for _ in range(rep):
                nL += list(base_n[i0:i1]); kL += list(base_k[i0:i1])
                tL += list(base_t[i0:i1]); sL += list(base_s[i0:i1])
        nL.append(substrate["n"]); kL.append(substrate["k"])
        tL.append(0.0);            sL.append(substrate["s"])
        return np.array(nL, float), np.array(kL, float), np.array(tL, float), np.array(sL, float)

    def _normalize_periodicity(t_base, blocks, d_targets, fixed_mask=None):
        if not d_targets:
            return t_base
        out = t_base.copy()
        bidx = 0
        for kind, i0, i1, rep in blocks:
            if kind == "repeat":
                d0 = d_targets[bidx]
                seg = out[i0:i1]
                if fixed_mask is None:
                    dcur = float(np.sum(seg))
                    if dcur > 0:
                        out[i0:i1] *= (d0 / dcur)
                else:
                    fseg = fixed_mask[i0:i1]
                    d_fixed = float(np.sum(seg[fseg]))
                    d_var   = float(np.sum(seg[~fseg]))
                    if d_var > 0 and d0 > d_fixed:
                        scale = (d0 - d_fixed) / d_var
                        out[i0:i1][~fseg] *= scale
                bidx += 1
        return out

    # xrdml loader
    def _load_xrdml(fp):
        import re, numpy as np
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        m_counts = re.search(r"<counts[^>]*>(.*?)</counts>", txt, re.I | re.S)
        m_intens = None if m_counts else re.search(r"<intensities[^>]*>(.*?)</intensities>", txt, re.I | re.S)
        series = m_counts or m_intens
        if not series:
            return None
        y_raw = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", series.group(1)), sep=" ")
        npts = y_raw.size

        m_cct = re.search(r"<commonCountingTime[^>]*>(.*?)</commonCountingTime>", txt, re.I | re.S)
        m_ct  = re.search(r"<countingTime[^>]*>(.*?)</countingTime>", txt, re.I | re.S)
        if m_cct:
            y = y_raw / float(m_cct.group(1))
        elif m_ct:
            cts = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", m_ct.group(1)), sep=" ")
            y = y_raw / cts if cts.size == npts else y_raw
        else:
            y = y_raw
        y = np.clip(y, 1e-12, None)

        m_baf = re.search(r"<beamAttenuationFactors[^>]*>(.*?)</beamAttenuationFactors>", txt, re.I | re.S)
        if m_baf:
            fac = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", m_baf.group(1)), sep=" ")
            if   fac.size == npts: y = y * fac
            elif fac.size == 1:    y = y * fac[0]

        def _get_positions(axis_name):
            m = re.search(rf'<positions[^>]*axis\s*=\s*["\']{re.escape(axis_name)}["\'][^>]*>(.*?)</positions>', txt, re.I | re.S)
            if not m:
                return None
            blk = m.group(1)
            m_list = re.search(r"<listPositions[^>]*>(.*?)</listPositions>", blk, re.I | re.S)
            if m_list:
                arr = np.fromstring(re.sub(r"[^\d\.\+\-Ee]", " ", m_list.group(1)), sep=" ")
                if arr.size == npts:
                    return arr
                if arr.size > 1:
                    xs = np.linspace(0, arr.size - 1, npts)
                    return np.interp(xs, np.arange(arr.size), arr)
            m_rng = re.search(r"<startPosition[^>]*>(.*?)</startPosition>.*?<endPosition[^>]*>(.*?)</endPosition>", blk, re.I | re.S)
            if m_rng:
                s, e = map(float, m_rng.groups())
                return np.linspace(s, e, npts)
            return None

        def _axis_or_none(*names):
            for nm in names:
                arr = _get_positions(nm)
                if arr is not None:
                    return np.asarray(arr, dtype=float)
            return None

        omega = _axis_or_none("Omega", "Theta")
        two_theta = _axis_or_none(
            "Omega/2Theta", "Omega-2Theta", "Omega2Theta",
            "Theta/2Theta", "Theta-2Theta", "2Theta", "TwoTheta"
        )

        if omega is None and two_theta is None:
            omega = np.arange(npts, dtype=float) * 0.5
            two_theta = 2.0 * omega
        elif omega is None:
            omega = 0.5 * two_theta
        elif two_theta is None:
            two_theta = 2.0 * omega

        return {"omega": np.asarray(omega, dtype=float),
                "two_theta": np.asarray(two_theta, dtype=float),
                "y": y}

    # XRR Analysis Window
    win = tk.Toplevel(root)
    win.iconbitmap(icon_path)
    win.title("XRR Analysis Window")
    win.geometry("760x720")
    place_near_root(win)

    ctrl = tk.LabelFrame(win, text="Control", padx=6, pady=6)
    ctrl.pack(fill="x", padx=8, pady=4)

    tk.Label(ctrl, text="XRR Data file").grid(row=0, column=0, sticky="w")
    path_var = tk.StringVar()
    tk.Entry(ctrl, textvariable=path_var, width=52).grid(row=0, column=1, padx=3, columnspan=3, sticky="w")

    row1 = tk.Frame(ctrl); row1.grid(row=1, column=0, columnspan=4, sticky="w")
    tk.Label(row1, text="Trials").grid(row=0, column=0, sticky="e")
    trials_var = tk.IntVar(value=300)
    tk.Entry(row1, textvariable=trials_var, width=8).grid(row=0, column=1, sticky="w", padx=3)
    tk.Label(row1, text="Wavelength (nm)").grid(row=0, column=2, sticky="e", padx=(12,0))
    wavelength_var = tk.DoubleVar(value=0.15418)
    tk.Entry(row1, textvariable=wavelength_var, width=8).grid(row=0, column=3, sticky="w", padx=3)
    tk.Label(row1, text="chi^2").grid(row=0, column=4, sticky="e", padx=(12,0))
    chisq_var = tk.StringVar(value="-")
    tk.Label(row1, textvariable=chisq_var, width=12, relief="sunken").grid(row=0, column=5, sticky="w", padx=3)

    ranges_row = tk.Frame(ctrl); ranges_row.grid(row=3, column=0, columnspan=9, sticky="w")
    tk.Label(ranges_row, text="Fitting range start/end (deg)").grid(row=0, column=0, sticky="e")
    omega_pair = tk.Frame(ranges_row); omega_pair.grid(row=0, column=1, sticky="w", padx=(4,0))
    o_start_var = tk.DoubleVar(value=0.0); tk.Entry(omega_pair, textvariable=o_start_var, width=8).pack(side="left")
    o_end_var   = tk.DoubleVar(value=2.0); tk.Entry(omega_pair, textvariable=o_end_var,   width=8).pack(side="left", padx=(3,0))

    tk.Label(ranges_row, text="X-scale (min/max)").grid(row=0, column=2, sticky="e", padx=(6,0))
    x_pair = tk.Frame(ranges_row); x_pair.grid(row=0, column=3, sticky="w")
    x_min_var = tk.StringVar(); tk.Entry(x_pair, textvariable=x_min_var, width=8).pack(side="left")
    x_max_var = tk.StringVar(); tk.Entry(x_pair, textvariable=x_max_var, width=8).pack(side="left", padx=(3,0))

    tk.Label(ranges_row, text="Y-scale (min/max)").grid(row=0, column=4, sticky="e", padx=(6,0))
    y_pair = tk.Frame(ranges_row); y_pair.grid(row=0, column=5, sticky="w")
    y_min_var = tk.StringVar(); tk.Entry(y_pair, textvariable=y_min_var, width=8).pack(side="left")
    y_max_var = tk.StringVar(); tk.Entry(y_pair, textvariable=y_max_var, width=8).pack(side="left", padx=(3,0))

    fig = Figure(figsize=(6.5, 5.0), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlabel("Omega/2Theta")  # ★ 固定
    ax.set_ylabel("Intensity (cps)")
    ax.set_yscale("log")
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0,4))
    NavigationToolbar2Tk(canvas, win)

    current = {"omega": None, "two_theta": None, "y": None}
    plot_state = {"manual_xlim": False, "manual_ylim": False}

    def _apply_axis_limits():
        def _f(s):
            s = s.strip()
            return float(s) if s else None
        xmin=_f(x_min_var.get()); xmax=_f(x_max_var.get())
        ymin=_f(y_min_var.get()); ymax=_f(y_max_var.get())
        if xmin is not None and xmax is not None:
            if xmin>=xmax:
                messagebox.showerror("X range","Xmin < Xmax"); return
            ax.set_xlim(xmin, xmax); plot_state["manual_xlim"]=True
        if ymin is not None and ymax is not None:
            if ymin<=0:
                messagebox.showwarning("Y range","log scale requires Ymin>0; set to 1e-12.")
                ymin=1e-12; y_min_var.set("{:g}".format(ymin))
            if ymin>=ymax:
                messagebox.showerror("Y range","Ymin < Ymax"); return
            ax.set_ylim(ymin, ymax); plot_state["manual_ylim"]=True
        canvas.draw_idle()

    apply_btn = tk.Button(ctrl, text="XY Re-Scale", width=10, command=_apply_axis_limits)

    def _choose_theta_from_loaded(d):
        om = d["omega"]; tt = d["two_theta"]
        th_from_tt = 0.5 * tt
        try:
            if np.allclose(tt, 2.0*om, rtol=2e-3, atol=2e-3):
                return om
        except Exception:
            pass
        if np.all(np.isfinite(om)) and om.ptp() > 0:
            return om
        return th_from_tt

    def choose_file():
        xrr_dir = os.path.join(current_dir, "xrr"); os.makedirs(xrr_dir, exist_ok=True)
        fname = filedialog.askopenfilename(initialdir=xrr_dir, filetypes=[("XRDML files", "*.xrdml *.xrfml")])
        if not fname:
            return False
        path_var.set(fname)
        d = _load_xrdml(fname)
        if d is None:
            return False
        current.update(d)
        theta = _choose_theta_from_loaded(current)
        o_start_var.set(float(theta[0])); o_end_var.set(float(theta[-1]))
        ax.clear()
        ax.plot(theta, current["y"], "-", lw=1.2, label=os.path.basename(fname))
        ax.set_xlabel("Omega/2Theta")  # ★ 固定
        ax.set_ylabel("Intensity (cps)")
        ax.set_yscale("log"); ax.grid(True, which="both", alpha=0.25); ax.legend()
        plot_state["manual_xlim"]=False; plot_state["manual_ylim"]=False
        ax.relim(); ax.autoscale_view(); canvas.draw_idle()
        return True

    tk.Button(ctrl, text="Open", command=choose_file, width=7).grid(row=0, column=4, padx=1, rowspan=2, sticky="ns")

    stop_event = threading.Event()

    def _refresh_axes():
        ax.relim()
        if not plot_state["manual_xlim"]:
            y_lim=ax.get_ylim(); ax.autoscale(enable=True, axis="x"); ax.set_ylim(y_lim)
        if not plot_state["manual_ylim"]:
            x_lim=ax.get_xlim(); ax.autoscale(enable=True, axis="y"); ax.set_xlim(x_lim)
        canvas.draw_idle()

    def set_running(running):
        run_btn.config(state=("disabled" if running else "normal"))
        stop_btn.config(state=("normal" if running else "disabled"))
        apply_btn.config(state=("disabled" if running else "normal"))

    def on_stop():
        stop_event.set()
        if console and console.winfo_exists():
            ts = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            console.insert(tk.END, "{} Stop requested for XRR fit.\n".format(ts)); console.see(tk.END)

    # Run (Shake-LFPSO) + Optuna
    def start_fit():
        if current["omega"] is None and not choose_file():
            return

        model = _model_from_gui()
        if model is None:
            messagebox.showerror("Model error", "No layers defined.")
            return
        base_cells, base_n, base_k, base_t0, base_s0, has_nk, blocks, substrate = model

        fix_t = np.array([bool(it.get("fix_t", False)) for it in base_cells], dtype=bool)
        fix_d = np.array([bool(it.get("fix_d", False)) for it in base_cells], dtype=bool)
        fix_s = np.array([bool(it.get("fix_s", False)) for it in base_cells], dtype=bool)

        try:
            o_s=float(o_start_var.get()); o_e=float(o_end_var.get())
            if o_s>=o_e:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input error","Check Omega start/end.")
            return

        theta_all = _choose_theta_from_loaded(current)
        mask = (theta_all >= o_s) & (theta_all <= o_e)
        if not np.any(mask):
            messagebox.showerror("Range error","No data in the specified range.")
            return

        theta = theta_all[mask]
        x_for_plot = theta
        y_exp = current["y"][mask]
        lam_nm = float(wavelength_var.get())
        pso_iter_user = max(1, int(trials_var.get()))

        for ln in ax.lines[1:]:
            ln.remove()
        fit_line, = ax.plot([], [], c="crimson", lw=1.4, label="Fitted")
        ax.set_xlabel("Omega/2Theta")  
        ax.legend()

        stop_event.clear()
        set_running(True)

        d_targets = [float(np.sum(base_t0[i0:i1])) for kind, i0, i1, rep in blocks if kind == "repeat"]

        rng = np.random.default_rng()
        NL = len(base_cells)
        pop = min(200, max(80, 20 + 4*NL))

        lo_t = np.maximum(0.3*base_t0, 1e-5); hi_t = np.maximum(3.0*base_t0, 3e-5)
        lo_s = np.full_like(base_s0, 0.01);     hi_s = np.maximum(3.0*base_s0, 0.5)
        base_rho = np.array([c["rho"] for c in base_cells], float)
        lo_d = 0.5*base_rho; hi_d = 2.0*base_rho

        lo_t[fix_t] = base_t0[fix_t]; hi_t[fix_t] = base_t0[fix_t]
        lo_s[fix_s] = base_s0[fix_s]; hi_s[fix_s] = base_s0[fix_s]
        lo_d[fix_d] = base_rho[fix_d]; hi_d[fix_d] = base_rho[fix_d]

        Xt = rng.uniform(lo_t, hi_t, size=(pop, NL))
        Xs = rng.uniform(lo_s, hi_s, size=(pop, NL))
        Xd = rng.uniform(lo_d, hi_d, size=(pop, NL))
        Xt[0,:] = base_t0; Xs[0,:] = base_s0; Xd[0,:] = base_rho

        Vmax_t = 0.3*(hi_t - lo_t); Vmax_s = 0.3*(hi_s - lo_s); Vmax_d = 0.3*(hi_d - lo_d)
        Vt = rng.uniform(-Vmax_t, Vmax_t, size=(pop, NL))
        Vs = rng.uniform(-Vmax_s, Vmax_s, size=(pop, NL))
        Vd = rng.uniform(-Vmax_d, Vmax_d, size=(pop, NL))
        w_inert, c1, c2 = 0.72, 1.49, 1.49

        Pbest_t, Pbest_s, Pbest_d = Xt.copy(), Xs.copy(), Xd.copy()
        Pbest_E = np.full(pop, np.inf)

        def _movavg(y, win):
            win = max(5, int(win))
            k = np.ones(win) / float(win)
            return np.convolve(y, k, mode="same")
        y_ma = _movavg(y_exp, max(7, len(y_exp)//50))
        likely_periodic = any((k == "repeat" and rep >= 3) for k,_,_,rep in blocks)
        if likely_periodic:
            w_peak = np.where(y_exp >= 3.0*y_ma, np.maximum(y_exp/y_ma, 1.0), 1.0)
        else:
            w_peak = np.ones_like(y_exp)

        def _eval_params(t_base, rho_base, s_base):
            if d_targets:
                t_base = _normalize_periodicity(t_base, blocks, d_targets, fixed_mask=fix_t)
            n_base = base_n.copy(); k_base = base_k.copy()
            for i, flag in enumerate(has_nk):
                if not flag:
                    n_base[i] = 1.0 - 2.7e-6 * rho_base[i]
                    k_base[i] = 0.0
            n_arr, k_arr, d_arr, s_arr = _expand_full(n_base, k_base, t_base, s_base, blocks, substrate)
            y_sim = _parratt(theta, n_arr, k_arr, d_arr, s_arr, lam_nm)
            y_sim = np.maximum(y_sim, 1e-18)
            y_exp_c = np.maximum(y_exp, 1e-18)
            scale = np.exp(np.mean(np.log(y_exp_c) - np.log(y_sim)))
            y_calc = y_sim * scale
            r = np.log10(y_exp_c) - np.log10(y_calc)
            E = float(np.mean((r*r) * w_peak))
            return E, y_calc

        idx_ds = _peak_preserving_downsample(theta, y_exp, target=600)
        theta_ds = theta[idx_ds]
        y_exp_ds = y_exp[idx_ds]
        if likely_periodic:
            y_ma_ds = _movavg(y_exp_ds, max(7, len(y_exp_ds)//50))
            w_peak_ds = np.where(y_exp_ds >= 3.0*y_ma_ds, np.maximum(y_exp_ds/y_ma_ds, 1.0), 1.0)
        else:
            w_peak_ds = np.ones_like(y_exp_ds)

        def _eval_params_fast(t_base, rho_base, s_base):
            if d_targets:
                t_base = _normalize_periodicity(t_base, blocks, d_targets, fixed_mask=fix_t)
            n_base = base_n.copy(); k_base = base_k.copy()
            for i, flag in enumerate(has_nk):
                if not flag:
                    n_base[i] = 1.0 - 2.7e-6 * rho_base[i]
                    k_base[i] = 0.0
            n_arr, k_arr, d_arr, s_arr = _expand_full(n_base, k_base, t_base, s_base, blocks, substrate)
            y_sim = _parratt(theta_ds, n_arr, k_arr, d_arr, s_arr, lam_nm)
            y_sim = np.maximum(y_sim, 1e-18)
            y_exp_c = np.maximum(y_exp_ds, 1e-18)
            scale = np.exp(np.mean(np.log(y_exp_c) - np.log(y_sim)))
            y_calc = y_sim * scale
            r = np.log10(y_exp_c) - np.log10(y_calc)
            E = float(np.mean((r*r) * w_peak_ds))
            return E

        # Optuna
        n_warm = int(min(60, max(16, 3*NL)))

        from optuna.trial import TrialState
        from optuna.exceptions import TrialPruned
        from optuna.pruners import MedianPruner
        from optuna.samplers import TPESampler
        import hashlib

        sampler = TPESampler(seed=0, multivariate=True, group=True)
        pruner  = MedianPruner(n_startup_trials=max(5, n_warm//4))

        save_dir = os.path.join(current_dir, "save")
        os.makedirs(save_dir, exist_ok=True)
        geo_sig = {
            "NL": NL,
            "lam": float(lam_nm),
            "theta_start": float(theta_ds[0]),
            "theta_end": float(theta_ds[-1]),
            "blocks": [(k, int(i0), int(i1), int(rep)) for (k, i0, i1, rep) in blocks],
            "has_nk": list(map(bool, has_nk)),
            "n": np.round(base_n, 8).tolist(),
            "k": np.round(base_k, 8).tolist(),
            "t0": np.round(base_t0, 9).tolist(),
            "s0": np.round(base_s0, 9).tolist(),
        }
        h = hashlib.sha1(repr(geo_sig).encode("utf-8")).hexdigest()[:16]
        storage = f"sqlite:///{os.path.join(save_dir, 'optuna_xrr.db')}"
        study_name = f"xrr_{h}"
        study = optuna.create_study(
            direction="minimize",
            sampler=sampler,
            pruner=pruner,
            storage=storage,
            study_name=study_name,
            load_if_exists=True,
        )

        try:
            n_exist = sum(t.state == TrialState.COMPLETE for t in study.trials)
            if n_exist >= 10:
                n_warm = max(10, n_warm // 2)
        except Exception:
            pass

        def _objective(trial: optuna.Trial):
            if stop_event.is_set():
                raise TrialPruned()

            t_s = np.array([
                float(base_t0[i]) if fix_t[i]
                else trial.suggest_float(f"t_{i}", float(lo_t[i]), float(hi_t[i]))
                for i in range(NL)
            ], float)
            s_s = np.array([
                float(base_s0[i]) if fix_s[i]
                else trial.suggest_float(f"s_{i}", float(lo_s[i]), float(hi_s[i]))
                for i in range(NL)
            ], float)
            d_s = np.array([
                float(base_rho[i]) if (fix_d[i] or has_nk[i])
                else trial.suggest_float(f"d_{i}", float(lo_d[i]), float(hi_d[i]))
                for i in range(NL)
            ], float)
            if d_targets:
                t_s = _normalize_periodicity(t_s, blocks, d_targets, fixed_mask=fix_t)
            E = _eval_params_fast(t_s, d_s, s_s)

            trial.set_user_attr("t", t_s.tolist())
            trial.set_user_attr("s", s_s.tolist())
            trial.set_user_attr("d", d_s.tolist())
            return E

        study.optimize(_objective, n_trials=n_warm, gc_after_trial=True)

        # Re-test
        t_best = np.array(study.best_trial.user_attrs["t"], float)
        s_best = np.array(study.best_trial.user_attrs["s"], float)
        d_best = np.array(study.best_trial.user_attrs["d"], float)
        E0, curve0 = _eval_params(t_best, d_best, s_best)

        # Update
        fit_line.set_data(x_for_plot, curve0)
        chisq_var.set("{:.4g}".format(E0))
        _refresh_axes()

        for i, it in enumerate(base_cells):
            cell = it["cell"]
            if not fix_t[i]:
                cell.entries[IDX_THK].delete(0, tk.END); cell.entries[IDX_THK].insert(0, "{:.6g}".format(t_best[i]))
            if not it["has_nk"] and not fix_d[i]:
                cell.entries[IDX_DEN].delete(0, tk.END); cell.entries[IDX_DEN].insert(0, "{:.6g}".format(d_best[i]))
            if not fix_s[i]:
                cell.entries[IDX_ROU].delete(0, tk.END); cell.entries[IDX_ROU].insert(0, "{:.6g}".format(s_best[i]))
        mark_as_modified()

        shrink = 0.6
        if E0 < 0.02:
            shrink = 0.45
        elif E0 < 0.05:
            shrink = 0.55
        iter_max = max(8, int(pso_iter_user * shrink))

        Gbest_E = np.inf
        Gbest_t = t_best.copy(); Gbest_s = s_best.copy(); Gbest_d = d_best.copy()
        Gbest_curve = curve0.copy()

        Xt[0,:] = t_best
        Xs[0,:] = s_best
        Xd[0,:] = d_best

        def _pso_evaluate_population_two_stage():
            nonlocal Gbest_E, Gbest_t, Gbest_s, Gbest_d, Gbest_curve
            E_fast = np.empty(pop, dtype=float)
            for i in range(pop):
                E_fast[i] = _eval_params_fast(Xt[i], Xd[i], Xs[i])

            k = max(5, pop // 8)
            top_idx = np.argpartition(E_fast, k)[:k]
            improved = False
            for i in top_idx:
                Ei, ycalc = _eval_params(Xt[i], Xd[i], Xs[i])
                if Ei < Pbest_E[i]:
                    Pbest_E[i] = Ei
                    Pbest_t[i] = Xt[i].copy()
                    Pbest_s[i] = Xs[i].copy()
                    Pbest_d[i] = Xd[i].copy()
                if Ei < Gbest_E:
                    Gbest_E = Ei
                    Gbest_t = Xt[i].copy(); Gbest_s = Xs[i].copy(); Gbest_d = Xd[i].copy()
                    Gbest_curve = ycalc
                    improved = True

            non_top = np.setdiff1d(np.arange(pop), top_idx, assume_unique=True)
            for i in non_top:
                if E_fast[i] < Pbest_E[i]:
                    Pbest_E[i] = E_fast[i]
                    Pbest_t[i] = Xt[i].copy()
                    Pbest_s[i] = Xs[i].copy()
                    Pbest_d[i] = Xd[i].copy()

            return improved

        _pso_evaluate_population_two_stage()
        fit_line.set_data(x_for_plot, Gbest_curve)
        chisq_var.set("{:.4g}".format(Gbest_E)); _refresh_axes()

        fit_line.set_data(x_for_plot, Gbest_curve)
        chisq_var.set("{:.4g}".format(Gbest_E)); _refresh_axes()

        Jamcount = 0
        best_last = Gbest_E
        shake_done = 0

        def _write_gui_from_best(bt, bd, bs):
            for i, it in enumerate(base_cells):
                cell = it["cell"]
                if not fix_t[i]:
                    cell.entries[IDX_THK].delete(0, tk.END); cell.entries[IDX_THK].insert(0, "{:.6g}".format(bt[i]))
                if not it["has_nk"] and not fix_d[i]:
                    cell.entries[IDX_DEN].delete(0, tk.END); cell.entries[IDX_DEN].insert(0, "{:.6g}".format(bd[i]))
                if not fix_s[i]:
                    cell.entries[IDX_ROU].delete(0, tk.END); cell.entries[IDX_ROU].insert(0, "{:.6g}".format(bs[i]))
            mark_as_modified()

        def worker():
            nonlocal Gbest_E, Gbest_t, Gbest_s, Gbest_d, Gbest_curve, Jamcount, best_last, shake_done
            try:
                for it in range(iter_max):
                    if stop_event.is_set():
                        break

                    r1 = rng.random((pop, NL)); r2 = rng.random((pop, NL))
                    # update velocities
                    Vt[:] = 0.72*Vt + 1.49*r1*(Pbest_t - Xt) + 1.49*r2*(Gbest_t - Xt)
                    Vs[:] = 0.72*Vs + 1.49*r1*(Pbest_s - Xs) + 1.49*r2*(Gbest_s - Xs)
                    Vd[:] = 0.72*Vd + 1.49*r1*(Pbest_d - Xd) + 1.49*r2*(Gbest_d - Xd)
                    # cap velocities
                    Vt[:] = np.clip(Vt, -Vmax_t, Vmax_t)
                    Vs[:] = np.clip(Vs, -Vmax_s, Vmax_s)
                    Vd[:] = np.clip(Vd, -Vmax_d, Vmax_d)
                    # update positions
                    Xt[:] += Vt; Xs[:] += Vs; Xd[:] += Vd
                    Xt[:] = np.clip(Xt, lo_t, hi_t)
                    Xs[:] = np.clip(Xs, lo_s, hi_s)
                    Xd[:] = np.clip(Xd, lo_d, hi_d)
                    # normalize D
                    if d_targets:
                        for i in range(pop):
                            Xt[i] = _normalize_periodicity(Xt[i], blocks, d_targets, fixed_mask=fix_t)

                    improved = _pso_evaluate_population_two_stage()

                    if improved or (it % 5 == 0) or (it == iter_max - 1):
                        def _upd():
                            fit_line.set_data(x_for_plot, Gbest_curve)
                            chisq_var.set("{:.4g}".format(Gbest_E))
                            _refresh_axes()
                        root.after(0, _upd)
                        _write_gui_from_best(Gbest_t, Gbest_d, Gbest_s)

                    if Gbest_E < best_last - 1e-6:
                        best_last = Gbest_E; Jamcount = 0
                    else:
                        Jamcount += 1
                        JAM_TH = max(15, iter_max//6)
                        if Jamcount >= JAM_TH and shake_done < 3:
                            factor = 1.5
                            Vmax_t[:] *= factor; Vmax_s[:] *= factor; Vmax_d[:] *= factor
                            amp_t = 0.3*(hi_t - lo_t); amp_s = 0.3*(hi_s - lo_s); amp_d = 0.3*(hi_d - lo_d)
                            Xt[:] = Gbest_t + rng.uniform(-amp_t, amp_t, size=(pop, NL))
                            Xs[:] = Gbest_s + rng.uniform(-amp_s, amp_s, size=(pop, NL))
                            Xd[:] = Gbest_d + rng.uniform(-amp_d, amp_d, size=(pop, NL))
                            Xt[:] = np.clip(Xt, lo_t, hi_t); Xs[:] = np.clip(Xs, lo_s, hi_s); Xd[:] = np.clip(Xd, lo_d, hi_d)
                            if d_targets:
                                for i in range(pop):
                                    Xt[i] = _normalize_periodicity(Xt[i], blocks, d_targets, fixed_mask=fix_t)
                            Vt[:] = rng.uniform(-Vmax_t, Vmax_t, size=(pop, NL))
                            Vs[:] = rng.uniform(-Vmax_s, Vmax_s, size=(pop, NL))
                            Vd[:] = rng.uniform(-Vmax_d, Vmax_d, size=(pop, NL))
                            Jamcount = 0; shake_done += 1
                        elif Jamcount >= 2 * JAM_TH and shake_done >= 3:
                            break

                def _final():
                    fit_line.set_data(x_for_plot, Gbest_curve)
                    chisq_var.set("{:.4g}".format(Gbest_E))
                    _refresh_axes()
                root.after(0, _final)

            except Exception as e:
                root.after(0, lambda: messagebox.showerror("Fit error", str(e)))
            finally:
                root.after(0, lambda: set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    run_btn  = tk.Button(ctrl, text="Run",  width=10, bg="#5cb85c", fg="white", command=start_fit)
    stop_btn = tk.Button(ctrl, text="Stop", width=10, bg="#d9534f", fg="white", command=on_stop, state="disabled")
    run_btn.grid(row=0, column=5, rowspan=3, sticky="ns", padx=(10,2), pady=2)
    stop_btn.grid(row=0, column=6, rowspan=3, sticky="ns", padx=(2,2), pady=2)
    apply_btn.grid(row=0, column=7, rowspan=3, sticky="ns", padx=(2,2), pady=2)


# ---------------------------------------------------------------------------
#  Source > Deposition
# ---------------------------------------------------------------------------

def load_depo_file():

    new_window = tk.Toplevel(root)
    new_window.iconbitmap(icon_path)
    new_window.title("Deposition Window")
    new_window.geometry("500x320")
    place_near_root(new_window)
    new_window.update_idletasks()
    place_near_root(new_window)

    # Menu
    menubar = tk.Menu(new_window); new_window.config(menu=menubar)
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Exit", command=new_window.destroy)

    # Parameters
    prm = tk.LabelFrame(new_window, text="Parameters", padx=6, pady=6)
    prm.pack(fill="x", padx=8, pady=(8, 4))

    Nx_var, L_var      = tk.IntVar(value=128), tk.DoubleVar(value=128.0)
    Tstep_var, dt_var  = tk.IntVar(value=1000), tk.DoubleVar(value=0.1)

    R_single_var = tk.DoubleVar(value=0.05)  
    v_start_var  = tk.DoubleVar(value=0.01)
    v_end_var    = tk.DoubleVar(value=0.10)
    v_num_var    = tk.IntVar(value=5)

    nu_var, lam_var   = tk.DoubleVar(value=1.0), tk.DoubleVar(value=1.0)
    noise_amp_var     = tk.DoubleVar(value=0.5)
    noise_coeff_var   = tk.BooleanVar(value=True)
    seed_var          = tk.IntVar(value=0)

    p_var        = tk.DoubleVar(value=1.0)     
    dz_nm_var    = tk.DoubleVar(value=1.0)     
    
    particles_var = tk.IntVar(value=0)         

    _lbl = lambda r,c,t: tk.Label(prm,text=t).grid(row=r,column=c,sticky="e")
    _ent = lambda r,c,v,w=8: tk.Entry(prm,textvariable=v,width=w).grid(row=r,column=c,padx=3)

    # Row 0
    _lbl(0,0,"Nx = Ny"); _ent(0,1,Nx_var)
    _lbl(0,2,"L");       _ent(0,3,L_var)
    _lbl(0,4,"Tstep");   _ent(0,5,Tstep_var)
    _lbl(0,6,"dt");      _ent(0,7,dt_var)
    # Row 1
    _lbl(1,0,"R (single)"); _ent(1,1,R_single_var)
    _lbl(1,2,"nu");         _ent(1,3,nu_var)
    _lbl(1,4,"lam");        _ent(1,5,lam_var)
    _lbl(1,6,"noise_amp");  _ent(1,7,noise_amp_var)
    # Row 2
    _lbl(2,0,"v_start"); _ent(2,1,v_start_var)
    _lbl(2,2,"v_end");   _ent(2,3,v_end_var)
    _lbl(2,4,"v_num");   _ent(2,5,v_num_var)
    _lbl(2,6,"seed");    _ent(2,7,seed_var)
    # Row 3
    tk.Checkbutton(prm, text="noise_coeff_R", variable=noise_coeff_var)\
        .grid(row=3, column=0, columnspan=3, sticky="w")
    _lbl(3,4,"p (RSOS)"); _ent(3,5,p_var)
    _lbl(3,6,"dz (nm/event)"); _ent(3,7,dz_nm_var)
    # Row 4  
    _lbl(4,0,"Particles (# accepted)"); _ent(4,1,particles_var, w=12)

    for c in range(8):
        prm.grid_columnconfigure(c, weight=1 if c%2 else 0)

    # Buttons
    btn_frm = tk.Frame(new_window); btn_frm.pack(pady=10)
    tk.Button(btn_frm, text="RSOS-KPZ",      width=15, command=lambda: run_kpz()).grid(row=0,column=0,padx=4)
    tk.Button(btn_frm, text="RSOS",          width=15, command=lambda: run_rsos()).grid(row=0,column=1,padx=4)
    tk.Button(btn_frm, text="Crystallinity", width=15, command=lambda: show_crystallinity()).grid(row=0,column=2,padx=4)
    tk.Button(btn_frm, text="Load CSV",      width=15, command=lambda: load_external_csv()).grid(row=1,column=0,padx=4,pady=2)
    tk.Button(btn_frm, text="Optimization",  width=15, command=lambda: optimize_roughness()).grid(row=1,column=1,padx=4,pady=2)

    loaded_df    = None
    last_h_final = None  

    def _log(text):
        ts = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        if console is None or not console.winfo_exists():
            create_log_window()
        console.insert(tk.END, f"{ts} {text}\n"); console.see(tk.END)
        log_message_to_file(f"{ts} {text}\n")

    def _save_csv(x, h_mean_nm, rough_nm, tag, x_name="time"):
        out = Path(current_dir) / "save"; out.mkdir(exist_ok=True)
        path = out / f"{tag}.csv"
        pd.DataFrame({x_name:x, "mean_height":h_mean_nm, "roughness":rough_nm}).to_csv(path, index=False)
        _log(f"saved → {path}")

    def _save_height_csv(h_nm, tag):
        out = Path(current_dir) / "save"; out.mkdir(exist_ok=True)
        n  = h_nm.shape[0]
        X, Y = np.meshgrid(np.arange(n), np.arange(n))
        path = out / f"{tag}.csv"
        pd.DataFrame({"x":X.ravel(),"y":Y.ravel(),"z":h_nm.ravel()}).to_csv(path, index=False)
        _log(f"height map saved → {path}")

    def simulate_kpz_1d(Nx,L,T,dt,R,nu,lam,noise_amp,use_coeff,seed):
        np.random.seed(seed); dx=L/Nx; h=0.01*np.random.randn(Nx)
        t_rec,h_av,w_rec=[],[],[]
        for step in range(T):
            hm=h.mean(); w=np.sqrt(((h-hm)**2).mean())
            t_rec.append(step*dt); h_av.append(hm); w_rec.append(w)
            h_r,h_l=np.roll(h,-1),np.roll(h,1)
            d2h=(h_r-2*h+h_l)/dx**2; grad2=((h_r-h_l)/(2*dx))**2
            coeff=noise_amp*(np.sqrt(R) if use_coeff else 1.0)
            noise=coeff*np.random.randn(Nx)/np.sqrt(dx*dt)
            h += dt*(R+nu*d2h+0.5*lam*grad2+noise)
        return np.asarray(t_rec),np.asarray(h_av),np.asarray(w_rec)

    def _save_height_csv(h_nm, tag):
        out = Path(current_dir) / "save"
        out.mkdir(exist_ok=True)
        n = h_nm.shape[0]
        X, Y = np.meshgrid(np.arange(n), np.arange(n))
        hm = float(h_nm.mean())
        path = out / f"{tag}.csv"
        pd.DataFrame({
            "x": X.ravel(),
            "y": Y.ravel(),
            "z": h_nm.ravel(),
            "delta_h": (h_nm - hm).ravel()  
        }).to_csv(path, index=False)
        _log(f"height map saved → {path}")

    # RSOS 2D
    def simulate_rsos_2d(N, sweeps, p, seed):
        rng = np.random.default_rng(seed)
        h = np.zeros((N, N), dtype=int)
        t, h_av, w, acc_cum = [], [], [], []
        acc = 0
        for s in range(sweeps):
            for _ in range(N * N):
                i, j = rng.integers(0, N, 2)
                if rng.random() < p:
                    h_try = h[i, j] + 1
                    for di, dj in ((1,0),(-1,0),(0,1),(0,-1)):
                        if abs(h_try - h[(i+di) % N, (j+dj) % N]) > 1:
                            break
                    else:
                        h[i, j] = h_try
                        acc += 1
            hm = h.mean()
            t.append(s)
            h_av.append(hm)
            w.append(np.sqrt(((h - hm) ** 2).mean()))
            acc_cum.append(acc)
        return np.asarray(t), np.asarray(h_av), np.asarray(w), h, np.asarray(acc_cum)

    # RSOS 2D
    def simulate_rsos_by_particles(N, n_particles, p, seed):
        rng = np.random.default_rng(seed)
        h = np.zeros((N,N), dtype=int)
        acc = 0
        
        stride = max(1, int(n_particles // 400))
        x_rec, h_av_rec, w_rec = [], [], []
        while acc < n_particles:
            i, j = rng.integers(0, N, 2)
            if rng.random() < p:
                h_try = h[i, j] + 1
                ok = True
                for di, dj in ((1,0),(-1,0),(0,1),(0,-1)):
                    if abs(h_try - h[(i+di)%N, (j+dj)%N]) > 1:
                        ok = False; break
                if ok:
                    h[i, j] = h_try
                    acc += 1
                    if acc % stride == 0 or acc == n_particles:
                        hm = h.mean()
                        x_rec.append(acc)
                        h_av_rec.append(hm)
                        w_rec.append(np.sqrt(((h - hm)**2).mean()))
        return np.asarray(x_rec), np.asarray(h_av_rec), np.asarray(w_rec), h

    # RSOS‑KPZ
    def run_kpz():
        nonlocal last_h_final
        try:
            N       = int(Nx_var.get())
            sweeps  = int(Tstep_var.get())
            p_dep   = float(p_var.get())
            seed    = int(seed_var.get())
            dz_nm   = float(dz_nm_var.get())
            n_part  = int(particles_var.get())
        except Exception as err:
            messagebox.showerror("Input error", str(err)); return
    
        if n_part > 0:
            x_particles, hm_arr, w_arr, h_final = simulate_rsos_by_particles(N, n_part, p_dep, seed)
        else:
            t, hm_arr, w_arr, h_final, acc_cum = simulate_rsos_2d(N, sweeps, p_dep, seed)
            x_particles = acc_cum
    
        h_nm          = h_final.astype(float) * dz_nm
        thickness_nm  = hm_arr * dz_nm
        roughness_nm  = w_arr * dz_nm
        x_plot        = np.maximum(x_particles.astype(float), 1.0)  # 片対数描画用
    
        last_h_final = h_nm.copy()
    
        # CSV output
        _save_height_csv(h_nm, f"rsos_p{p_dep:g}_height")
        _save_csv(x_particles, thickness_nm, roughness_nm,
                  f"rsos_p{p_dep:g}", x_name="particles")
    
        # RSOS Graph 1
        X, Y = np.meshgrid(np.arange(N), np.arange(N))
        fig1 = Figure(figsize=(6.8, 5.0), dpi=100)
        ax1 = fig1.add_subplot(111, projection='3d')
        surf = ax1.plot_surface(X, Y, h_nm, cmap="viridis", linewidth=0, antialiased=False)
        ax1.set_xlabel("x (lattice)")
        ax1.set_ylabel("y (lattice)")
        ax1.set_zlabel("Height (nm)")
        ax1.set_title("RSOS Graph 1")
        fig1.colorbar(surf, ax=ax1, shrink=0.65, label="Height (nm)")
        gw1 = tk.Toplevel(root); gw1.iconbitmap(icon_path)
        gw1.title("RSOS Graph 1"); place_near_root(gw1)
        cvs1 = FigureCanvasTkAgg(fig1, master=gw1); cvs1.draw()
        cvs1.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs1, gw1)
    
        # RSOS Graph 2
        fig2 = Figure(figsize=(6.8, 4.2), dpi=100)
        axL = fig2.add_subplot(111)
        axR = axL.twinx()
        ln1, = axL.plot(x_plot, thickness_nm, lw=1.6, label="Thickness (nm)")
        ln2, = axR.plot(x_plot, roughness_nm, lw=1.6, linestyle="--", label="Roughness (nm)")
        axL.set_xscale("log")
        axL.set_xlabel("Deposited particles (accepted, #)")
        axL.set_ylabel("Thickness (nm)")
        axR.set_ylabel("Roughness (nm)")
        axL.grid(True, alpha=0.35)
        axL.set_title("RSOS Graph 2")
        axL.legend([ln1, ln2], [ln1.get_label(), ln2.get_label()], loc="best")
        gw2 = tk.Toplevel(root); gw2.iconbitmap(icon_path)
        gw2.title("RSOS Graph 2"); place_near_root(gw2)
        cvs2 = FigureCanvasTkAgg(fig2, master=gw2); cvs2.draw()
        cvs2.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs2, gw2)
    
        _log("RSOS Graph 1 & 2 rendered and CSVs saved.")

    # RSOS Graph
    def run_rsos():
        nonlocal last_h_final
        try:
            N       = int(Nx_var.get())
            sweeps  = int(Tstep_var.get())
            p_dep   = float(p_var.get())
            seed    = int(seed_var.get())
            dz_nm   = float(dz_nm_var.get())
            dt      = float(dt_var.get())
            n_part  = int(particles_var.get())
        except Exception as err:
            messagebox.showerror("Input error", str(err)); return

        if n_part > 0:
            x_particles, hm, w, h_final = simulate_rsos_by_particles(N, n_part, p_dep, seed)
        else:
            t, hm, w, h_final, acc_cum = simulate_rsos_2d(N, sweeps, p_dep, seed)
            x_particles = acc_cum

        last_h_final = (h_final.astype(float) * dz_nm).copy()

        thickness_nm = hm * dz_nm
        roughness_nm = w * dz_nm

        x_plot = np.maximum(x_particles.astype(float), 1.0)

        _save_csv(x_particles, thickness_nm, roughness_nm,
                  f"rsos_p{p_dep:g}", x_name="particles")

        # Plot
        fig = Figure(figsize=(6.8, 4.2), dpi=100)
        ax1 = fig.add_subplot(111)
        ax2 = ax1.twinx()

        ln1, = ax1.plot(x_plot, thickness_nm, lw=1.6, label="Thickness (nm)")
        ln2, = ax2.plot(x_plot, roughness_nm, lw=1.6, linestyle="--", label="Roughness (nm)")
        ax1.set_xscale("log")  

        ax1.set_xlabel("Deposited particles (accepted, #)")
        ax1.set_ylabel("Thickness (nm)")
        ax2.set_ylabel("Roughness (nm)")
        ax1.grid(True, alpha=0.35)
        ax1.set_title("RSOS Graph 2")

        lns = [ln1, ln2]
        labs = [l.get_label() for l in lns]
        ax1.legend(lns, labs, loc="best")

        gw = tk.Toplevel(root); gw.iconbitmap(icon_path)
        gw.title("RSOS Graph 2"); place_near_root(gw)
        cvs = FigureCanvasTkAgg(fig, master=gw); cvs.draw()
        cvs.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs, gw)
        _log("RSOS Graph 2 (thickness & roughness vs particles) rendered.")

    # Histgram
    def show_crystallinity():
        if last_h_final is None:
            messagebox.showinfo("Info","先に RSOS または RSOS‑KPZ を実行してください。")
            return
        vals = last_h_final.ravel()
        fig = Figure(figsize=(4.6, 3.6), dpi=100)
        ax = fig.add_subplot(111)
        ax.hist(vals, bins=20, alpha=0.9)
        ax.set_xlabel("Height (nm)")
        ax.set_ylabel("Frequency")
        ax.set_title("Height distribution (proxy for crystallinity)")

        gw = tk.Toplevel(root); gw.iconbitmap(icon_path)
        gw.title("Crystallinity (hist.)"); place_near_root(gw)
        cvs = FigureCanvasTkAgg(fig, master=gw); cvs.draw()
        cvs.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(cvs, gw)

    # CSV Load & Optimization
    def load_external_csv():
        nonlocal loaded_df
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if not path: return
        try:
            loaded_df = pd.read_csv(path)
            _log(f"CSV loaded: {path}")
            messagebox.showinfo("Loaded", f"{os.path.basename(path)} を読み込みました。")
        except Exception as err:
            messagebox.showerror("Load error", str(err))

    def optimize_roughness():
        if loaded_df is None:
            messagebox.showwarning("Warning","まず Load CSV でデータを読み込んでください。")
            return
        if "roughness" not in loaded_df.columns:
            messagebox.showerror("Error","CSV に 'roughness' 列が見つかりません。")
            return
        idx = loaded_df["roughness"].idxmin()
        best = loaded_df.loc[[idx]]
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV files","*.csv")],
                                            initialfile="optimal_condition.csv")
        if not path: return
        try:
            best.to_csv(path, index=False)
            _log(f"Optimal condition saved → {path}")
            messagebox.showinfo("Optimization",
                                f"Minimum roughness = {best['roughness'].values[0]:.4g}\n"
                                "Save the result")
        except Exception as err:
            messagebox.showerror("Save error", str(err))

# ---------------------------------------------------------------------------
#  Edit 
# ---------------------------------------------------------------------------

def button_layout():
    layout_window = tk.Toplevel(root)
    layout_window.iconbitmap(icon_path)
    layout_window.title("Button Layout")
    place_near_root(layout_window)
    
    button_frames = {}
    drag_data = {"widget": None, "x": 0, "y": 0, "row": 0, "column": 0}

    for widget in button_frame.winfo_children():
        button = tk.Button(layout_window, text=widget['text'], width=15)
        button_frames[button] = widget
        button.grid(row=widget.grid_info()['row'], column=widget.grid_info()['column'], padx=0, pady=0)

    def on_drag_start(event):
        widget = event.widget
        drag_data["widget"] = widget
        drag_data["x"] = event.x
        drag_data["y"] = event.y
        drag_data["row"] = widget.grid_info()["row"]
        drag_data["column"] = widget.grid_info()["column"]

    def on_drag_motion(event):
        pass

    def on_drag_end(event):
        widget = drag_data["widget"]
        current_row = widget.grid_info()["row"]
        current_col = widget.grid_info()["column"]

        x = widget.winfo_x() + event.x
        y = widget.winfo_y() + event.y
        target_row = y // 30  
        target_col = x // 90  

        if target_row >= 0 and target_col >= 0:
            for btn in button_frames.keys():
                if btn.grid_info()["row"] == target_row and btn.grid_info()["column"] == target_col:
                    btn.grid(row=current_row, column=current_col, padx=0, pady=0)
                    break
            widget.grid(row=target_row, column=target_col, padx=0, pady=0)

    for button in button_frames.keys():
        button.bind("<Button-1>", on_drag_start)
        button.bind("<B1-Motion>", on_drag_motion)
        button.bind("<ButtonRelease-1>", on_drag_end)

    def run_layout():
        for button, original_button in button_frames.items():
            original_row = button.grid_info()['row']
            original_column = button.grid_info()['column']
            original_button.grid_forget()
            original_button.grid(row=original_row, column=original_column, padx=0, pady=0)
        layout_window.destroy()
        recalc_column_widths()

    menubar = tk.Menu(layout_window)
    layout_window.config(menu=menubar)

    run_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Run", menu=run_menu)
    run_menu.add_command(label="Run", command=run_layout)

def append_parameter_column(header: str, width: int = 15) -> None:
    COLUMN_HEADERS.append(header)
    COLUMN_WIDTHS.append(width)
    
    col_idx = len(COLUMN_HEADERS) - 1
    lbl = tk.Label(label_frame, text=header, relief='solid', bd=1)
    lbl.grid(row=0, column=col_idx, sticky="nsew")
    label_frame.grid_columnconfigure(col_idx, weight=0, minsize=width * CHAR_PX)
    if len(header_labels) <= col_idx:
        header_labels.extend([None]*(col_idx+1-len(header_labels)))
    header_labels[col_idx] = lbl

    def _all_cells():
        for obj in subroutines:
            if isinstance(obj, Subroutine):
                yield from obj.cells
            elif isinstance(obj, Cell):
                yield obj

    for cell in _all_cells():
        e = tk.Entry(cell.cell_frame, width=width, bd=1, relief='solid', justify='left')
        e.grid(row=0, column=col_idx, sticky='nsew')
        e.bind("<KeyRelease>", lambda _ev: mark_as_modified())
        cell.entries.append(e)

    mark_as_modified()
    refresh_load_buttons_layout()
    recalc_column_widths()

def delete_parameter_column(header: str) -> None:
    if header not in COLUMN_HEADERS:
        messagebox.showerror("Error", f"Column '{header}' not found.")
        return
    if header in ORIGINAL_COLUMN_HEADERS:
        messagebox.showerror("Error", "Built‑in columns cannot be deleted.")
        return

    idx = COLUMN_HEADERS.index(header)
    COLUMN_HEADERS.pop(idx)
    COLUMN_WIDTHS.pop(idx)

    for w in label_frame.winfo_children():
        w.destroy()

    header_labels.clear()
    for c, (hdr, w) in enumerate(zip(COLUMN_HEADERS, COLUMN_WIDTHS)):
        lbl_kwargs = {'text': hdr, 'relief':'solid', 'bd':1, 'highlightthickness':0}
        tk.Label(label_frame, **lbl_kwargs).grid(row=0, column=c, sticky='nsew', padx=0, pady=0)
        label_frame.grid_columnconfigure(c, weight=0, minsize=w * CHAR_PX)
        header_labels.append(label_frame.grid_slaves(row=0, column=c)[0])

    ensure_load_header()

    def _all_cells():
        for obj in subroutines:
            if isinstance(obj, Subroutine):
                yield from obj.cells
            elif isinstance(obj, Cell):
                yield obj

    for cell in _all_cells():
        vals = [e.get() for e in cell.entries]
        for e in cell.entries:
            e.destroy()
        del vals[idx-1]                
        cell.entries.clear()

        for col, (w, val) in enumerate(zip(COLUMN_WIDTHS[1:], vals), start=1):
            ent = tk.Entry(cell.cell_frame, width=w, bd=1, relief='solid', justify='left')
            ent.grid(row=0, column=col, sticky='nsew')
            ent.insert(0, val)
            ent.bind("<KeyRelease>", lambda _e: mark_as_modified())
            cell.entries.append(ent)

    mark_as_modified()
    refresh_load_buttons_layout()
    recalc_column_widths()

def button_create():
    win = tk.Toplevel(root)
    win.iconbitmap(icon_path)
    win.title("Create Column")
    win.geometry("200x150")
    place_near_root(win)

    tk.Label(win, text="Parameter Name").pack(pady=(15, 5))
    name_entry = tk.Entry(win, width=22)
    name_entry.pack()

    def on_add():
        hdr = name_entry.get().strip()
        if not hdr:
            messagebox.showerror("Error", "Please enter a parameter name.")
            return
        append_parameter_column(hdr)
        win.destroy()

    def on_delete():
        hdr = name_entry.get().strip()
        if not hdr:
            messagebox.showerror("Error", "Please enter a parameter name.")
            return
        delete_parameter_column(hdr)
        win.destroy()

    btn_frm = tk.Frame(win); btn_frm.pack(pady=12)
    tk.Button(btn_frm, text="Add Parameter", command=on_add).grid(row=0, column=0, sticky="ew", padx=4, pady=2)
    tk.Button(btn_frm, text="Delete Parameter", command=on_delete).grid(row=1, column=0, sticky="ew", padx=4, pady=2)
    btn_frm.grid_columnconfigure(0, weight=1) 

# Edit > Save as CSV files
def save_button_layout(file_path):

    rows = []
    for widget in button_frame.winfo_children():
        rows.append({"Category":"Button",
                     "Name"    : widget.cget("text"),
                     "Row"     : widget.grid_info()["row"],
                     "Col"     : widget.grid_info()["column"]})

    for idx, (hdr, w) in enumerate(zip(COLUMN_HEADERS, COLUMN_WIDTHS)):
        if hdr in ORIGINAL_COLUMN_HEADERS:          
            continue
        rows.append({"Category":"Column",
                     "Name"    : hdr,
                     "Width"   : w,
                     "Position": idx})

    pd.DataFrame(rows).to_csv(file_path, index=False)

# Edit > Button Layout
def load_button_layout(file_path):
    try:
        df = pd.read_csv(file_path)
        for hdr in [h for h in COLUMN_HEADERS if h not in ORIGINAL_COLUMN_HEADERS]:
            delete_parameter_column(hdr)
        col_rows = df[df["Category"]=="Column"].sort_values(by="Position", kind="mergesort")
        for _, r in col_rows.iterrows():
            append_parameter_column(r["Name"], int(r.get("Width", 15)))

        existing = {b.cget("text"): b for b in button_frame.winfo_children()}
        for b in button_frame.winfo_children():
            b.grid_forget()

        btn_rows = df[df["Category"]=="Button"]
        for _, r in btn_rows.iterrows():
            name, row, col = r["Name"], int(r["Row"]), int(r["Col"])
            btn = existing.get(name)
            if btn is None:
                btn = tk.Button(button_frame, text=name,
                                command=lambda: None, width=13)
            btn.grid(row=row, column=col, padx=0, pady=0)
        recalc_column_widths()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load layout: {e}")

# Edit > Save Status
def button_save():
    art_dir = os.path.join(current_dir, "art")
    os.makedirs(art_dir, exist_ok=True)
    file_path = filedialog.asksaveasfilename(initialdir=art_dir, defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if file_path:
        try:
            save_button_layout(file_path)
        except Exception as e:
            messagebox.showerror("Save error", f"Failed to save:\n{e}")

# Edit > Load Status
def button_load():
    art_dir = os.path.join(current_dir, "art")
    os.makedirs(art_dir, exist_ok=True)
    file_path = filedialog.askopenfilename(initialdir=art_dir, defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if file_path:
        try:
            load_button_layout(file_path)
        except Exception as e:
            messagebox.showerror("Load error", f"Failed to load layout:\n{e}")

# ---------------------------------------------------------------------------
#  Help
# ---------------------------------------------------------------------------

def open_web_manual():
    webbrowser.open("https://github.com/nhayase/XROSS")

def open_pdf_manual():
    pdf_path = os.path.join(current_dir, 'doc', 'xross_manual.pdf')
    if os.path.exists(pdf_path):
        os.startfile(pdf_path)
    else:
        tk.messagebox.showerror("File not found", f"Cannot find the file {pdf_path}")
 
# ---------------------------------------------------------------------------
#  Main Window
# ---------------------------------------------------------------------------
    
def display_parameters(parameters):
    parameter_window = tk.Toplevel(root)
    parameter_window.iconbitmap(icon_path)
    parameter_window.title("Parameters")
    
    for name, details in parameters.items():
        frame = tk.Frame(parameter_window)
        frame.pack(fill='x')
        
        label = tk.Label(frame, text=name, width=25)
        label.pack(side=tk.LEFT)
        
        entry = tk.Entry(frame, width=20)
        entry.insert(0, details['value'])
        entry.pack(side=tk.LEFT)
        
        unit_label = tk.Label(frame, text=details['unit'], width=10)
        unit_label.pack(side=tk.LEFT)

# Menu bar
menubar = tk.Menu(root)
root.config(menu=menubar)

# File menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Open", command=open_file, accelerator="Ctrl+O")
file_menu.add_command(label="Save", command=save_file, accelerator="Ctrl+S")
file_menu.add_command(label="Save as...", command=save_as_file, accelerator="Ctrl+Alt+S")
file_menu.add_separator()
file_menu.add_command(label="Exit", command=on_exit, accelerator="Ctrl+E")

# Source menu
source_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Source", menu=source_menu)
source_menu.add_command(label="EUV Optics", command=load_euvr_file, accelerator="F1")
source_menu.add_command(label="XRR Analysis", command=load_analysis_file, accelerator="F2")
source_menu.add_command(label="Deposition", command=load_depo_file, accelerator="F3")

# Edit menu
edit_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Edit", menu=edit_menu)
edit_menu.add_command(label="Button Layout", command=button_layout, accelerator="Ctrl+B")
edit_menu.add_command(label="Create Column", command=button_create, accelerator="Ctrl+N")
edit_menu.add_command(label="Save Status", command=button_save, accelerator="Ctrl+M")
edit_menu.add_command(label="Load Status", command=button_load, accelerator="Ctrl+L")

# Help menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="Web-manual", command=open_web_manual)
help_menu.add_command(label="PDF-manual", command=open_pdf_manual)

# Memo
modelling_title = tk.Label(root, text='So weit die Sonne leuchtet, ist die Hoffnung auch.', font=('Arial', 10))
modelling_title.pack()

button_frame = tk.Frame(root)
button_frame.pack()

spacer = tk.Frame(root, height=10)
spacer.pack()  

# Button layout
button_width = 13

def add_buttons_to_frame():
    row, col = 0, 0
    for widget in button_frame.winfo_children():
        widget.grid_forget()
    for widget in button_frame.winfo_children():
        widget.grid(row=row, column=col, padx=0, pady=0)
        col += 1
        if col == 6:
            row += 1
            col = 0

add_button = tk.Button(button_frame, text='Add Layer', command=add_layer, width=button_width)
add_button.grid(row=1, column=0, padx=0, pady=0)

delete_button = tk.Button(button_frame, text='Delete Layer', width=button_width, command=delete_layer)
delete_button.grid(row=1, column=0, padx=0, pady=0)

add_subroutine_button = tk.Button(button_frame, text='Add Subroutine', command=add_subroutine, width=button_width)
add_subroutine_button.grid(row=0, column=1, padx=0, pady=0)

delete_subroutine_button = tk.Button(button_frame, text='Del Subroutine', command=delete_subroutine, width=button_width)
delete_subroutine_button.grid(row=1, column=1, padx=0, pady=0)

up_button = tk.Button(button_frame, text='Up', command=move_selected_up, width=button_width)
up_button.grid(row=0, column=2, padx=0, pady=0)

down_button = tk.Button(button_frame, text='Down', command=move_selected_down, width=button_width)
down_button.grid(row=1, column=2, padx=0, pady=0)

all_clear_button = tk.Button(button_frame, text='All Clear', command=all_clear, width=button_width)
all_clear_button.grid(row=0, column=3, padx=0, pady=0)

report_button = tk.Button(button_frame, text='Log Window', command=record, width=button_width)
report_button.grid(row=1, column=4, padx=0, pady=0)

depict_button = tk.Button(button_frame, text='Depiction', command=depict_layer, width=button_width)
depict_button.grid(row=1, column=5, padx=0, pady=0)

# PanelWindow console 
paned_window = tk.PanedWindow(root, orient=tk.VERTICAL)
paned_window.pack(fill=tk.BOTH, expand=True)

canvas_frame = tk.Frame(paned_window)
paned_window.add(canvas_frame)

canvas = tk.Canvas(canvas_frame)
scrollbar_y = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
scrollbar_y.pack(side="right", fill="y")
scrollbar_x = tk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
scrollbar_x.pack(side="bottom", fill="x")
canvas.pack(side="left", fill="both", expand=True)
canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

scrollable_frame = tk.Frame(canvas)
scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

param_frame = tk.Frame(scrollable_frame)
param_frame.pack()

label_frame = tk.Frame(param_frame, bd=1, relief='solid', highlightthickness=0)
label_frame.pack(fill='x', padx=LAYER_PADX)
label_frame.grid_columnconfigure(0, weight=0, minsize=SELECT_COL_PX)

# Header
header_labels.clear()
for c, (hdr, w) in enumerate(zip(COLUMN_HEADERS, COLUMN_WIDTHS)):
    lbl_kwargs = {'text': hdr, 'relief': 'solid', 'bd': 1, 'highlightthickness': 0}
    tk.Label(label_frame, **lbl_kwargs).grid(row=0, column=c, sticky='nsew', padx=0, pady=0)
    label_frame.grid_columnconfigure(c, weight=0)  
    header_labels.append(label_frame.grid_slaves(row=0, column=c)[0])

ensure_load_header() 
root.protocol("WM_DELETE_WINDOW", on_exit)

# Shortcuts
root.bind('<Control-o>',     lambda event: open_file())
root.bind('<Control-s>',     lambda event: save_file())
root.bind('<Control-Alt-s>', lambda event: save_as_file())
root.bind('<Control-e>',     lambda event: on_exit())
root.bind('<Control-b>',     lambda event: button_layout())
root.bind('<F1>',            lambda event: load_euvr_file())
root.bind('<F2>',            lambda event: load_analysis_file())
root.bind('<F3>',            lambda event: load_depo_file())
root.bind('<Control-n>',     lambda event: button_create())
root.bind('<Control-m>',     lambda event: button_save())
root.bind('<Control-l>',     lambda event: button_load())

create_log_window()   
log_window.withdraw()
add_buttons_to_frame()

def _on_root_resize(_ev=None):
    recalc_column_widths()
root.bind("<Configure>", lambda ev: _on_root_resize(ev))

root.mainloop()
