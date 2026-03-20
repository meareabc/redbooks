# -*- coding: utf-8 -*-
"""数据分析页面"""

import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from datetime import datetime

import pandas as pd

from ..constants import HAS_MATPLOTLIB, HAS_WORDCLOUD, HAS_DOCX
from ..analyzer import DataAnalyzer


def create_analysis_page(app, parent):
    """创建数据分析页面 (CustomTkinter)"""
    # === 分析工具 ===
    tools_frame = ctk.CTkFrame(parent)
    tools_frame.pack(fill=tk.X, padx=10, pady=10)
    
    ctk.CTkLabel(tools_frame, text="分析工具", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))
    
    row1 = ctk.CTkFrame(tools_frame, fg_color="transparent")
    row1.pack(fill=tk.X, padx=10, pady=(5, 15))
    
    ctk.CTkButton(row1, text="📊 生成统计图表", command=lambda: _generate_charts(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ctk.CTkButton(row1, text="☁️ 生成词云", command=lambda: _generate_wordcloud(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ctk.CTkButton(row1, text="📄 生成分析报告", command=lambda: _generate_report(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ctk.CTkButton(row1, text="🔄 合并所有数据", command=lambda: _merge_data(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    
    # === 统计仪表盘 ===
    dashboard_frame = ctk.CTkFrame(parent)
    dashboard_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
    
    ctk.CTkLabel(dashboard_frame, text="统计仪表盘", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))
    
    stats_grid = ctk.CTkFrame(dashboard_frame, fg_color="transparent")
    stats_grid.pack(fill=tk.X, padx=10, pady=(0, 15))
    
    app.dashboard_labels = {}
    stats_items = [
        ("total_notes", "总笔记", "0"),
        ("total_likes", "总点赞", "0"),
        ("avg_likes", "平均点赞", "0"),
        ("max_likes", "最高点赞", "0"),
        ("total_collects", "总收藏", "0"),
        ("total_comments", "总评论", "0"),
        ("image_notes", "图文笔记", "0"),
        ("video_notes", "视频笔记", "0"),
    ]
    
    for i, (key, label, default) in enumerate(stats_items):
        row = i // 4
        col = i % 4
        
        card = ctk.CTkFrame(stats_grid, corner_radius=8, fg_color=("gray90", "gray16"))
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
        app.dashboard_labels[key] = ctk.CTkLabel(card, text=default, font=ctk.CTkFont(size=22, weight="bold"), text_color="#3b82f6")
        app.dashboard_labels[key].pack(pady=(0, 15))
    
    for i in range(4):
        stats_grid.columnconfigure(i, weight=1)
    
    # === 历史记录 ===
    history_frame = ctk.CTkFrame(parent)
    history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
    
    ctk.CTkLabel(history_frame, text="历史记录", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))
    
    tree_container = ctk.CTkFrame(history_frame, fg_color="transparent")
    tree_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
    
    columns = ("时间", "目标", "笔记数", "图片数", "文件")
    app.history_tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=8)
    
    for col in columns:
        app.history_tree.heading(col, text=col)
        app.history_tree.column(col, width=120 if col != "文件" else 200)
    
    scrollbar = ctk.CTkScrollbar(tree_container, orientation="vertical", command=app.history_tree.yview)
    app.history_tree.configure(yscrollcommand=scrollbar.set)
    
    app.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    _refresh_history(app)


def _generate_charts(app):
    """生成图表"""
    if not HAS_MATPLOTLIB:
        messagebox.showwarning("提示", "需要安装matplotlib库")
        return
    
    if not app.all_notes_data:
        _load_latest_data(app)
    
    if not app.all_notes_data:
        messagebox.showinfo("提示", "没有数据可分析")
        return
    
    df = pd.DataFrame(app.all_notes_data)
    charts = DataAnalyzer.generate_charts(df, "data/charts")
    
    if charts:
        messagebox.showinfo("完成", f"已生成 {len(charts)} 个图表\n保存到: data/charts/")
        os.startfile("data/charts")
    else:
        messagebox.showwarning("提示", "图表生成失败")


def _generate_wordcloud(app):
    """生成词云"""
    if not HAS_WORDCLOUD:
        messagebox.showwarning("提示", "需要安装wordcloud和jieba库")
        return
    
    if not app.all_notes_data:
        _load_latest_data(app)
    
    if not app.all_notes_data:
        messagebox.showinfo("提示", "没有数据可分析")
        return
    
    texts = [d.get('title', '') + ' ' + d.get('content', '') for d in app.all_notes_data]
    output = "data/wordcloud.png"
    
    result = DataAnalyzer.generate_wordcloud(texts, output)
    if result:
        messagebox.showinfo("完成", f"词云已生成: {output}")
        os.startfile(output)
    else:
        messagebox.showwarning("提示", "词云生成失败")


def _generate_report(app):
    """生成分析报告"""
    if not HAS_DOCX:
        messagebox.showwarning("提示", "需要安装python-docx库")
        return
    
    if not app.all_notes_data:
        _load_latest_data(app)
    
    if not app.all_notes_data:
        messagebox.showinfo("提示", "没有数据可分析")
        return
    
    df = pd.DataFrame(app.all_notes_data)
    stats = DataAnalyzer.generate_stats(df)
    
    charts = []
    if HAS_MATPLOTLIB:
        charts = DataAnalyzer.generate_charts(df, "data/charts")
    
    keyword = app.all_notes_data[0].get('keyword', '未知') if app.all_notes_data else '未知'
    output = f"data/分析报告_{keyword}_{int(time.time())}.docx"
    
    result = DataAnalyzer.generate_report(df, stats, charts, output, keyword)
    if result:
        messagebox.showinfo("完成", f"报告已生成: {output}")
        os.startfile(output)
    else:
        messagebox.showwarning("提示", "报告生成失败")


def _load_latest_data(app):
    """加载最新数据文件"""
    if not os.path.exists("data"):
        return
    
    files = [f for f in os.listdir("data") if f.startswith("搜索结果_") and f.endswith(".xlsx")]
    if not files:
        return
    
    files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)), reverse=True)
    latest = os.path.join("data", files[0])
    
    try:
        df = pd.read_excel(latest)
        app.all_notes_data = df.to_dict('records')
    except Exception:
        pass


def _merge_data(app):
    """合并所有数据"""
    if not os.path.exists("data"):
        messagebox.showinfo("提示", "没有数据文件")
        return
    
    all_dfs = []
    for f in os.listdir("data"):
        if f.startswith("搜索结果_") and f.endswith(".xlsx"):
            try:
                df = pd.read_excel(os.path.join("data", f))
                all_dfs.append(df)
            except Exception:
                continue
    
    if not all_dfs:
        messagebox.showinfo("提示", "没有可合并的数据")
        return
    
    merged = pd.concat(all_dfs, ignore_index=True)
    if 'note_link' in merged.columns:
        merged = merged.drop_duplicates(subset=['note_link'])
    
    output = f"data/合并数据_{int(time.time())}.xlsx"
    merged.to_excel(output, index=False)
    
    messagebox.showinfo("完成", f"已合并 {len(merged)} 条数据\n保存到: {output}")


def _refresh_history(app):
    """刷新历史"""
    for item in app.history_tree.get_children():
        app.history_tree.delete(item)
    
    if not os.path.exists("data"):
        return
    
    files = []
    for f in os.listdir("data"):
        if f.startswith("搜索结果_") and f.endswith((".xlsx", ".csv", ".json")):
            path = os.path.join("data", f)
            files.append((f, os.path.getmtime(path), path))
    
    files.sort(key=lambda x: x[1], reverse=True)
    
    for f, mtime, path in files[:20]:
        try:
            keyword = f.replace("搜索结果_", "").rsplit("_", 1)[0]
            time_str = datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
            
            if f.endswith(".xlsx"):
                df = pd.read_excel(path)
            elif f.endswith(".csv"):
                df = pd.read_csv(path)
            else:
                df = pd.read_json(path)
            
            notes = len(df)
            images = df['image_count'].sum() if 'image_count' in df.columns else 0
            
            app.history_tree.insert("", tk.END, values=(time_str, keyword, notes, images, f))
        except Exception:
            continue
