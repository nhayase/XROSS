"""
xross.gui.app — Main application window.
Full v1.0.4 feature parity: freeze checkboxes, Up/Down, Edit menu, Image Analysis.
"""
import csv, datetime, os, platform, sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from itertools import zip_longest
import numpy as np, pandas as pd
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from xross import __version__
from xross.fileio import log_message

_root=None; _icon_path=""; _current_dir=""; _console=None; _log_window=None
subroutines=[]; orphan_layers=[]
current_subroutine=None; current_layer=None
current_file_path=None; is_modified=False
COLUMN_HEADERS=["","Name","n","k","Thickness (nm)","Density (g/cm³)","Roughness (nm)"]
ORIGINAL_COLUMN_HEADERS=COLUMN_HEADERS.copy()
COLUMN_WIDTHS=[5,10,10,10,15,15,15]
CHAR_PX=7.5; LAYER_PADX=0; SELECT_COL_CHARS=3; LOAD_COL_CHARS=8; NAME_COL_CHARS=20
SELECT_COL_PX=SELECT_COL_CHARS*CHAR_PX
header_labels=[]; label_frame=None; param_frame=None; button_frame=None

def _entry_index_for(header):
    try:
        i=COLUMN_HEADERS.index(header)-1
        return i if i>=0 else None
    except ValueError: return None

def place_near_root(toplevel,dx=620,dy=-50):
    if _root is None: return
    _root.update_idletasks(); toplevel.geometry(f"+{_root.winfo_rootx()+dx}+{_root.winfo_rooty()+dy}")
def mark_as_modified():
    global is_modified; is_modified=True; _update_title()
def mark_as_unmodified():
    global is_modified; is_modified=False; _update_title()
def _update_title():
    if _root is None: return
    t=f"XROSS {__version__}"
    if current_file_path: t+=f" - {os.path.basename(current_file_path)}"
    if is_modified: t+=" *"
    _root.title(t)
def _log(msg):
    line=log_message(msg,_current_dir)
    if _console and _console.winfo_exists(): _console.insert(tk.END,line); _console.see(tk.END)

