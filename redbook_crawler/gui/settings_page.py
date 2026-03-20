# -*- coding: utf-8 -*-
"""高级设置页面"""

import os
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime


def create_settings_page(app, parent):
    """创建设置页面 (CustomTkinter)"""
    parent.grid_columnconfigure((0, 1), weight=1)
    
    # === Cookie管理 ===
    cookie_frame = ctk.CTkFrame(parent)
    cookie_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(cookie_frame, text="Cookie管理", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    app.save_cookies_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(cookie_frame, text="登录后自动保存Cookie", variable=app.save_cookies_var).pack(anchor="w", padx=15, pady=8)
    
    row1 = ctk.CTkFrame(cookie_frame, fg_color="transparent")
    row1.pack(fill=tk.X, padx=15, pady=8)
    app.cookie_status_var = tk.StringVar(value="未检测到Cookie")
    ctk.CTkLabel(row1, textvariable=app.cookie_status_var, text_color="gray").pack(side=tk.LEFT, padx=(0, 10))
    ctk.CTkButton(row1, text="清除Cookie", command=lambda: _clear_cookies(app), width=100).pack(side=tk.LEFT)
    
    _check_cookie_status(app)
    
    # === 日志设置 ===
    log_frame = ctk.CTkFrame(parent)
    log_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(log_frame, text="日志设置", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    app.log_to_file_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(log_frame, text="保存日志到文件", variable=app.log_to_file_var).pack(anchor="w", padx=15, pady=8)
    
    row2 = ctk.CTkFrame(log_frame, fg_color="transparent")
    row2.pack(fill=tk.X, padx=15, pady=8)
    
    ctk.CTkButton(row2, text="打开日志", command=app._open_log_file, width=100).pack(side=tk.LEFT, padx=(0, 10))
    ctk.CTkButton(row2, text="清空日志", command=app._clear_log_file, width=100,
                  fg_color="#ef4444", hover_color="#dc2626").pack(side=tk.LEFT)
    
    # === 速度控制 ===
    speed_frame = ctk.CTkFrame(parent)
    speed_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(speed_frame, text="速度控制", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    row3 = ctk.CTkFrame(speed_frame, fg_color="transparent")
    row3.pack(fill=tk.X, padx=15, pady=8)
    
    ctk.CTkLabel(row3, text="点击延迟(秒):").pack(side=tk.LEFT)
    app.click_min_var = tk.StringVar(value="0.3")
    ctk.CTkEntry(row3, textvariable=app.click_min_var, width=60).pack(side=tk.LEFT, padx=5)
    ctk.CTkLabel(row3, text="-").pack(side=tk.LEFT)
    app.click_max_var = tk.StringVar(value="0.5")
    ctk.CTkEntry(row3, textvariable=app.click_max_var, width=60).pack(side=tk.LEFT, padx=5)
    
    row3_2 = ctk.CTkFrame(speed_frame, fg_color="transparent")
    row3_2.pack(fill=tk.X, padx=15, pady=8)
    
    ctk.CTkLabel(row3_2, text="滚动延迟(秒):").pack(side=tk.LEFT)
    app.scroll_min_var = tk.StringVar(value="0.4")
    ctk.CTkEntry(row3_2, textvariable=app.scroll_min_var, width=60).pack(side=tk.LEFT, padx=5)
    ctk.CTkLabel(row3_2, text="-").pack(side=tk.LEFT)
    app.scroll_max_var = tk.StringVar(value="0.6")
    ctk.CTkEntry(row3_2, textvariable=app.scroll_max_var, width=60).pack(side=tk.LEFT, padx=5)
    
    # === 反爬设置 ===
    anti_frame = ctk.CTkFrame(parent)
    anti_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(anti_frame, text="反爬虫设置", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    app.random_delay_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(anti_frame, text="随机延迟（模拟人类行为）", variable=app.random_delay_var).pack(anchor="w", padx=15, pady=10)
    
    app.random_scroll_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(anti_frame, text="随机滚动距离", variable=app.random_scroll_var).pack(anchor="w", padx=15, pady=10)
    
    # === 数据库设置 ===
    db_frame = ctk.CTkFrame(parent)
    db_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(db_frame, text="数据库设置", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
    
    row5 = ctk.CTkFrame(db_frame, fg_color="transparent")
    row5.pack(fill=tk.X, padx=15, pady=8)
    
    ctk.CTkLabel(row5, text="数据库路径:").pack(side=tk.LEFT)
    app.db_path_var = tk.StringVar(value="data/redbook.db")
    ctk.CTkEntry(row5, textvariable=app.db_path_var, width=400).pack(side=tk.LEFT, padx=10)
    
    ctk.CTkButton(row5, text="浏览", command=app._browse_db_path, width=80).pack(side=tk.LEFT)


def _check_cookie_status(app):
    """检查Cookie状态"""
    if app.cookie_mgr.exists():
        saved_time = app.cookie_mgr.get_saved_time()
        if saved_time and saved_time != '未知':
            try:
                dt = datetime.fromisoformat(saved_time)
                time_str = dt.strftime("%m-%d %H:%M")
                app.cookie_status_var.set(f"[已保存] Cookie ({time_str})")
            except Exception:
                app.cookie_status_var.set("[已保存] Cookie")
        else:
            app.cookie_status_var.set("[已保存] Cookie")
    else:
        app.cookie_status_var.set("[未保存] 未检测到Cookie")


def _clear_cookies(app):
    """清除Cookie"""
    if messagebox.askyesno("确认", "确定要清除保存的Cookie吗？"):
        app.cookie_mgr.clear()
        app.cookie_status_var.set("[未保存] Cookie已清除")
