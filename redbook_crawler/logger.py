# -*- coding: utf-8 -*-
"""文件日志记录器"""

import os
import threading
from datetime import datetime


class FileLogger:
    """文件日志记录器（线程安全）"""
    
    def __init__(self, log_file: str):
        self.log_file = log_file
        self._lock = threading.Lock()
        self._ensure_dir()
    
    def _ensure_dir(self):
        """确保日志目录存在"""
        log_dir = os.path.dirname(self.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
    def log(self, message: str, level: str = "INFO"):
        """线程安全的日志写入"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}\n"
        with self._lock:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line)
            except Exception:
                pass
