# -*- coding: utf-8 -*-
"""内容选项页面"""

import tkinter as tk
import customtkinter as ctk

def create_content_page(app, parent):
    """创建内容选项页面 (CustomTkinter)"""
    parent.grid_columnconfigure((0, 1), weight=1)
    
    # === 基础内容 ===
    basic_frame = ctk.CTkFrame(parent)
    basic_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(basic_frame, text="基础内容", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    app.get_content_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(basic_frame, text="获取笔记正文内容", variable=app.get_content_var).pack(anchor="w", padx=15, pady=10)
    
    app.get_tags_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(basic_frame, text="提取话题标签 (#xxx)", variable=app.get_tags_var).pack(anchor="w", padx=15, pady=10)
    
    app.get_time_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(basic_frame, text="获取发布时间", variable=app.get_time_var).pack(anchor="w", padx=15, pady=10)
    
    app.get_interactions_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(basic_frame, text="获取互动数据（点赞/收藏/评论数）", variable=app.get_interactions_var).pack(anchor="w", padx=15, pady=10)
    
    # === 图片视频 ===
    media_frame = ctk.CTkFrame(parent)
    media_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(media_frame, text="图片/视频", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    app.download_images_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(media_frame, text="下载图片", variable=app.download_images_var).pack(anchor="w", padx=15, pady=10)
    
    app.get_all_images_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(media_frame, text="获取全部图片（切换轮播）", variable=app.get_all_images_var).pack(anchor="w", padx=15, pady=10)
    
    app.download_videos_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(media_frame, text="下载视频", variable=app.download_videos_var).pack(anchor="w", padx=15, pady=10)
    
    # === 评论 ===
    comment_frame = ctk.CTkFrame(parent)
    comment_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(comment_frame, text="评论爬取", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    app.get_comments_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(comment_frame, text="获取热门评论", variable=app.get_comments_var).pack(anchor="w", padx=15, pady=10)
    
    row4 = ctk.CTkFrame(comment_frame, fg_color="transparent")
    row4.pack(fill=tk.X, padx=15, pady=10)
    
    ctk.CTkLabel(row4, text="评论数量:").pack(side=tk.LEFT)
    app.comments_count_var = tk.StringVar(value="10")
    ctk.CTkEntry(row4, textvariable=app.comments_count_var, width=80).pack(side=tk.LEFT, padx=(10, 0))
    
    # === 导出格式 ===
    export_frame = ctk.CTkFrame(parent)
    export_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(export_frame, text="导出设置", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
    
    row5 = ctk.CTkFrame(export_frame, fg_color="transparent")
    row5.pack(fill=tk.X, padx=15, pady=10)
    
    ctk.CTkLabel(row5, text="导出格式:").pack(side=tk.LEFT)
    app.export_format_var = tk.StringVar(value="xlsx")
    ctk.CTkOptionMenu(row5, variable=app.export_format_var, values=["xlsx", "csv", "json"], width=120).pack(side=tk.LEFT, padx=(10, 0))
    
    app.export_db_var = tk.BooleanVar(value=True)
    ctk.CTkSwitch(export_frame, text="同时保存到SQLite数据库", variable=app.export_db_var).pack(anchor="w", padx=15, pady=(15, 10))
    
    # === 快捷预设 ===
    preset_frame = ctk.CTkFrame(parent)
    preset_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
    
    ctk.CTkLabel(preset_frame, text="快捷预设", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(5, 5))
    
    preset_row = ctk.CTkFrame(preset_frame, fg_color="transparent")
    preset_row.pack(fill=tk.X, padx=10, pady=(5, 15))
    
    ctk.CTkButton(preset_row, text="极速采集", command=lambda: _preset_turbo(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ctk.CTkButton(preset_row, text="完整数据", command=lambda: _preset_complete(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ctk.CTkButton(preset_row, text="只下图片", command=lambda: _preset_images(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ctk.CTkButton(preset_row, text="只下视频", command=lambda: _preset_videos(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ctk.CTkButton(preset_row, text="只要文本", command=lambda: _preset_text(app)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)


def _preset_turbo(app):
    """极速采集预设"""
    app.download_images_var.set(False)
    app.download_videos_var.set(False)
    app.get_all_images_var.set(False)
    app.get_content_var.set(False)
    app.get_tags_var.set(False)
    app.get_comments_var.set(False)
    app.get_interactions_var.set(True)
    app.crawl_mode_var.set("fast")


def _preset_complete(app):
    """完整数据预设"""
    app.download_images_var.set(True)
    app.download_videos_var.set(True)
    app.get_all_images_var.set(True)
    app.get_content_var.set(True)
    app.get_tags_var.set(True)
    app.get_comments_var.set(True)
    app.get_interactions_var.set(True)
    app.crawl_mode_var.set("standard")


def _preset_images(app):
    """只下图片预设"""
    app.download_images_var.set(True)
    app.download_videos_var.set(False)
    app.get_all_images_var.set(True)
    app.get_content_var.set(False)
    app.get_tags_var.set(False)
    app.get_comments_var.set(False)
    app.get_interactions_var.set(False)
    app.crawl_mode_var.set("standard")


def _preset_videos(app):
    """只下视频预设"""
    app.download_images_var.set(False)
    app.download_videos_var.set(True)
    app.get_all_images_var.set(False)
    app.get_content_var.set(False)
    app.get_tags_var.set(False)
    app.get_comments_var.set(False)
    app.get_interactions_var.set(False)
    app.note_type_var.set("视频")
    app.crawl_mode_var.set("standard")


def _preset_text(app):
    """只要文本预设"""
    app.download_images_var.set(False)
    app.download_videos_var.set(False)
    app.get_all_images_var.set(False)
    app.get_content_var.set(True)
    app.get_tags_var.set(True)
    app.get_comments_var.set(True)
    app.get_interactions_var.set(True)
    app.crawl_mode_var.set("standard")
