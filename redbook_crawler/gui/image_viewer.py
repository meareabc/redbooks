# -*- coding: utf-8 -*-
"""图片查看器弹窗"""

import os
import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class ImageViewer:
    """图片查看器弹窗"""
    
    def __init__(self, parent, image_paths, start_index=0):
        self.parent = parent
        self.image_paths = [p for p in image_paths if p and os.path.exists(p)]
        self.current_index = start_index
        
        if not self.image_paths or not HAS_PIL:
            return
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"图片查看器 - {start_index + 1}/{len(self.image_paths)}")
        self.window.geometry("800x600")
        self.window.configure(bg="#1e1e1e")
        
        # 工具栏
        toolbar = tk.Frame(self.window, bg="#2d2d2d", height=40)
        toolbar.pack(fill=tk.X)
        
        tk.Button(toolbar, text="◀ 上一张", command=self._prev, 
                 bg="#3b82f6", fg="white", font=('Microsoft YaHei UI', 12),
                 borderwidth=0, padx=10).pack(side=tk.LEFT, padx=5, pady=5)
        
        self.title_label = tk.Label(toolbar, text="", fg="white", bg="#2d2d2d",
                                    font=('Microsoft YaHei UI', 12))
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(toolbar, text="下一张 ▶", command=self._next, 
                 bg="#3b82f6", fg="white", font=('Microsoft YaHei UI', 12),
                 borderwidth=0, padx=10).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 图片显示区
        self.canvas = tk.Canvas(self.window, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绑定键盘
        self.window.bind('<Left>', lambda e: self._prev())
        self.window.bind('<Right>', lambda e: self._next())
        self.window.bind('<Escape>', lambda e: self.window.destroy())
        self.window.bind('<Configure>', lambda e: self._show_image())
        
        self.current_photo = None
        self._show_image()
    
    def _show_image(self):
        """显示当前图片"""
        if not self.image_paths:
            return
        
        path = self.image_paths[self.current_index]
        self.title_label.config(text=f"{self.current_index + 1}/{len(self.image_paths)} - {os.path.basename(path)}")
        self.window.title(f"图片查看器 - {self.current_index + 1}/{len(self.image_paths)}")
        
        try:
            img = Image.open(path)
            
            # 适应窗口大小
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            
            if canvas_w <= 1 or canvas_h <= 1:
                canvas_w = 800
                canvas_h = 550
            
            img_w, img_h = img.size
            ratio = min(canvas_w / img_w, canvas_h / img_h, 1.0)
            new_w = int(img_w * ratio)
            new_h = int(img_h * ratio)
            
            img = img.resize((new_w, new_h), Image.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(img)
            
            self.canvas.delete("all")
            x = canvas_w // 2
            y = canvas_h // 2
            self.canvas.create_image(x, y, image=self.current_photo, anchor=tk.CENTER)
            
        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text=f"无法加载图片\n{e}", 
                                   fill="white", font=('Microsoft YaHei UI', 14))
    
    def _prev(self):
        """上一张"""
        if self.current_index > 0:
            self.current_index -= 1
            self._show_image()
    
    def _next(self):
        """下一张"""
        if self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self._show_image()
