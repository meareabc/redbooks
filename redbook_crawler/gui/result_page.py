# -*- coding: utf-8 -*-
"""爬取结果页面 - 结果展示、详情面板、批次管理"""

import os
import json
import glob
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from datetime import datetime
import pandas as pd

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .image_viewer import ImageViewer

def create_result_page(app, parent):
    """创建爬取结果页面 (CustomTkinter)"""
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    
    # === 工具栏 ===
    toolbar = ctk.CTkFrame(parent)
    toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
    
    # 数据源选项
    ctk.CTkLabel(toolbar, text="数据源:", font=ctk.CTkFont(size=14, weight="bold")).pack(side=tk.LEFT, padx=(15, 5), pady=10)
    app.result_source_var = tk.StringVar(value="current")
    source_combo = ctk.CTkOptionMenu(toolbar, variable=app.result_source_var, values=["current", "database", "folder"], width=120)
    source_combo.pack(side=tk.LEFT, padx=(0, 15), pady=10)
    app.result_source_var.trace_add("write", lambda *a: _on_source_change(app))
    
    ctk.CTkButton(toolbar, text="🔄 刷新", command=lambda: _refresh_results(app), width=80).pack(side=tk.LEFT, padx=(0, 5), pady=10)
    ctk.CTkButton(toolbar, text="📥 导出Excel", command=lambda: _export_results(app), width=100).pack(side=tk.LEFT, padx=(0, 5), pady=10)
    ctk.CTkButton(toolbar, text="🗑 删除选中", command=lambda: _delete_selected(app), width=100, fg_color="#ef4444", hover_color="#dc2626").pack(side=tk.LEFT, pady=10, padx=(0, 5))
    ctk.CTkButton(toolbar, text="🧹 按任务删除", command=lambda: _show_task_delete_dialog(app), width=110, fg_color="#f59e0b", hover_color="#d97706").pack(side=tk.LEFT, pady=10)
    
    # 搜索过滤
    app.result_filter_var = tk.StringVar()
    filter_entry = ctk.CTkEntry(toolbar, textvariable=app.result_filter_var, width=150, placeholder_text="搜索标题/作者...")
    filter_entry.pack(side=tk.RIGHT, padx=(5, 15), pady=10)
    filter_entry.bind('<Return>', lambda e: _refresh_results(app))
    ctk.CTkLabel(toolbar, text="🔍", font=ctk.CTkFont(size=16)).pack(side=tk.RIGHT)
    
    # === 主内容区域 ===
    main_split = ctk.CTkFrame(parent, fg_color="transparent")
    main_split.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
    main_split.grid_rowconfigure(0, weight=1)
    main_split.grid_columnconfigure(0, weight=5) # 5/8 width for table
    main_split.grid_columnconfigure(1, weight=3) # 3/8 width for details
    
    # --- 左侧: 结果表格 ---
    left_frame = ctk.CTkFrame(main_split)
    left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    
    columns = ("序号", "标题", "作者", "类型", "点赞", "收藏", "评论")
    app.result_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=20)
    
    col_configs = {
        "序号": 50, "标题": 250, "作者": 100, "类型": 60, 
        "点赞": 70, "收藏": 70, "评论": 70
    }
    for col in columns:
        app.result_tree.heading(col, text=col, command=lambda c=col: _sort_column(app, c))
        app.result_tree.column(col, width=col_configs.get(col, 80), anchor=tk.CENTER if col != "标题" else tk.W)
    
    result_scroll = ctk.CTkScrollbar(left_frame, orientation="vertical", command=app.result_tree.yview)
    app.result_tree.configure(yscrollcommand=result_scroll.set)
    
    app.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0), pady=2)
    result_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=2)
    
    app.result_tree.bind('<<TreeviewSelect>>', lambda e: _on_result_select(app))
    
    # 右键菜单
    app.result_menu = tk.Menu(app.result_tree, tearoff=0)
    app.result_menu.add_command(label="复制标题", command=lambda: _copy_field(app, 'title'))
    app.result_menu.add_command(label="复制链接", command=lambda: _copy_field(app, 'note_link'))
    app.result_menu.add_command(label="在浏览器中打开", command=lambda: _open_in_browser(app))
    app.result_menu.add_separator()
    app.result_menu.add_command(label="打开图片文件夹", command=lambda: _open_image_folder(app))
    app.result_menu.add_command(label="删除选中", command=lambda: _delete_selected(app))
    
    app.result_tree.bind('<Button-3>', lambda e: _show_context_menu(app, e))
    
    # --- 右侧: 详情面板 ---
    right_frame = ctk.CTkFrame(main_split)
    right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
    
    ctk.CTkLabel(right_frame, text="笔记详情", font=ctk.CTkFont(size=16, weight="bold"), text_color="#3b82f6").pack(pady=(15, 10))
    
    app.detail_text = ctk.CTkTextbox(right_frame, wrap=tk.WORD, font=ctk.CTkFont(size=14))
    app.detail_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
    app.detail_text.configure(state="disabled")
    
    # 图片预览区
    preview_frame = ctk.CTkFrame(right_frame, height=180)
    preview_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
    preview_frame.pack_propagate(False)
    
    ctk.CTkLabel(preview_frame, text="图片预览 (点击放大)", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
    
    # Canvas for preview - handle appearance mode for background
    bg_color = "#ebebeb" if ctk.get_appearance_mode() == "Light" else "#242424"
    app.preview_canvas = tk.Canvas(preview_frame, height=130, bg=bg_color, highlightthickness=0)
    app.preview_canvas.pack(fill=tk.X, padx=10, pady=(0, 10))
    app.preview_canvas.bind('<Button-1>', lambda e: _on_preview_click(app, e))
    
    app._preview_photos = []
    app._preview_paths = []
    
    # 结果数量标签
    app.result_count_var = tk.StringVar(value="共 0 条结果")
    ctk.CTkLabel(parent, textvariable=app.result_count_var, font=ctk.CTkFont(size=12)).grid(row=2, column=0, sticky="w", padx=15, pady=(0, 10))


def populate_results(app, data_list=None):
    """填充结果表格"""
    for item in app.result_tree.get_children():
        app.result_tree.delete(item)
    
    data = data_list if data_list is not None else app.all_notes_data
    filter_text = app.result_filter_var.get().strip().lower() if hasattr(app, 'result_filter_var') else ""
    
    count = 0
    for i, note in enumerate(data):
        title = note.get('title', '')
        author = note.get('author', '')
        
        # 搜索过滤
        if filter_text:
            if filter_text not in title.lower() and filter_text not in author.lower():
                continue
        
        count += 1
        app.result_tree.insert("", tk.END, iid=str(i), values=(
            count,
            title[:50],
            author,
            note.get('note_type', '图文'),
            note.get('like_count', 0),
            note.get('collect_count', 0),
            note.get('comment_count', 0),
        ))
    
    app.result_count_var.set(f"共 {count} 条结果")


def _on_result_select(app):
    """选中结果行时显示详情"""
    selected = app.result_tree.selection()
    if not selected:
        return
    
    idx = int(selected[0])
    if idx >= len(app.all_notes_data):
        return
    
    note = app.all_notes_data[idx]
    
    # 更新详情文本
    app.detail_text.configure(state="normal")
    app.detail_text.delete('1.0', tk.END)
    
    lines = [
        f"📌 标题: {note.get('title', '')}",
        f"👤 作者: {note.get('author', '')}",
        f"📅 时间: {note.get('publish_time', '')}",
        f"📍 IP: {note.get('ip_region', '')}",
        f"",
        f"❤️ 点赞: {note.get('like_count', 0)}  ⭐ 收藏: {note.get('collect_count', 0)}  💬 评论: {note.get('comment_count', 0)}",
        f"📝 类型: {note.get('note_type', '')}",
        f"🔗 链接: {note.get('note_link', '')}",
        f"🆔 ID: {note.get('note_id', '')}",
        f"",
    ]
    
    content = note.get('content', '')
    if content:
        lines.append(f"📄 正文:")
        lines.append(content[:500])
        lines.append("")
    
    tags = note.get('tags', [])
    if tags:
        if isinstance(tags, list):
            lines.append(f"🏷️ 标签: {', '.join(tags)}")
        else:
            lines.append(f"🏷️ 标签: {tags}")
        lines.append("")
    
    comments = note.get('comments', [])
    if comments:
        if isinstance(comments, list):
            lines.append(f"💬 评论 ({len(comments)}条):")
            for c in comments[:10]:
                if isinstance(c, dict):
                    lines.append(f"  @{c.get('author', '匿名')}: {c.get('content', '')}")
                else:
                    lines.append(f"  {c}")
        elif isinstance(comments, str):
            lines.append(f"💬 评论:")
            lines.append(comments[:300])
    
    app.detail_text.insert('1.0', '\n'.join(lines))
    app.detail_text.configure(state="disabled")
    
    # 更新图片预览
    _update_preview(app, note)


def _update_preview(app, note):
    """更新图片预览"""
    app.preview_canvas.delete("all")
    app._preview_photos = []
    app._preview_paths = []
    
    if not HAS_PIL:
        return
    
    # 收集本地图片路径
    local_images = note.get('local_images', [])
    if isinstance(local_images, str):
        local_images = [p.strip() for p in local_images.split('|') if p.strip()]
    
    valid_paths = [p for p in local_images if p and os.path.exists(p)]
    
    if not valid_paths:
        app.preview_canvas.create_text(200, 75, text="无本地图片", fill="#999",
                                       font=('Microsoft YaHei UI', 12))
        return
    
    app._preview_paths = valid_paths
    
    # 显示缩略图
    x = 10
    for path in valid_paths[:8]:
        try:
            img = Image.open(path)
            img.thumbnail((130, 130))
            photo = ImageTk.PhotoImage(img)
            app._preview_photos.append(photo)
            
            app.preview_canvas.create_image(x, 10, image=photo, anchor=tk.NW)
            x += 140
        except Exception:
            continue


def _on_preview_click(app, event):
    """点击预览图片打开查看器"""
    if not app._preview_paths:
        return
    
    # 计算点击的是哪张图
    idx = event.x // 140
    if idx < len(app._preview_paths):
        ImageViewer(app.root, app._preview_paths, idx)


def _refresh_results(app):
    """刷新结果"""
    populate_results(app)


def _on_source_change(app):
    """数据源切换"""
    source = app.result_source_var.get()
    if source == "current":
        populate_results(app)
    elif source == "database":
        _load_from_database(app)
    elif source == "folder":
        _load_from_folder(app)


def _load_from_database(app):
    """从数据库加载"""
    try:
        import sqlite3
        conn = sqlite3.connect(app.config.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes ORDER BY crawl_time DESC LIMIT 500')
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for row in rows:
            note = dict(zip(columns, row))
            # 解析JSON字段
            for key in ['tags', 'image_urls', 'comments']:
                if key in note and isinstance(note[key], str):
                    try:
                        note[key] = json.loads(note[key])
                    except Exception:
                        pass
            data.append(note)
        
        app.all_notes_data = data
        populate_results(app)
    except Exception as e:
        messagebox.showerror("错误", f"加载数据库失败: {e}")


def _load_from_folder(app):
    """从文件夹加载"""
    folder = filedialog.askdirectory(title="选择数据文件夹")
    if not folder:
        return
    
    # 查找Excel文件
    files = glob.glob(os.path.join(folder, "*.xlsx"))
    if not files:
        messagebox.showinfo("提示", "文件夹中没有找到Excel文件")
        return
    
    try:
        df = pd.read_excel(files[0])
        app.all_notes_data = df.to_dict('records')
        populate_results(app)
    except Exception as e:
        messagebox.showerror("错误", f"加载失败: {e}")


def _sort_column(app, col):
    """排序列"""
    data = app.all_notes_data
    if not data:
        return
    
    col_key_map = {
        "标题": "title", "作者": "author", "类型": "note_type",
        "点赞": "like_count", "收藏": "collect_count", "评论": "comment_count"
    }
    
    key = col_key_map.get(col)
    if not key:
        return
    
    # 切换排序方向
    if not hasattr(app, '_sort_reverse'):
        app._sort_reverse = {}
    
    reverse = not app._sort_reverse.get(col, False)
    app._sort_reverse[col] = reverse
    
    try:
        app.all_notes_data.sort(key=lambda x: x.get(key, 0) if isinstance(x.get(key, 0), (int, float)) else str(x.get(key, '')),
                                 reverse=reverse)
        populate_results(app)
    except Exception:
        pass


def _copy_field(app, field):
    """复制字段到剪贴板"""
    selected = app.result_tree.selection()
    if not selected:
        return
    
    idx = int(selected[0])
    if idx < len(app.all_notes_data):
        value = str(app.all_notes_data[idx].get(field, ''))
        app.root.clipboard_clear()
        app.root.clipboard_append(value)


def _open_in_browser(app):
    """在浏览器中打开"""
    import webbrowser
    selected = app.result_tree.selection()
    if not selected:
        return
    
    idx = int(selected[0])
    if idx < len(app.all_notes_data):
        link = app.all_notes_data[idx].get('note_link', '')
        if link:
            webbrowser.open(link)


def _open_image_folder(app):
    """打开图片文件夹"""
    selected = app.result_tree.selection()
    if not selected:
        return
    
    idx = int(selected[0])
    if idx < len(app.all_notes_data):
        local_images = app.all_notes_data[idx].get('local_images', [])
        if isinstance(local_images, str):
            local_images = [p.strip() for p in local_images.split('|') if p.strip()]
        
        if local_images:
            folder = os.path.dirname(local_images[0])
            if os.path.exists(folder):
                os.startfile(folder)
                return
    
    messagebox.showinfo("提示", "没有找到本地图片文件夹")


def _show_context_menu(app, event):
    """显示右键菜单"""
    selected = app.result_tree.identify_row(event.y)
    if selected:
        app.result_tree.selection_set(selected)
        app.result_menu.post(event.x_root, event.y_root)


def _delete_selected(app):
    """删除选中的结果"""
    selected = app.result_tree.selection()
    if not selected:
        return
    
    if not messagebox.askyesno("确认", f"确定删除选中的 {len(selected)} 条结果？"):
        return
    
    indices = sorted([int(s) for s in selected], reverse=True)
    for idx in indices:
        if idx < len(app.all_notes_data):
            app.all_notes_data.pop(idx)
    
    populate_results(app)


def _show_task_delete_dialog(app):
    """弹出按任务删除历史记录的对话框"""
    keywords = app.db_mgr.get_all_task_keywords()
    if not keywords:
        messagebox.showinfo("提示", "数据库中暂无任何历史任务记录。")
        return
        
    dialog = ctk.CTkToplevel(app.root)
    dialog.title("按任务删除历史记录")
    dialog.geometry("400x500")
    dialog.transient(app.root)
    dialog.grab_set()
    
    # center dialog
    dialog.update_idletasks()
    x = app.root.winfo_x() + (app.root.winfo_width() - 400) // 2
    y = app.root.winfo_y() + (app.root.winfo_height() - 500) // 2
    dialog.geometry(f"+{x}+{y}")
    
    ctk.CTkLabel(dialog, text="选择要彻底删除历史记录的任务：\n(将同步删除数据库记录，下次可从头爬取)", 
                 font=ctk.CTkFont(size=14, weight="bold"), justify="left").pack(padx=20, pady=(20, 10), fill=tk.X)
                 
    scroll_frame = ctk.CTkScrollableFrame(dialog)
    scroll_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
    
    checkbox_vars = {}
    for kw in keywords:
        # Some URLs might be long, slice for display but keep original key
        display_kw = kw if len(kw) < 40 else kw[:37] + "..."
        var = tk.BooleanVar(value=False)
        checkbox_vars[kw] = var
        ctk.CTkCheckBox(scroll_frame, text=display_kw, variable=var).pack(anchor="w", pady=5)
        
    def _on_confirm():
        selected = [k for k, v in checkbox_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个任务。")
            return
            
        if messagebox.askyesno("确认", f"确定要彻底删除这 {len(selected)} 个任务的所有历史记录吗？\n删除后不可恢复！"):
            import glob, shutil, os
            success_count = 0
            for k in selected:
                if app.db_mgr.delete_task_history(k):
                    success_count += 1
                    # Try to clean up from active tasks queue as well
                    task = app.task_manager.find_task("keyword", k) or app.task_manager.find_task("blogger", k) or app.task_manager.find_task("hot", k)
                    if task:
                        app.task_manager.remove_task(task.task_id)
                        
                    # 彻底删除硬盘残留数据 (Excel和图片)
                    safe_k = k.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
                    for f in glob.glob(f"data/搜索结果_{safe_k}_*"):
                        try: os.remove(f)
                        except: pass
                    
                    for d in glob.glob(f"images/{safe_k}_*"):
                        try: shutil.rmtree(d)
                        except: pass
                        
                    short_id = k.rstrip('/').split('/')[-1].split('?')[0] if 'http' in k else ""
                    if short_id:
                        for d in glob.glob(f"images/博主_{short_id}"):
                            try: shutil.rmtree(d)
                            except: pass
                            
            messagebox.showinfo("完成", f"成功彻底清除了 {success_count} 个任务的历史记录及关联文件。")
            dialog.destroy()
            
            # Refresh if looking at database source
            if app.result_source_var.get() == "database":
                _load_from_database(app)
            else:
                # Optionally pop them from current view if it's "current" source
                if app.result_source_var.get() == "current":
                    app.all_notes_data = [n for n in app.all_notes_data if n.get('keyword') not in selected]
                    populate_results(app)
                    
            from .main_page import refresh_task_list
            refresh_task_list(app)
            
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill=tk.X, padx=20, pady=20)
    ctk.CTkButton(btn_frame, text="取消", fg_color="gray", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    ctk.CTkButton(btn_frame, text="✅ 确认删除", fg_color="#ef4444", hover_color="#dc2626", command=_on_confirm).pack(side=tk.RIGHT, padx=5)


def _export_results(app):
    """导出结果"""
    if not app.all_notes_data:
        messagebox.showinfo("提示", "没有数据可导出")
        return
    
    filepath = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv")]
    )
    
    if not filepath:
        return
    
    try:
        df = pd.DataFrame(app.all_notes_data)
        if filepath.endswith('.csv'):
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
        else:
            df.to_excel(filepath, index=False)
        messagebox.showinfo("成功", f"已导出到: {filepath}")
    except Exception as e:
        messagebox.showerror("错误", f"导出失败: {e}")
