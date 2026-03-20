# -*- coding: utf-8 -*-
"""搜索爬取页面 - 核心页面，支持多任务输入和美观的任务队列"""

import tkinter as tk
import customtkinter as ctk
from PIL import Image
from ..task_manager import TaskItem, STATUS_PENDING, STATUS_RUNNING, STATUS_PAUSED, STATUS_COMPLETED, STATUS_FAILED

def create_main_page(app, parent):
    """创建主页面 - 左侧配置，右侧任务队列"""
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=4) # Left panel width
    parent.grid_columnconfigure(1, weight=6) # Right panel width
    
    # === 左侧: 任务配置区 ===
    left_frame = ctk.CTkFrame(parent, fg_color="transparent")
    left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    left_frame.grid_columnconfigure(0, weight=1)
    
    # 模式选择
    mode_frame = ctk.CTkFrame(left_frame)
    mode_frame.pack(fill=tk.X, pady=(0, 10))
    
    ctk.CTkLabel(mode_frame, text="爬取模式", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
    
    app.crawl_type_var = tk.StringVar(value="keyword")
    mode_seg = ctk.CTkSegmentedButton(mode_frame, values=["关键词搜索", "博主主页", "热门榜单"],
                                     command=lambda v: _on_mode_change(app, v))
    mode_seg.set("关键词搜索")
    mode_seg.pack(fill=tk.X, padx=10, pady=(0, 15))
    
    # 目标输入区 (多行)
    input_frame = ctk.CTkFrame(left_frame)
    input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    app.input_label = ctk.CTkLabel(input_frame, text="输入关键词 (支持多行批量添加)", font=ctk.CTkFont(size=14, weight="bold"))
    app.input_label.pack(anchor="w", padx=10, pady=(10, 5))
    
    app.target_textbox = ctk.CTkTextbox(input_frame, height=100)
    app.target_textbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
    
    app.hot_combo = ctk.CTkOptionMenu(input_frame, values=["综合", "美食", "穿搭", "美妆", "旅行", "家居", "数码"])
    app.hot_combo.pack(fill=tk.X, padx=10, pady=(0, 10))
    app.hot_combo.pack_forget() # 默认隐藏
    
    # 基础配置
    config_frame = ctk.CTkFrame(left_frame)
    config_frame.pack(fill=tk.X, pady=(0, 10))
    
    row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
    row1.pack(fill=tk.X, padx=10, pady=10)
    
    ctk.CTkLabel(row1, text="最多笔记数:").pack(side=tk.LEFT)
    app.max_notes_var = tk.StringVar(value="30")
    ctk.CTkEntry(row1, textvariable=app.max_notes_var, width=60).pack(side=tk.LEFT, padx=(5, 15))
    
    ctk.CTkLabel(row1, text="速度模式:").pack(side=tk.LEFT)
    app.crawl_mode_var = tk.StringVar(value="standard")
    ctk.CTkOptionMenu(row1, variable=app.crawl_mode_var, values=["standard", "fast", "turbo"], width=100).pack(side=tk.LEFT, padx=(5, 0))
    
    # 高级筛选 (折叠/展开 可选，这里直接展示)
    filter_frame = ctk.CTkFrame(left_frame)
    filter_frame.pack(fill=tk.X, pady=(0, 10))
    
    row2 = ctk.CTkFrame(filter_frame, fg_color="transparent")
    row2.pack(fill=tk.X, padx=10, pady=10)
    
    ctk.CTkLabel(row2, text="点赞:").pack(side=tk.LEFT)
    app.min_likes_var = tk.StringVar(value="0")
    ctk.CTkEntry(row2, textvariable=app.min_likes_var, width=50).pack(side=tk.LEFT, padx=(5, 2))
    ctk.CTkLabel(row2, text="-").pack(side=tk.LEFT)
    app.max_likes_var = tk.StringVar(value="999999")
    ctk.CTkEntry(row2, textvariable=app.max_likes_var, width=60).pack(side=tk.LEFT, padx=(2, 10))
    
    ctk.CTkLabel(row2, text="类型:").pack(side=tk.LEFT)
    app.note_type_var = tk.StringVar(value="全部")
    ctk.CTkOptionMenu(row2, variable=app.note_type_var, values=["全部", "图文", "视频"], width=80).pack(side=tk.LEFT, padx=(5, 0))
    
    # 添加任务按钮
    add_btn = ctk.CTkButton(left_frame, text="添加到任务队列 ➔", font=ctk.CTkFont(size=16, weight="bold"),
                            height=40, command=lambda: _add_tasks_to_queue(app))
    add_btn.pack(fill=tk.X, pady=(0, 10))
    
    # === 右侧: 任务队列和状态区 ===
    right_frame = ctk.CTkFrame(parent, fg_color="transparent")
    right_frame.grid(row=0, column=1, sticky="nsew")
    right_frame.grid_rowconfigure(1, weight=1) # queue frame expands
    
    # 控制台
    ctrl_frame = ctk.CTkFrame(right_frame)
    ctrl_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    
    app.start_btn = ctk.CTkButton(ctrl_frame, text="▶ 开始爬取", fg_color="#22c55e", hover_color="#16a34a",
                                  font=ctk.CTkFont(size=14, weight="bold"), command=app._start_crawl)
    app.start_btn.pack(side=tk.LEFT, padx=10, pady=10)
    
    app.stop_btn = ctk.CTkButton(ctrl_frame, text="⏹ 停止", fg_color="#ef4444", hover_color="#dc2626",
                                 state="disabled", font=ctk.CTkFont(size=14, weight="bold"), command=app._stop_crawl)
    app.stop_btn.pack(side=tk.LEFT, padx=(0, 10), pady=10)
    
    ctk.CTkButton(ctrl_frame, text="清空队列", fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
                  command=lambda: _clear_all_tasks(app)).pack(side=tk.RIGHT, padx=10, pady=10)
                  
    app.task_summary_var = tk.StringVar(value="任务: 0")
    ctk.CTkLabel(ctrl_frame, textvariable=app.task_summary_var).pack(side=tk.RIGHT, padx=10)
    
    # 任务队列 (非常美观的卡片列表)
    queue_container = ctk.CTkFrame(right_frame)
    queue_container.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
    queue_container.grid_rowconfigure(1, weight=1)
    queue_container.grid_columnconfigure(0, weight=1)
    
    queue_header = ctk.CTkFrame(queue_container, fg_color=("gray85", "gray20"), corner_radius=0)
    queue_header.grid(row=0, column=0, sticky="ew")
    queue_header.grid_columnconfigure(1, weight=1) # ALLOW HEADER TO SHRINK
    
    # Adjust widths proportionally for CustomTkinter
    ctk.CTkLabel(queue_header, text="任务", width=60).grid(row=0, column=0, padx=5, pady=5)
    ctk.CTkLabel(queue_header, text="目标", width=160, anchor="w").grid(row=0, column=1, padx=5, pady=5, sticky="w")
    ctk.CTkLabel(queue_header, text="进度", width=120).grid(row=0, column=2, padx=5, pady=5)
    ctk.CTkLabel(queue_header, text="状态", width=60).grid(row=0, column=3, padx=5, pady=5)
    ctk.CTkLabel(queue_header, text="操作", width=40).grid(row=0, column=4, padx=5, pady=5)
    
    app.task_queue_frame = ctk.CTkScrollableFrame(queue_container, fg_color="transparent")
    app.task_queue_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
    
    app.task_widgets = {} # dict to hold widget references for updates
    
    # 运行状态 & 日志
    status_log_frame = ctk.CTkFrame(right_frame, height=220)
    status_log_frame.grid(row=2, column=0, sticky="ew")
    status_log_frame.grid_propagate(False)
    status_log_frame.grid_rowconfigure(1, weight=1)
    status_log_frame.grid_columnconfigure(0, weight=1)
    
    # Top bar of status
    status_bar = ctk.CTkFrame(status_log_frame, fg_color="transparent")
    status_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
    
    app.status_var = tk.StringVar(value="就绪")
    ctk.CTkLabel(status_bar, text="状态:").pack(side=tk.LEFT)
    ctk.CTkLabel(status_bar, textvariable=app.status_var, font=ctk.CTkFont(weight="bold"), text_color="#3b82f6").pack(side=tk.LEFT, padx=(5, 15))
    
    app.notes_var = tk.StringVar(value="0")
    ctk.CTkLabel(status_bar, text="笔记:").pack(side=tk.LEFT)
    ctk.CTkLabel(status_bar, textvariable=app.notes_var, font=ctk.CTkFont(weight="bold")).pack(side=tk.LEFT, padx=(2, 10))
    
    app.images_var = tk.StringVar(value="0")
    ctk.CTkLabel(status_bar, text="图片:").pack(side=tk.LEFT)
    ctk.CTkLabel(status_bar, textvariable=app.images_var, font=ctk.CTkFont(weight="bold")).pack(side=tk.LEFT, padx=(2, 10))
    
    app.videos_var = tk.StringVar(value="0")
    ctk.CTkLabel(status_bar, text="视频:").pack(side=tk.LEFT)
    ctk.CTkLabel(status_bar, textvariable=app.videos_var, font=ctk.CTkFont(weight="bold")).pack(side=tk.LEFT, padx=(2, 10))
    
    # Progressbar custom bindings
    app.total_progress = ctk.CTkProgressBar(status_bar, mode="determinate", width=120)
    app.total_progress.set(0)
    app.total_progress.pack(side=tk.RIGHT, pady=8)
    app.progress_label = ctk.CTkLabel(status_bar, text="0%")
    app.progress_label.pack(side=tk.RIGHT, padx=10)
    app.time_var = tk.StringVar(value="0s")
    ctk.CTkLabel(status_bar, textvariable=app.time_var).pack(side=tk.RIGHT, padx=(0, 10))
    
    # Logger TextBox CustomTkinter
    app.log_text = ctk.CTkTextbox(status_log_frame, font=ctk.CTkFont("Consolas", size=13))
    app.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
    app.log_text.configure(state="disabled")
    
    # 兼容原有的变量引用 (因为有些地方用到app.keyword_var直接取值)
    app.keyword_var = tk.StringVar(value="")
    app.blogger_url_var = tk.StringVar(value="")
    app.hot_category_var = tk.StringVar(value="综合")
    app.date_filter_var = tk.StringVar(value="全部")
    
    # 绑定初始数据
    refresh_task_list(app)


def _on_mode_change(app, mode_str):
    """切换爬取模式"""
    mode_map = {"关键词搜索": "keyword", "博主主页": "blogger", "热门榜单": "hot"}
    mode = mode_map.get(mode_str, "keyword")
    app.crawl_type_var.set(mode)
    
    if mode == "keyword":
        app.input_label.configure(text="输入关键词 (支持多行批量添加)")
        app.target_textbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        app.hot_combo.pack_forget()
    elif mode == "blogger":
        app.input_label.configure(text="输入博主主页URL (支持多行批量添加)")
        app.target_textbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        app.hot_combo.pack_forget()
    elif mode == "hot":
        app.input_label.configure(text="选择热门分类")
        app.target_textbox.pack_forget()
        app.hot_combo.pack(fill=tk.X, padx=10, pady=(0, 10))


def _add_tasks_to_queue(app):
    from tkinter import messagebox
    mode = app.crawl_type_var.get()
    
    try:
        max_notes = int(app.max_notes_var.get())
    except ValueError:
        max_notes = 30
        
    targets = []
    if mode in ["keyword", "blogger"]:
        text = app.target_textbox.get("1.0", tk.END).strip()
        if not text:
            return
        
        # 支持逗号、换行分隔
        lines = text.replace('，', ',').replace('\r', '\n').split('\n')
        for line in lines:
            if ',' in line:
                targets.extend([t.strip() for t in line.split(',') if t.strip()])
            elif line.strip():
                targets.append(line.strip())
                
        # 保存到兼容变量以便app.py也能读到
        if mode == "keyword":
            app.keyword_var.set(",".join(targets))
        else:
            app.blogger_url_var.set("\n".join(targets))
            
    elif mode == "hot":
        targets.append(app.hot_combo.get())
        app.hot_category_var.set(targets[0])
        
    added = 0
    for t in targets:
        task = app.task_manager.add_task(mode, t, max_notes)
        if task:
            added += 1
            
    if added > 0:
        if mode in ["keyword", "blogger"]:
            app.target_textbox.delete("1.0", tk.END) # Clear after add
        refresh_task_list(app)


def refresh_task_list(app):
    """刷新任务队列显示，生成漂亮的卡片列表"""
    # 清空旧组件
    for widget in app.task_queue_frame.winfo_children():
        widget.destroy()
        
    app.task_widgets = {}
    
    for i, task in enumerate(app.task_manager.tasks):
        row = ctk.CTkFrame(app.task_queue_frame, fg_color=("gray95", "gray15"), corner_radius=6)
        row.pack(fill=tk.X, pady=2, padx=2)
        
        type_map = {"keyword": "关键词", "blogger": "博主", "hot": "热门"}
        t_type = type_map.get(task.task_type, task.task_type)
        
        # 卡片内部网格布局
        row.grid_columnconfigure(1, weight=1) # target needs more space
        
        ctk.CTkLabel(row, text=t_type, width=60).grid(row=0, column=0, padx=5, pady=5)
        
        # 目标显示 (截断过长的URL)
        display_target = task.display_name
        if len(display_target) > 25:
            display_target = display_target[:22] + "..."
        ctk.CTkLabel(row, text=display_target, width=160, anchor="w").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # 进度条区
        prog_frame = ctk.CTkFrame(row, fg_color="transparent")
        prog_frame.grid(row=0, column=2, padx=5, pady=5)
        
        prog_bar = ctk.CTkProgressBar(prog_frame, width=80, height=8)
        prog_val = task.crawled_count / task.max_notes if task.max_notes else 0
        prog_bar.set(prog_val)
        prog_bar.pack(side=tk.LEFT, padx=(0, 5))
        
        prog_lbl = ctk.CTkLabel(prog_frame, text=f"{task.crawled_count}/{task.max_notes}", width=40)
        prog_lbl.pack(side=tk.LEFT)
        
        # 状态
        status_colors = {
            STATUS_PENDING: ("gray50", "gray50"),
            STATUS_RUNNING: ("#3b82f6", "#3b82f6"),
            STATUS_COMPLETED: ("#22c55e", "#22c55e"),
            STATUS_FAILED: ("#ef4444", "#ef4444"),
            STATUS_PAUSED: ("#f59e0b", "#f59e0b")
        }
        color = status_colors.get(task.status, ("gray50", "gray50"))
        
        status_lbl = ctk.CTkLabel(row, text=task.status_display, width=60, text_color=color, font=ctk.CTkFont(weight="bold"))
        status_lbl.grid(row=0, column=3, padx=5, pady=5)
        
        # 操作按钮
        del_btn = ctk.CTkButton(row, text="×", width=30, height=24, fg_color="transparent", 
                                hover_color="#ef4444", text_color=("gray10", "gray90"),
                                command=lambda t_id=task.task_id: _remove_task(app, t_id))
        del_btn.grid(row=0, column=4, padx=5, pady=5)
        
        # 保存组件引用以便未来按需部分更新(可选)
        app.task_widgets[task.task_id] = {
            "prog_bar": prog_bar,
            "prog_lbl": prog_lbl,
            "status_lbl": status_lbl
        }
        
    if hasattr(app, "task_summary_var"):
        app.task_summary_var.set(app.task_manager.get_summary())


def _remove_task(app, task_id):
    app.task_manager.remove_task(task_id)
    refresh_task_list(app)


def _clear_all_tasks(app):
    import tkinter.messagebox as messagebox
    if app.task_manager.tasks:
        if messagebox.askyesno("确认", "确定清空全部任务？"):
            app.task_manager.tasks = []
            refresh_task_list(app)