def _find_icon():
    """Search favicon.ico in multiple locations."""
    candidates=[
        os.path.join(_current_dir,"favicon.ico"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","..","favicon.ico"),
        os.path.join(os.path.dirname(sys.executable),"favicon.ico") if getattr(sys,'_MEIPASS',None) else "",
        os.path.join(getattr(sys,'_MEIPASS',''),"favicon.ico") if getattr(sys,'_MEIPASS',None) else "",
    ]
    for c in candidates:
        if c and os.path.exists(c): return os.path.abspath(c)
    return ""

def _set_icon(w):
    if _icon_path and os.path.exists(_icon_path):
        try: w.iconbitmap(_icon_path)
        except: pass

def create_log_window():
    global _log_window, _console
    if _log_window and _log_window.winfo_exists(): return
    _log_window=tk.Toplevel(_root); _set_icon(_log_window)
    _log_window.title("Log Window")
    _root.update_idletasks()
    # Use winfo_x (frame left edge) for horizontal alignment
    rx = _root.winfo_x(); rw = _root.winfo_width()
    bottom = _root.winfo_rooty() + _root.winfo_height()
    _log_window.geometry(f"{rw}x200+{rx}+{bottom}")
    _log_window.protocol("WM_DELETE_WINDOW",lambda:_log_window.withdraw())
    sx=tk.Scrollbar(_log_window,orient="horizontal"); sy=tk.Scrollbar(_log_window,orient="vertical")
    sx.pack(side="bottom",fill="x"); sy.pack(side="right",fill="y")
    _console=tk.Text(_log_window,wrap="none",xscrollcommand=sx.set,yscrollcommand=sy.set)
    _console.pack(side="left",fill="both",expand=True); sx.config(command=_console.xview); sy.config(command=_console.yview)
def record():
    if not (_log_window and _log_window.winfo_exists()): create_log_window()
    else:
        _root.update_idletasks()
        rx = _root.winfo_x(); rw = _root.winfo_width()
        bottom = _root.winfo_rooty() + _root.winfo_height()
        _log_window.geometry(f"{rw}x200+{rx}+{bottom}")
    _log_window.deiconify(); _log_window.lift()

# === Cell with freeze checkboxes ===
class Cell:
    def __init__(self,parent):
        self.layer_frames=[]; self.entries=[]; self.selected=False; self.nk_data=None; self.nk_path=None
        self.cell_frame=tk.Frame(parent,bd=1,relief="solid"); self.cell_frame.pack(fill="x",padx=LAYER_PADX); self.layer_frames.append(self.cell_frame)
        self.select_button=tk.Label(self.cell_frame,text=" ",bg="lightgrey",relief="solid",bd=1,highlightthickness=0)
        self.select_button.grid(row=0,column=0,sticky="nsew"); self.select_button.bind("<Button-1>",self.on_click)
        for col,w in enumerate(COLUMN_WIDTHS[1:],start=1):
            e=tk.Entry(self.cell_frame,width=w,bd=1,relief="solid",justify="left",highlightthickness=0)
            e.grid(row=0,column=col,sticky="nsew"); e.bind("<KeyRelease>",lambda _:mark_as_modified()); self.entries.append(e)
        self.freeze_vars={"thk":tk.BooleanVar(value=False),"den":tk.BooleanVar(value=False),"rou":tk.BooleanVar(value=False)}
        self.freeze_cbs={}
        self.load_button=tk.Button(self.cell_frame,text="Click",width=LOAD_COL_CHARS,command=self._load_nk,bd=1,highlightthickness=0)
        self.nk_var=tk.StringVar(value="")
        self.nk_entry=tk.Entry(self.cell_frame,textvariable=self.nk_var,bd=1,relief="solid",state="disabled",disabledbackground="white",disabledforeground="black")
        cl=len(COLUMN_WIDTHS); cn=cl+1
        self.load_button.grid(row=0,column=cl,sticky="nsew"); self.nk_entry.grid(row=0,column=cn,sticky="nsew")
        # Column alignment: match header widths
        _px=[int(SELECT_COL_CHARS*CHAR_PX)]+[int(w*CHAR_PX) for w in COLUMN_WIDTHS[1:]]+[int(LOAD_COL_CHARS*CHAR_PX),int(NAME_COL_CHARS*CHAR_PX)]
        for c,w in enumerate(_px): self.cell_frame.grid_columnconfigure(c,weight=(1 if c==cn else 0),minsize=w)
        self.place_freeze_checkboxes()

    def place_freeze_checkboxes(self):
        idx_thk=_entry_index_for("Thickness (nm)")
        idx_den=_entry_index_for("Density (g/cm³)")
        idx_rou=_entry_index_for("Roughness (nm)")
        mapping=[("thk",idx_thk),("den",idx_den),("rou",idx_rou)]
        for key,idx in mapping:
            if idx is None or idx>=len(self.entries) or self.entries[idx] is None:
                if key in self.freeze_cbs and self.freeze_cbs[key].winfo_exists():
                    try: self.freeze_cbs[key].place_forget(); self.freeze_cbs[key].destroy()
                    except: pass
                self.freeze_cbs.pop(key,None); continue
            ent=self.entries[idx]
            cb=self.freeze_cbs.get(key)
            if cb is None or not cb.winfo_exists():
                cb=tk.Checkbutton(self.cell_frame,variable=self.freeze_vars[key],padx=0,pady=0,bd=0,highlightthickness=0,takefocus=False)
                cb.bind("<ButtonRelease-1>",lambda _:mark_as_modified())
                self.freeze_cbs[key]=cb
            try: cb.place(in_=ent,relx=1.0,x=-14,rely=0.5,anchor="e")
            except: pass

    def _load_nk(self):
        from xross.core import parse_nk_file
        path=filedialog.askopenfilename(title="Select nk file",filetypes=[("nk files","*.nk *.txt *.dat *.csv"),("All","*.*")])
        if not path: return
        try:
            lam,n,k=parse_nk_file(path); self.nk_data={"lam_nm":lam,"n":n,"k":k}; self.nk_path=path
            if not (self.entries and self.entries[0].get().strip()): self.entries[0].insert(0,os.path.splitext(os.path.basename(path))[0])
            self.nk_entry.config(state="normal"); self.nk_var.set(os.path.basename(path)); self.nk_entry.config(state="disabled")
            _log(f"Loaded nk: {os.path.basename(path)} (N={len(lam)})")
        except Exception as e: messagebox.showerror("nk error",str(e))
    def on_click(self,event):
        global current_layer,current_subroutine
        if self.selected: self.select_button.config(bg="lightgrey"); self.selected=False; current_layer=None
        else:
            if current_layer: current_layer.select_button.config(bg="lightgrey"); current_layer.selected=False
            if current_subroutine: current_subroutine.label.config(bg="lightgrey"); current_subroutine.selected=False
            self.select_button.config(bg="blue"); self.selected=True; current_layer=self; current_subroutine=None
    def get_freeze_states(self): return {k:bool(v.get()) for k,v in self.freeze_vars.items()}
    def to_dict(self): return {"entries":[e.get() for e in self.entries]}

# === Subroutine with ↑↓ ===
class Subroutine:
    def __init__(self,name,parent):
        self.name=name; self.loop_count=1; self.cells=[]; self.selected=False; self.collapsed=False
        self.frame=tk.Frame(parent); self.frame.pack(fill="x",pady=10)
        self.header_frame=tk.Frame(self.frame); self.header_frame.pack(fill="x")
        tk.Button(self.header_frame,text="+",width=2,command=self.toggle).pack(side=tk.LEFT)
        tk.Button(self.header_frame,text="↑",width=2,command=self.move_layer_up).pack(side=tk.LEFT)
        tk.Button(self.header_frame,text="↓",width=2,command=self.move_layer_down).pack(side=tk.LEFT)
        self.label=tk.Label(self.header_frame,text=f"{name}({self.loop_count})",font=("Arial",14),bg="lightgrey")
        self.label.pack(side=tk.LEFT,fill="x"); self.label.bind("<Button-1>",self.on_click); self.label.bind("<Button-3>",self.on_right_click)
        self.cells_frame=tk.Frame(self.frame); self.cells_frame.pack(fill="x")
    def add_cell(self): c=Cell(self.cells_frame); self.cells.append(c)
    def move_layer_up(self):
        if current_layer and current_layer.selected and current_layer in self.cells:
            i=self.cells.index(current_layer)
            if i>0: self.cells[i],self.cells[i-1]=self.cells[i-1],self.cells[i]; self._repack(); mark_as_modified()
    def move_layer_down(self):
        if current_layer and current_layer.selected and current_layer in self.cells:
            i=self.cells.index(current_layer)
            if i<len(self.cells)-1: self.cells[i],self.cells[i+1]=self.cells[i+1],self.cells[i]; self._repack(); mark_as_modified()
    def _repack(self):
        for c in self.cells: c.cell_frame.pack_forget(); c.cell_frame.pack(fill="x",padx=LAYER_PADX)
    def on_click(self,event):
        global current_subroutine,current_layer
        if current_subroutine==self: self.label.config(bg="lightgrey"); self.selected=False; current_subroutine=None
        else:
            if current_subroutine: current_subroutine.label.config(bg="lightgrey"); current_subroutine.selected=False
            if current_layer: current_layer.select_button.config(bg="lightgrey"); current_layer.selected=False
            self.label.config(bg="blue"); self.selected=True; current_subroutine=self; current_layer=None
    def on_right_click(self,event):
        lc=simpledialog.askinteger("Set Loop Count","Enter loop count:",initialvalue=self.loop_count)
        if lc: self.loop_count=lc; mark_as_modified()
        self.label.config(text=f"{self.name}({self.loop_count})")
    def toggle(self):
        self.collapsed=not self.collapsed
        if self.collapsed: self.cells_frame.pack_forget()
        else: self.cells_frame.pack(fill="x")

# === Layer management ===
def add_subroutine():
    sub=Subroutine("Right-click",param_frame); subroutines.append(sub)
    sub.label.bind("<Button-1>",lambda e,s=sub:_select_sub(s)); mark_as_modified()
def _select_sub(sub):
    global current_subroutine,current_layer
    if current_subroutine==sub: current_subroutine.label.config(bg="lightgrey"); current_subroutine.selected=False; current_subroutine=None
    else:
        if current_subroutine: current_subroutine.label.config(bg="lightgrey"); current_subroutine.selected=False
        if current_layer: current_layer.select_button.config(bg="lightgrey"); current_layer.selected=False; current_layer=None
        sub.label.config(bg="blue"); sub.selected=True; current_subroutine=sub
def delete_subroutine():
    global current_subroutine
    if current_subroutine and current_subroutine.selected: current_subroutine.frame.destroy(); subroutines.remove(current_subroutine); current_subroutine=None; mark_as_modified()
def add_layer():
    if current_subroutine and current_subroutine.selected: current_subroutine.add_cell(); mark_as_modified()
    else: c=Cell(param_frame); orphan_layers.append(c); subroutines.append(c); mark_as_modified()
def delete_layer():
    global current_layer
    if current_layer and current_layer.selected:
        for s in subroutines:
            if isinstance(s,Subroutine) and current_layer in s.cells: s.cells.remove(current_layer); break
        if current_layer in orphan_layers: orphan_layers.remove(current_layer)
        if current_layer in subroutines: subroutines.remove(current_layer)
        for f in current_layer.layer_frames: f.destroy()
        current_layer=None; mark_as_modified()
def move_selected_up():
    if current_layer and current_layer.selected: _move_item(current_layer,-1)
    elif current_subroutine and current_subroutine.selected: _move_item(current_subroutine,-1)
    mark_as_modified()
def move_selected_down():
    if current_layer and current_layer.selected: _move_item(current_layer,1)
    elif current_subroutine and current_subroutine.selected: _move_item(current_subroutine,1)
    mark_as_modified()
def _move_item(item,direction):
    if item not in subroutines: return
    i=subroutines.index(item); n=i+direction
    if 0<=n<len(subroutines):
        subroutines[i],subroutines[n]=subroutines[n],subroutines[i]
        for it in subroutines:
            if isinstance(it,Subroutine): it.frame.pack_forget(); it.frame.pack(fill="x",pady=10)
            elif isinstance(it,Cell): it.cell_frame.pack_forget(); it.cell_frame.pack(fill="x",padx=LAYER_PADX)
def clear_current_state():
    global subroutines,orphan_layers,current_subroutine,current_layer
    for s in subroutines:
        if isinstance(s,Subroutine): s.frame.destroy()
        elif isinstance(s,Cell):
            for f in s.layer_frames: f.destroy()
    subroutines.clear(); orphan_layers.clear(); current_subroutine=None; current_layer=None
def all_clear():
    if messagebox.askyesno("Confirm","Are you sure you want to clear all Layers and Subroutines?"):
        clear_current_state(); _log("All cleared."); mark_as_modified()

# === File ops ===
def _save_state(fp):
    rows,mp=[],0
    for o in subroutines:
        if isinstance(o,Subroutine):
            for c in o.cells: p=[e.get() for e in c.entries]; rows.append([o.name,str(o.loop_count)]+p); mp=max(mp,len(p))
        elif isinstance(o,Cell): p=[e.get() for e in o.entries]; rows.append(["Orphan",""]+p); mp=max(mp,len(p))
    hdr=["Subroutine","Loop Count"]+[f"Param{i+1}" for i in range(mp)]
    fx=[(r+[""]*(len(hdr)-len(r)))[:len(hdr)] for r in rows]
    with open(fp,"w",newline="",encoding="utf-8") as f: w=csv.writer(f); w.writerow(hdr); w.writerows(fx)
    _log(f"Saved {fp}"); mark_as_unmodified()
def _load_state(fp):
    df=pd.read_csv(fp,dtype=str).fillna(""); clear_current_state()
    for _,row in df.iterrows():
        nm,lp,params=row["Subroutine"],row["Loop Count"],list(row.iloc[2:].values)
        if nm=="Orphan":
            c=Cell(param_frame)
            for e,v in zip_longest(c.entries,params,fillvalue=""): e.delete(0,tk.END); e.insert(0,v)
            orphan_layers.append(c); subroutines.append(c); continue
        sub=next((s for s in subroutines if isinstance(s,Subroutine) and s.name==nm),None)
        if sub is None: sub=Subroutine(nm,param_frame); subroutines.append(sub)
        try: sub.loop_count=int(lp) if str(lp).strip() else 1
        except: sub.loop_count=1
        sub.label.config(text=f"{sub.name}({sub.loop_count})")
        c=Cell(sub.cells_frame)
        for e,v in zip_longest(c.entries,params,fillvalue=""): e.delete(0,tk.END); e.insert(0,v)
        sub.cells.append(c)
    mark_as_unmodified()
def open_file():
    global current_file_path
    fp=filedialog.askopenfilename(initialdir=os.path.join(_current_dir,"geo"),filetypes=[("CSV","*.csv")])
    if fp: _load_state(fp); current_file_path=fp; _update_title()
def save_file():
    if current_file_path: _save_state(current_file_path)
    else: save_as_file()
def save_as_file():
    global current_file_path
    fp=filedialog.asksaveasfilename(initialdir=os.path.join(_current_dir,"geo"),defaultextension=".csv",filetypes=[("CSV","*.csv")])
    if fp: _save_state(fp); current_file_path=fp; _update_title()
def on_exit():
    if is_modified:
        r=messagebox.askyesnocancel("Save?","Save changes?")
        if r is None: return
        if r: save_file()
    _root.destroy()

# === Edit menu functions ===
def append_parameter_column(header,width=15):
    COLUMN_HEADERS.append(header); COLUMN_WIDTHS.append(width)
    ci=len(COLUMN_HEADERS)-1
    lbl=tk.Label(label_frame,text=header,relief="solid",bd=1); lbl.grid(row=0,column=ci,sticky="nsew")
    if len(header_labels)<=ci: header_labels.extend([None]*(ci+1-len(header_labels)))
    header_labels[ci]=lbl
    for obj in subroutines:
        cells=obj.cells if isinstance(obj,Subroutine) else [obj] if isinstance(obj,Cell) else []
        for cell in cells:
            e=tk.Entry(cell.cell_frame,width=width,bd=1,relief="solid",justify="left")
            e.grid(row=0,column=ci,sticky="nsew"); e.bind("<KeyRelease>",lambda _:mark_as_modified()); cell.entries.append(e)
    mark_as_modified()
def delete_parameter_column(header):
    if header not in COLUMN_HEADERS: messagebox.showerror("Error",f"'{header}' not found."); return
    if header in ORIGINAL_COLUMN_HEADERS: messagebox.showerror("Error","Built-in columns cannot be deleted."); return
    idx=COLUMN_HEADERS.index(header); COLUMN_HEADERS.pop(idx); COLUMN_WIDTHS.pop(idx)
    for w in label_frame.winfo_children(): w.destroy()
    header_labels.clear()
    for c,(h,w) in enumerate(zip(COLUMN_HEADERS,COLUMN_WIDTHS)):
        l=tk.Label(label_frame,text=h,relief="solid",bd=1,highlightthickness=0); l.grid(row=0,column=c,sticky="nsew"); header_labels.append(l)
    cl=len(COLUMN_WIDTHS); cn=cl+1
    tk.Label(label_frame,text="Load",relief="solid",bd=1).grid(row=0,column=cl,sticky="nsew")
    tk.Label(label_frame,text="nk file name",relief="solid",bd=1).grid(row=0,column=cn,sticky="nsew")
    for obj in subroutines:
        cells=obj.cells if isinstance(obj,Subroutine) else [obj] if isinstance(obj,Cell) else []
        for cell in cells:
            vals=[e.get() for e in cell.entries]; [e.destroy() for e in cell.entries]; del vals[idx-1]; cell.entries.clear()
            for col,(w,val) in enumerate(zip(COLUMN_WIDTHS[1:],vals),start=1):
                ent=tk.Entry(cell.cell_frame,width=w,bd=1,relief="solid",justify="left")
                ent.grid(row=0,column=col,sticky="nsew"); ent.insert(0,val); ent.bind("<KeyRelease>",lambda _:mark_as_modified()); cell.entries.append(ent)
    mark_as_modified()
def button_create():
    w=tk.Toplevel(_root); _set_icon(w); w.title("Create Column"); w.geometry("200x150"); place_near_root(w)
    tk.Label(w,text="Parameter Name").pack(pady=(15,5)); ne=tk.Entry(w,width=22); ne.pack()
    bf=tk.Frame(w); bf.pack(pady=12)
    tk.Button(bf,text="Add Parameter",command=lambda:(append_parameter_column(ne.get().strip()),w.destroy()) if ne.get().strip() else None).grid(row=0,column=0,padx=4,pady=2)
    tk.Button(bf,text="Delete Parameter",command=lambda:(delete_parameter_column(ne.get().strip()),w.destroy()) if ne.get().strip() else None).grid(row=1,column=0,padx=4,pady=2)
def button_layout():
    lw=tk.Toplevel(_root); _set_icon(lw); lw.title("Button Layout"); place_near_root(lw)
    bfs={}
    for widget in button_frame.winfo_children():
        b=tk.Button(lw,text=widget["text"],width=15); bfs[b]=widget
        b.grid(row=widget.grid_info()["row"],column=widget.grid_info()["column"])
    def run_layout():
        for b,orig in bfs.items(): orig.grid_forget(); orig.grid(row=b.grid_info()["row"],column=b.grid_info()["column"])
        lw.destroy()
    mb=tk.Menu(lw); lw.config(menu=mb); rm=tk.Menu(mb,tearoff=0); mb.add_cascade(label="Run",menu=rm); rm.add_command(label="Run",command=run_layout)
def save_button_layout(fp):
    rows=[]
    for w in button_frame.winfo_children(): rows.append({"Category":"Button","Name":w.cget("text"),"Row":w.grid_info()["row"],"Col":w.grid_info()["column"]})
    for i,(h,w) in enumerate(zip(COLUMN_HEADERS,COLUMN_WIDTHS)):
        if h in ORIGINAL_COLUMN_HEADERS: continue
        rows.append({"Category":"Column","Name":h,"Width":w,"Position":i})
    pd.DataFrame(rows).to_csv(fp,index=False)
def load_button_layout(fp):
    try:
        df=pd.read_csv(fp)
        for h in [h for h in COLUMN_HEADERS if h not in ORIGINAL_COLUMN_HEADERS]: delete_parameter_column(h)
        for _,r in df[df["Category"]=="Column"].sort_values("Position").iterrows(): append_parameter_column(r["Name"],int(r.get("Width",15)))
        existing={b.cget("text"):b for b in button_frame.winfo_children()}
        for b in button_frame.winfo_children(): b.grid_forget()
        for _,r in df[df["Category"]=="Button"].iterrows():
            btn=existing.get(r["Name"])
            if btn: btn.grid(row=int(r["Row"]),column=int(r["Col"]))
    except Exception as e: messagebox.showerror("Error",str(e))
def button_save():
    ad=os.path.join(_current_dir,"art"); os.makedirs(ad,exist_ok=True)
    fp=filedialog.asksaveasfilename(initialdir=ad,defaultextension=".csv",filetypes=[("CSV","*.csv")])
    if fp: save_button_layout(fp)
def button_load():
    ad=os.path.join(_current_dir,"art"); os.makedirs(ad,exist_ok=True)
    fp=filedialog.askopenfilename(initialdir=ad,filetypes=[("CSV","*.csv")])
    if fp: load_button_layout(fp)

# === Depiction ===
def depict_layer():
    lc,dl,br,sl={},[], [],[]
    z=0.0; cmap=plt.cm.get_cmap("tab20",20); cc=0
    for o in subroutines:
        if isinstance(o,Subroutine):
            bc=[]
            for c in o.cells:
                if c not in lc: lc[c]=cc; cc+=1
                bc.append(lc[c])
            zs=z
            for _ in range(max(1,int(o.loop_count))):
                for c,ci in zip(o.cells,bc):
                    try: thk=max(float(c.entries[3].get()),1e-3)
                    except: thk=1.0
                    dl.append((thk,ci)); z+=thk
            br.append((zs,z,o.name,o.loop_count))
        elif isinstance(o,Cell):
            if o not in lc: lc[o]=cc; cc+=1
            try: thk=max(float(o.entries[3].get()),1e-3)
            except: thk=1.0
            dl.append((thk,lc[o])); sl.append((z+thk/2,o.entries[0].get() or f"Layer{len(dl)}")); z+=thk
    if not dl: messagebox.showwarning("","No Layer to depict."); return
    fig=Figure(figsize=(4,6),dpi=100); ax=fig.add_subplot(111,projection="3d")
    ax.set_facecolor("none"); fig.patch.set_facecolor("white"); ax.set_xlim(0,1.35); ax.set_ylim(0,1); ax.set_zlim(0,z*1.05)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([]); ax._axis3don=False
    z0=0.0
    for thk,ci in dl: ax.bar3d(0,0,z0,1,1,thk,color=cmap(ci%cmap.N),shade=True,alpha=0.9); z0+=thk
    for zm,txt in sl: ax.text(1.05,0.5,zm,txt,ha="left",va="center",fontsize=8)
    for z0b,z1b,nm,lp in br:
        zm=0.5*(z0b+z1b); hf=(z1b-z0b)/z if z>0 else 0.1; bf=max(8,int(35*hf))
        ax.text(1.02,0.5,zm,"}",fontsize=bf,ha="left",va="center"); ax.text(1.10,0.5,zm,f"{nm} ({lp})",ha="left",va="center",fontsize=8)
    w=tk.Toplevel(_root); _set_icon(w); w.title("Depiction Window"); place_near_root(w)
    cvs=FigureCanvasTkAgg(fig,master=w); cvs.draw(); cvs.get_tk_widget().pack(fill="both",expand=True); NavigationToolbar2Tk(cvs,w)

# === Sub-window launchers ===
def _open_euv():
    from xross.gui.euv_window import open_euv_window
    open_euv_window(_root,_icon_path,_current_dir,subroutines,orphan_layers,_log,place_near_root,Cell,Subroutine)
def _open_xrr():
    from xross.gui.xrr_window import open_xrr_window
    open_xrr_window(_root,_icon_path,_current_dir,subroutines,orphan_layers,_log,place_near_root,mark_as_modified,Cell,Subroutine)
def _open_opt():
    from xross.gui.opt_window import open_opt_window
    open_opt_window(_root,_icon_path,_current_dir,_log,place_near_root)
def _open_image():
    from xross.gui.image_window import open_image_window
    open_image_window(_root,_icon_path,_current_dir,_log,place_near_root)
def open_web_manual():
    import webbrowser; webbrowser.open("https://github.com/nhayase/XROSS")

# === run() ===
def run():
    global _root,_icon_path,_current_dir,label_frame,param_frame,button_frame
    _root=tk.Tk(); _root.geometry("620x420")
    _current_dir=os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv[0] else os.getcwd()
    _icon_path=_find_icon()
    _set_icon(_root)
    if platform.system()=="Windows":
        try: import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xross.v2")
        except: pass
    _update_title()
    mb=tk.Menu(_root); _root.config(menu=mb)
    fm=tk.Menu(mb,tearoff=0); mb.add_cascade(label="File",menu=fm)
    fm.add_command(label="Open",command=open_file,accelerator="Ctrl+O"); fm.add_command(label="Save",command=save_file,accelerator="Ctrl+S")
    fm.add_command(label="Save as...",command=save_as_file,accelerator="Ctrl+Alt+S"); fm.add_separator(); fm.add_command(label="Exit",command=on_exit,accelerator="Ctrl+E")
    sm=tk.Menu(mb,tearoff=0); mb.add_cascade(label="Source",menu=sm)
    sm.add_command(label="EUV Optics",command=_open_euv,accelerator="F1"); sm.add_command(label="XRR Analysis",command=_open_xrr,accelerator="F2")
    sm.add_command(label="Optimization",command=_open_opt,accelerator="F3"); sm.add_command(label="Image Analysis",command=_open_image,accelerator="F4")
    hm=tk.Menu(mb,tearoff=0); mb.add_cascade(label="Help",menu=hm)
    hm.add_command(label="Web-manual",command=open_web_manual); hm.add_command(label="About Us",command=lambda:__import__('webbrowser').open("https://euvmask.com"))
    tk.Label(_root,text="So weit die Sonne leuchtet, ist die Hoffnung auch.",font=("Arial",10)).pack()
    tk.Label(_root,text="Layer order: Top row = Surface,  Bottom row = Substrate",font=("Arial",8),fg="gray").pack()
    button_frame=tk.Frame(_root); button_frame.pack(); bw=13
    tk.Button(button_frame,text="Add Layer",command=add_layer,width=bw).grid(row=0,column=0)
    tk.Button(button_frame,text="Delete Layer",command=delete_layer,width=bw).grid(row=1,column=0)
    tk.Button(button_frame,text="Add Subroutine",command=add_subroutine,width=bw).grid(row=0,column=1)
    tk.Button(button_frame,text="Del Subroutine",command=delete_subroutine,width=bw).grid(row=1,column=1)
    tk.Button(button_frame,text="Up",command=move_selected_up,width=bw).grid(row=0,column=2)
    tk.Button(button_frame,text="Down",command=move_selected_down,width=bw).grid(row=1,column=2)
    tk.Button(button_frame,text="All Clear",command=all_clear,width=bw).grid(row=0,column=3)
    tk.Button(button_frame,text="Log Window",command=record,width=bw).grid(row=1,column=3)
    tk.Frame(_root,height=10).pack()
    pn=tk.PanedWindow(_root,orient=tk.VERTICAL); pn.pack(fill=tk.BOTH,expand=True)
    cf=tk.Frame(pn); pn.add(cf)
    cv=tk.Canvas(cf); sby=tk.Scrollbar(cf,orient="vertical",command=cv.yview); sby.pack(side="right",fill="y")
    sbx=tk.Scrollbar(cf,orient="horizontal",command=cv.xview); sbx.pack(side="bottom",fill="x")
    cv.pack(side="left",fill="both",expand=True); cv.configure(yscrollcommand=sby.set,xscrollcommand=sbx.set)
    sf=tk.Frame(cv); sf.bind("<Configure>",lambda e:cv.configure(scrollregion=cv.bbox("all"))); cv.create_window((0,0),window=sf,anchor="nw")
    param_frame=tk.Frame(sf); param_frame.pack()
    label_frame=tk.Frame(param_frame,bd=1,relief="solid",highlightthickness=0); label_frame.pack(fill="x",padx=LAYER_PADX)
    header_labels.clear()
    for c,(hdr,w) in enumerate(zip(COLUMN_HEADERS,COLUMN_WIDTHS)):
        l=tk.Label(label_frame,text=hdr,relief="solid",bd=1,highlightthickness=0); l.grid(row=0,column=c,sticky="nsew"); header_labels.append(l)
    cl=len(COLUMN_WIDTHS); cn=cl+1
    tk.Label(label_frame,text="Load",relief="solid",bd=1).grid(row=0,column=cl,sticky="nsew")
    tk.Label(label_frame,text="nk file name",relief="solid",bd=1).grid(row=0,column=cn,sticky="nsew")
    # Apply grid_columnconfigure to header for column alignment
    _px=[int(SELECT_COL_CHARS*CHAR_PX)]+[int(w*CHAR_PX) for w in COLUMN_WIDTHS[1:]]+[int(LOAD_COL_CHARS*CHAR_PX),int(NAME_COL_CHARS*CHAR_PX)]
    for c,w in enumerate(_px): label_frame.grid_columnconfigure(c,weight=(1 if c==cn else 0),minsize=w)
    _root.bind("<Control-o>",lambda e:open_file()); _root.bind("<Control-s>",lambda e:save_file()); _root.bind("<Control-Alt-s>",lambda e:save_as_file()); _root.bind("<Control-e>",lambda e:on_exit())
    _root.bind("<F1>",lambda e:_open_euv()); _root.bind("<F2>",lambda e:_open_xrr()); _root.bind("<F3>",lambda e:_open_opt()); _root.bind("<F4>",lambda e:_open_image())
    _root.protocol("WM_DELETE_WINDOW",on_exit); create_log_window(); _log_window.withdraw()
    # Default substrate (Si, bottom layer)
    # Layer order: top = surface (first row), bottom = substrate (last row)
    _sub_cell=Cell(param_frame)
    _sub_cell.entries[0].insert(0,"Si")                    # Name
    _sub_cell.entries[1].insert(0,"0.99999463")            # n (Si @ Cu-Ka)
    _sub_cell.entries[2].insert(0,"0")                     # k
    _sub_cell.entries[3].insert(0,"1000000")               # Thickness (nm) — semi-infinite
    _sub_cell.entries[4].insert(0,"2.33")                  # Density (g/cm³)
    _sub_cell.entries[5].insert(0,"0.1")                   # Roughness (nm)
    orphan_layers.append(_sub_cell); subroutines.append(_sub_cell)
    mark_as_unmodified()
    _root.mainloop()
