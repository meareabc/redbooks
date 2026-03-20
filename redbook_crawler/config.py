# -*- coding: utf-8 -*-
"""爬虫配置管理"""

import os
import json
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class CrawlerConfig:
    """爬虫配置（使用dataclass提升可维护性）"""
    # 基础配置
    keyword: str = ""
    scroll_times: int = 10
    max_notes: int = 30
    parallel_downloads: int = 10
    retry_times: int = 2
    save_interval: int = 10
    
    # 爬取内容选项（默认全部开启）
    download_images: bool = True
    download_videos: bool = True
    get_all_images: bool = True
    get_content: bool = True
    get_tags: bool = True
    get_publish_time: bool = True
    get_comments: bool = True
    comments_count: int = 20
    get_interactions: bool = True
    
    # 爬取模式
    crawl_mode: str = "standard"  # standard/fast/turbo
    crawl_type: str = "keyword"   # keyword/blogger/hot
    blogger_url: str = ""
    
    # 筛选条件
    min_likes: int = 0
    max_likes: int = 999999
    note_type_filter: str = "全部"
    date_filter: str = "全部"
    
    # 导出选项
    export_format: str = "xlsx"
    export_to_db: bool = True
    db_path: str = "data/redbook.db"
    
    # 速度控制（元组默认值需要用field）
    click_delay: Tuple[float, float] = field(default_factory=lambda: (0.2, 0.4))
    scroll_delay: Tuple[float, float] = field(default_factory=lambda: (0.3, 0.5))
    
    # Cookie和日志
    save_cookies: bool = True
    cookies_file: str = "data/cookies.json"
    log_to_file: bool = True
    log_file: str = "data/crawler.log"
    
    # 配置文件路径
    config_file: str = "data/settings.json"
    
    # 窗口位置
    window_x: int = -1
    window_y: int = -1
    window_width: int = 1000
    window_height: int = 750
    
    def save_to_file(self):
        """保存配置到文件"""
        try:
            os.makedirs("data", exist_ok=True)
            config_dict = {
                'keyword': self.keyword,
                'scroll_times': self.scroll_times,
                'max_notes': self.max_notes,
                'parallel_downloads': self.parallel_downloads,
                'retry_times': self.retry_times,
                'download_images': self.download_images,
                'download_videos': self.download_videos,
                'get_all_images': self.get_all_images,
                'get_content': self.get_content,
                'get_tags': self.get_tags,
                'get_publish_time': self.get_publish_time,
                'get_comments': self.get_comments,
                'comments_count': self.comments_count,
                'get_interactions': self.get_interactions,
                'crawl_mode': self.crawl_mode,
                'crawl_type': self.crawl_type,
                'blogger_url': self.blogger_url,
                'min_likes': self.min_likes,
                'max_likes': self.max_likes,
                'note_type_filter': self.note_type_filter,
                'date_filter': self.date_filter,
                'export_format': self.export_format,
                'export_to_db': self.export_to_db,
                'window_x': self.window_x,
                'window_y': self.window_y,
                'window_width': self.window_width,
                'window_height': self.window_height,
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            print(f"[配置] 已保存到 {self.config_file}")
        except Exception as e:
            print(f"[配置] 保存失败: {e}")
    
    def load_from_file(self):
        """从文件加载配置"""
        if not os.path.exists(self.config_file):
            print("[配置] 配置文件不存在，使用默认设置")
            return False
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            for key, value in config_dict.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            print(f"[配置] 已加载上次设置 (max_notes={self.max_notes}, keyword={self.keyword})")
            return True
        except Exception as e:
            print(f"[配置] 加载失败: {e}")
            return False
