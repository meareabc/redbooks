# -*- coding: utf-8 -*-
"""Cookie管理器"""

import os
import json
import threading
from typing import Optional
from datetime import datetime

from .constants import VERSION


class CookieManager:
    """Cookie管理器（支持过期检测）"""
    
    def __init__(self, cookies_file: str):
        self.cookies_file = cookies_file
        self._lock = threading.Lock()
    
    def _ensure_dir(self):
        """确保目录存在"""
        cookie_dir = os.path.dirname(self.cookies_file)
        if cookie_dir:
            os.makedirs(cookie_dir, exist_ok=True)
        
    def save(self, page) -> bool:
        """保存Cookie"""
        with self._lock:
            try:
                cookies = page.cookies()
                self._ensure_dir()
                data = {
                    'cookies': cookies,
                    'saved_at': datetime.now().isoformat(),
                    'version': VERSION
                }
                with open(self.cookies_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            except Exception:
                return False
    
    def load(self, page) -> bool:
        """加载Cookie"""
        with self._lock:
            try:
                if not os.path.exists(self.cookies_file):
                    return False
                    
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 兼容旧格式
                cookies = data.get('cookies', data) if isinstance(data, dict) else data
                
                loaded = 0
                for cookie in cookies:
                    try:
                        page.set.cookies(cookie)
                        loaded += 1
                    except Exception:
                        pass
                return loaded > 0
            except Exception:
                return False
    
    def exists(self) -> bool:
        """检查Cookie是否存在"""
        return os.path.exists(self.cookies_file)
    
    def get_saved_time(self) -> Optional[str]:
        """获取Cookie保存时间"""
        try:
            if not os.path.exists(self.cookies_file):
                return None
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('saved_at', '未知')
        except Exception:
            return None
    
    def clear(self):
        """清除Cookie"""
        if os.path.exists(self.cookies_file):
            os.remove(self.cookies_file)
