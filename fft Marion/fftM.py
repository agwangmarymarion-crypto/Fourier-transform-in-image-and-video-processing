"""Fourier Image Editor: frequency-domain image filtering with a small Tk UI.

Requirements: Python 3.10+, Pillow, NumPy
Run: python fourier_image_editor.py
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import numpy as np
from PIL import Image, ImageTk


class FourierImageEditor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Fourier Image Editor")
        self.root.geometry("1000x680")
        self.original: Image.Image | None = None
        self.preview_photo = None
        self.spectrum_photo = None
        self.result: Image.Image | None = None
        self.radius = tk.DoubleVar(value=0.22)
        self.mode = tk.StringVar(value="Low-pass")
        self._build_ui()

    def _build_ui(self) -> None:
        bar = ttk.Frame(self.root, padding=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="Open image", command=self.open_image).pack(side="left")
        ttk.Button(bar, text="Save result", command=self.save_result).pack(side="left", padx=(8, 18))
        ttk.Label(bar, text="Filter:").pack(side="left")
        selector = ttk.Combobox(bar, textvariable=self.mode, values=("Low-pass", "High-pass"), state="readonly", width=12)
        selector.pack(side="left", padx=6)
        selector.bind("<<ComboboxSelected>>", lambda _event: self.apply_filter())
        ttk.Label(bar, text="Cutoff:").pack(side="left", padx=(12, 4))
        scale = ttk.Scale(bar, from_=0.02, to=0.75, variable=self.radius, command=lambda _value: self.apply_filter())
        scale.pack(side="left", fill="x", expand=True, padx=6)
        self.cutoff_label = ttk.Label(bar, text="0.22")
        self.cutoff_label.pack(side="left", padx=6)

        panes = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        panes.pack(fill="both", expand=True)
        panes.columnconfigure((0, 1), weight=1)
        panes.rowconfigure(0, weight=1)
        self.image_panel = self._panel(panes, "Filtered image", 0)
        self.spectrum_panel = self._panel(panes, "Fourier magnitude spectrum", 1)
        self.status = ttk.Label(self.root, text="Open an image to begin.", anchor="w", padding=(10, 4))
        self.status.pack(fill="x")

    def _panel(self, parent: ttk.Frame, title: str, column: int) -> ttk.Label:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=0, column=column, sticky="nsew", padx=(0, 5) if column == 0 else (5, 0))
        label = ttk.Label(frame, text="No image loaded", anchor="center")
        label.pack(fill="both", expand=True)
        return label

    def open_image(self) -> None:
        path = filedialog.askopenfilename(title="Choose an image", filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"), ("All files", "*.*")])
        if not path:
            return
        try:
            with Image.open(path) as img:
                self.original = img.convert("RGB")
            self.root.title(f"Fourier Image Editor — {Path(path).name}")
            self.apply_filter()
        except Exception as exc:
            messagebox.showerror("Could not open image", str(exc))

    def apply_filter(self, *_args) -> None:
        if self.original is None:
            return
        cutoff = float(self.radius.get())
        self.cutoff_label.configure(text=f"{cutoff:.2f}")
        # Resize for responsive editing, retaining the full-size original for final export.
        working = self.original.copy()
        working.thumbnail((900, 700), Image.Resampling.LANCZOS)
        rgb = np.asarray(working, dtype=np.float32)
        h, w, _ = rgb.shape
        fy = np.fft.fftshift(np.fft.fftfreq(h))
        fx = np.fft.fftshift(np.fft.fftfreq(w))
        yy, xx = np.meshgrid(fy, fx, indexing="ij")
        distance = np.sqrt(xx * xx + yy * yy)
        mask = distance <= cutoff
        if self.mode.get() == "High-pass":
            mask = ~mask

        filtered = np.empty_like(rgb)
        spectra = []
        for channel in range(3):
            spectrum = np.fft.fftshift(np.fft.fft2(rgb[:, :, channel]))
            spectra.append(np.log1p(np.abs(spectrum)))
            edited = np.fft.ifft2(np.fft.ifftshift(spectrum * mask)).real
            filtered[:, :, channel] = edited
        out = np.clip(filtered, 0, 255).astype(np.uint8)
        self.result = Image.fromarray(out, "RGB")
        spectrum_view = np.mean(spectra, axis=0)
        spectrum_view = (255 * spectrum_view / max(float(spectrum_view.max()), 1e-9)).astype(np.uint8)
        self._show(self.image_panel, self.result, "preview_photo")
        self._show(self.spectrum_panel, Image.fromarray(spectrum_view, "L").convert("RGB"), "spectrum_photo")
        self.status.configure(text=f"{self.original.width} × {self.original.height} px  |  {self.mode.get()} filter  |  cutoff {cutoff:.2f} cycles/pixel")

    def _show(self, label: ttk.Label, image: Image.Image, attribute: str) -> None:
        display = image.copy()
        display.thumbnail((700, 550), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(display)
        setattr(self, attribute, photo)
        label.configure(image=photo, text="")

    def save_result(self) -> None:
        if self.original is None or self.result is None:
            messagebox.showinfo("No result", "Open an image first.")
            return
        # Apply same frequency operation to original resolution for export.
        rgb = np.asarray(self.original, dtype=np.float32)
        h, w, _ = rgb.shape
        fy = np.fft.fftshift(np.fft.fftfreq(h))
        fx = np.fft.fftshift(np.fft.fftfreq(w))
        yy, xx = np.meshgrid(fy, fx, indexing="ij")
        mask = np.sqrt(xx * xx + yy * yy) <= float(self.radius.get())
        if self.mode.get() == "High-pass":
            mask = ~mask
        filtered = np.empty_like(rgb)
        for channel in range(3):
            spectrum = np.fft.fftshift(np.fft.fft2(rgb[:, :, channel]))
            filtered[:, :, channel] = np.fft.ifft2(np.fft.ifftshift(spectrum * mask)).real
        full_result = Image.fromarray(np.clip(filtered, 0, 255).astype(np.uint8), "RGB")
        path = filedialog.asksaveasfilename(title="Save filtered image", defaultextension=".png", filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg"), ("TIFF image", "*.tif")])
        if not path:
            return
        try:
            full_result.save(path)
            self.status.configure(text=f"Saved {Path(path).name} at {w} × {h} px")
        except Exception as exc:
            messagebox.showerror("Could not save image", str(exc))


def main() -> None:
    root = tk.Tk()
    FourierImageEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
