# -*- coding: utf-8 -*-
"""任务输入弹窗 - 友好的多任务添加界面"""

import tkinter as tk
from tkinter import ttk, messagebox

from ..constants import HAS_CTK
if HAS_CTK:
    import customtkinter as ctk


class TaskInputDialog:
    """多任务输入弹窗
    
    用户可以逐条添加关键词或博主URL，列表式管理，比逗号分隔更友好。
    """
    
    def __init__(self, parent, task_type="keyword", default_max_notes=30, initial_items=None):
        """
        Args:
            parent: 父窗口
            task_type: keyword / blogger / hot
            default_max_notes: 默认每个任务的最大笔记数
            initial_items: 预填充的列表
        """
        self.result = None  # 用户确认后的结果: list of (target, max_notes) 或 None
        self.task_type = task_type
        
        # 创建弹窗
        self.dialog = tk.Toplevel(parent)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 标题和大小
        type_titles = {
            "keyword": "添加搜索关键词",
            "blogger": "添加博主主页",
            "hot": "添加热门分类",
        }
        self.dialog.title(type_titles.get(task_type, "添加任务"))
        self.dialog.geometry("550x500")
        self.dialog.resizable(True, True)
        self.dialog.configure(bg="#f5f5f5")
        
        # 居中显示
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 550) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        self._build_ui(task_type, default_max_notes, initial_items)
        
        # ESC关闭
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    def _build_ui(self, task_type, default_max_notes, initial_items):
        """构建界面"""
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === 提示文字 ===
        type_hints = {
            "keyword": "输入搜索关键词，每行一个，或在输入框中输入后点击「添加」",
            "blogger": "输入博主主页URL，每行一个（如 https://www.xiaohongshu.com/user/profile/xxx）",
            "hot": "选择热门分类",
        }
        hint_text = type_hints.get(task_type, "输入任务目标")
        tk.Label(main_frame, text=hint_text, fg="#666", 
                font=('Microsoft YaHei UI', 12), wraplength=500, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))
        
        # === 输入区 ===
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 8))
        
        if task_type == "hot":
            # 热门分类用下拉框
            tk.Label(input_frame, text="分类:", font=('Microsoft YaHei UI', 14)).pack(side=tk.LEFT)
            self.input_var = tk.StringVar(value="综合")
            ttk.Combobox(input_frame, textvariable=self.input_var,
                        values=["综合", "美食", "穿搭", "美妆", "旅行", "家居", "数码"],
                        width=15, state="readonly", font=('Microsoft YaHei UI', 14)).pack(side=tk.LEFT, padx=(5, 10))
        else:
            # 关键词/博主URL用输入框
            placeholder = "输入关键词..." if task_type == "keyword" else "输入博主URL..."
            self.input_var = tk.StringVar()
            self.input_entry = tk.Entry(input_frame, textvariable=self.input_var, width=35, 
                                        font=('Microsoft YaHei UI', 14))
            self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            self.input_entry.bind('<Return>', lambda e: self._add_item())
            self.input_entry.focus_set()
        
        ttk.Button(input_frame, text="➕ 添加", command=self._add_item, width=8).pack(side=tk.LEFT)
        
        # === 全局笔记数量 ===
        notes_frame = ttk.Frame(main_frame)
        notes_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(notes_frame, text="每个任务最多笔记:", font=('Microsoft YaHei UI', 14)).pack(side=tk.LEFT)
        self.max_notes_var = tk.StringVar(value=str(default_max_notes))
        tk.Spinbox(notes_frame, from_=1, to=500, textvariable=self.max_notes_var, width=6,
                  font=('Microsoft YaHei UI', 14)).pack(side=tk.LEFT, padx=(8, 0))
        
        # === 任务列表 ===
        list_frame = ttk.LabelFrame(main_frame, text=f" 任务列表 (0项) ", padding="8")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.list_frame_widget = list_frame
        
        # Listbox + 滚动条
        list_inner = ttk.Frame(list_frame)
        list_inner.pack(fill=tk.BOTH, expand=True)
        
        self.task_listbox = tk.Listbox(list_inner, font=('Microsoft YaHei UI', 13), 
                                        selectmode=tk.EXTENDED, bg="#ffffff",
                                        activestyle="dotbox", height=10)
        scrollbar = ttk.Scrollbar(list_inner, orient=tk.VERTICAL, command=self.task_listbox.yview)
        self.task_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.task_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 列表操作按钮
        list_btn_row = ttk.Frame(list_frame)
        list_btn_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(list_btn_row, text="🗑 删除选中", command=self._remove_selected, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(list_btn_row, text="🧹 清空列表", command=self._clear_all, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(list_btn_row, text="📋 批量粘贴", command=self._paste_batch, width=12).pack(side=tk.RIGHT)
        
        # === 底部按钮 ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        if HAS_CTK:
            ctk.CTkButton(btn_frame, text="✅ 确认开始", command=self._on_confirm,
                         width=130, height=38, corner_radius=8,
                         fg_color="#22c55e", hover_color="#16a34a",
                         font=('Microsoft YaHei UI', 14, 'bold')).pack(side=tk.RIGHT, padx=(8, 0))
            ctk.CTkButton(btn_frame, text="取消", command=self._on_cancel,
                         width=80, height=38, corner_radius=8,
                         fg_color="#94a3b8", hover_color="#64748b",
                         font=('Microsoft YaHei UI', 14)).pack(side=tk.RIGHT)
        else:
            ttk.Button(btn_frame, text="✅ 确认开始", command=self._on_confirm, width=14).pack(side=tk.RIGHT, padx=(8, 0))
            ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=8).pack(side=tk.RIGHT)
        
        # Delete键删除选中
        self.task_listbox.bind('<Delete>', lambda e: self._remove_selected())
        
        # 预填充
        if initial_items:
            for item in initial_items:
                if item.strip():
                    self.task_listbox.insert(tk.END, item.strip())
            self._update_count()
    
    def _add_item(self):
        """添加一项"""
        text = self.input_var.get().strip()
        if not text:
            return
        
        # 检查重复
        existing = list(self.task_listbox.get(0, tk.END))
        if text in existing:
            messagebox.showinfo("提示", f"「{text}」已在列表中", parent=self.dialog)
            return
        
        self.task_listbox.insert(tk.END, text)
        self.input_var.set("")
        self._update_count()
        
        # 自动滚动到底部
        self.task_listbox.see(tk.END)
        
        # 聚焦回输入框
        if hasattr(self, 'input_entry'):
            self.input_entry.focus_set()
    
    def _remove_selected(self):
        """删除选中项"""
        selected = list(self.task_listbox.curselection())
        if not selected:
            return
        for idx in reversed(selected):
            self.task_listbox.delete(idx)
        self._update_count()
    
    def _clear_all(self):
        """清空列表"""
        if self.task_listbox.size() == 0:
            return
        if messagebox.askyesno("确认", "确定要清空所有任务？", parent=self.dialog):
            self.task_listbox.delete(0, tk.END)
            self._update_count()
    
    def _paste_batch(self):
        """批量粘贴（从剪贴板读取，每行一个）"""
        try:
            clipboard = self.dialog.clipboard_get()
            if not clipboard:
                messagebox.showinfo("提示", "剪贴板为空", parent=self.dialog)
                return
            
            existing = set(self.task_listbox.get(0, tk.END))
            added = 0
            
            # 按行分割，去掉空行
            for line in clipboard.strip().split('\n'):
                item = line.strip()
                if item and item not in existing:
                    self.task_listbox.insert(tk.END, item)
                    existing.add(item)
                    added += 1
            
            self._update_count()
            
            if added > 0:
                messagebox.showinfo("完成", f"已从剪贴板添加 {added} 项", parent=self.dialog)
            else:
                messagebox.showinfo("提示", "没有新内容可添加（可能重复或为空）", parent=self.dialog)
                
        except tk.TclError:
            messagebox.showinfo("提示", "剪贴板中没有文本内容", parent=self.dialog)
    
    def _update_count(self):
        """更新数量显示"""
        count = self.task_listbox.size()
        self.list_frame_widget.config(text=f" 任务列表 ({count}项) ")
    
    def _on_confirm(self):
        """确认"""
        items = list(self.task_listbox.get(0, tk.END))
        if not items:
            messagebox.showwarning("提示", "请至少添加一个任务", parent=self.dialog)
            return
        
        try:
            max_notes = int(self.max_notes_var.get())
        except ValueError:
            max_notes = 30
        
        self.result = [(item, max_notes) for item in items]
        self.dialog.destroy()
    
    def _on_cancel(self):
        """取消"""
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        """显示弹窗并等待结果
        
        Returns:
            list of (target, max_notes) 或 None（取消时）
        """
        self.dialog.wait_window()
        return self.result
