# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import os
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import colors, cm

class ImageAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Analysis （512 tones/Heatmap & CSV）")
        self.pil_img = None          # PIL Image (RGB)
        self.img_array = None        # numpy array (H, W, 3)
        self.tk_img = None           # ImageTk.PhotoImage（Canvas表示用参照を保持）
        self.img_on_canvas = None    # Canvas上の画像ID
        self.rect_id = None          # 矩形ID
        self.current_path = None     # 読み込んだ画像のパス（CSV初期ファイル名のため）

        # コマンド
        top = ttk.Frame(root, padding=(8, 8, 8, 4))
        top.pack(side=tk.TOP, fill=tk.X)

        self.btn_load = ttk.Button(top, text="Load", command=self.load_image)
        self.btn_load.pack(side=tk.LEFT, padx=(0, 8))

        # X, Y, width, height
        ttk.Label(top, text="X").pack(side=tk.LEFT)
        self.entry_x = ttk.Entry(top, width=6)
        self.entry_x.insert(0, "0")
        self.entry_x.pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(top, text="Y").pack(side=tk.LEFT)
        self.entry_y = ttk.Entry(top, width=6)
        self.entry_y.insert(0, "0")
        self.entry_y.pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(top, text="Width").pack(side=tk.LEFT)
        self.entry_w = ttk.Entry(top, width=6)
        self.entry_w.insert(0, "100")
        self.entry_w.pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(top, text="Height").pack(side=tk.LEFT)
        self.entry_h = ttk.Entry(top, width=6)
        self.entry_h.insert(0, "100")
        self.entry_h.pack(side=tk.LEFT, padx=(2, 8))

        self.btn_confirm = ttk.Button(top, text="Confirm", command=self.confirm_roi)
        self.btn_confirm.pack(side=tk.LEFT, padx=(8, 8))

        self.btn_run = ttk.Button(top, text="Run", command=self.run_analysis)
        self.btn_run.pack(side=tk.LEFT, padx=(0, 8))

        # Display
        canvas_frame = ttk.Frame(root)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        self.vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        self.canvas = tk.Canvas(canvas_frame, bg="#333333",
                                xscrollcommand=self.hbar.set,
                                yscrollcommand=self.vbar.set,
                                highlightthickness=0)

        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")

        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", self.canvas_click_set_origin)

    # Loading
    def load_image(self):
        path = filedialog.askopenfilename(
            title="Select image files",
            filetypes=[("image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff"),
                       ("All files", "*.*")]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot Open：\n{e}")
            return

        self.pil_img = img
        self.current_path = path
        self.img_array = np.array(img, dtype=np.uint8)

        # キャンバスに描画
        self.tk_img = ImageTk.PhotoImage(self.pil_img)
        self.canvas.delete("all")
        self.img_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.rect_id = None

        # キャンバスサイズ・スクロール領域を画像サイズに
        w, h = img.size
        self.canvas.config(scrollregion=(0, 0, w, h), width=min(1000, w), height=min(700, h))

        # 既定のROIを画像内に収める
        self.entry_x.delete(0, tk.END); self.entry_x.insert(0, "0")
        self.entry_y.delete(0, tk.END); self.entry_y.insert(0, "0")
        self.entry_w.delete(0, tk.END); self.entry_w.insert(0, str(min(256, w)))
        self.entry_h.delete(0, tk.END); self.entry_h.insert(0, str(min(256, h)))

    def canvas_click_set_origin(self, event):
        if self.img_array is None:
            return
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        self.entry_x.delete(0, tk.END); self.entry_x.insert(0, str(x))
        self.entry_y.delete(0, tk.END); self.entry_y.insert(0, str(y))
        self.confirm_roi()

    def confirm_roi(self):
        if self.img_array is None:
            messagebox.showwarning("Caution", "先に画像を読み込んでください。")
            return
        try:
            x = int(self.entry_x.get())
            y = int(self.entry_y.get())
            w = int(self.entry_w.get())
            h = int(self.entry_h.get())
        except ValueError:
            messagebox.showerror("Error", "X, Y, 幅, 高さは整数で入力してください。")
            return

        H, W = self.img_array.shape[:2]

        x = max(0, min(x, W - 1))
        y = max(0, min(y, H - 1))
        w = max(1, w)
        h = max(1, h)
        if x + w > W: w = W - x
        if y + h > H: h = H - y

        self.entry_x.delete(0, tk.END); self.entry_x.insert(0, str(x))
        self.entry_y.delete(0, tk.END); self.entry_y.insert(0, str(y))
        self.entry_w.delete(0, tk.END); self.entry_w.insert(0, str(w))
        self.entry_h.delete(0, tk.END); self.entry_h.insert(0, str(h))

        if self.rect_id is None:
            self.rect_id = self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline="yellow", width=2
            )
        else:
            self.canvas.coords(self.rect_id, x, y, x + w, y + h)

    # 512階調解析 + ヒートマップ + CSV保存
    def run_analysis(self):
        if self.img_array is None:
            messagebox.showwarning("Caution", "先に画像を読み込んでください。")
            return
        try:
            x = int(self.entry_x.get())
            y = int(self.entry_y.get())
            w = int(self.entry_w.get())
            h = int(self.entry_h.get())
        except ValueError:
            messagebox.showerror("Error", "X, Y, 幅, 高さは整数で入力してください。")
            return

        H, W = self.img_array.shape[:2]
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > W or y + h > H:
            messagebox.showerror("Error", "解析範囲が画像サイズを超えています。")
            return

        roi = self.img_array[y:y+h, x:x+w, :]  # (h, w, 3)

        gray = (0.299 * roi[..., 0] + 0.587 * roi[..., 1] + 0.114 * roi[..., 2]).astype(np.float64)

        # 512階調
        quant512 = np.rint(gray / 255.0 * 511.0).astype(np.int32)
        quant512 = np.clip(quant512, 0, 511)

        # CSV保存
        initial_name = "intensity_map.csv"
        if self.current_path:
            base = os.path.splitext(os.path.basename(self.current_path))[0]
            initial_name = f"{base}_roi_{x}_{y}_{w}x{h}_512levels.csv"

        csv_path = filedialog.asksaveasfilename(
            title="Save CSV file",
            defaultextension=".csv",
            initialfile=initial_name,
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")]
        )
        if csv_path:
            try:
                np.savetxt(csv_path, quant512, fmt="%d", delimiter=",")
            except Exception as e:
                messagebox.showerror("Error", f"CSVを書き出せませんでした：\n{e}")
                return

        self.show_heatmap_window(quant512)

    def show_heatmap_window(self, quantized_int):

        base_cmap = cm.get_cmap("viridis", 512)
        boundaries = np.arange(-0.5, 511.5 + 1, 1)
        norm = colors.BoundaryNorm(boundaries, base_cmap.N)

        win = tk.Toplevel(self.root)
        #win.title("Heatmap")

        fig = Figure(figsize=(6, 5), dpi=100)
        ax = fig.add_subplot(111)
        im = ax.imshow(quantized_int, cmap=base_cmap, norm=norm, origin="upper")
        #ax.set_title("Title")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Level (0–511)")

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        win.geometry("800x700+100+50")

def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    app = ImageAnalyzerApp(root)
    root.geometry("1200x800")
    root.mainloop()

if __name__ == "__main__":
    main()
