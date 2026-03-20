# -*- coding: utf-8 -*-
"""高性能媒体下载器"""

import os
import time
import random
from typing import Optional, List, Dict, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


class MediaDownloader:
    """高性能媒体下载器（支持图片和视频）"""
    
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(self, max_workers: int = 10, retry_times: int = 2, timeout: int = 15):
        self.max_workers = max_workers
        self.retry_times = retry_times
        self.timeout = timeout
        self._session = None
        self._stats = {'success': 0, 'failed': 0, 'bytes': 0}
    
    @property
    def session(self) -> requests.Session:
        """懒加载Session，复用连接"""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': random.choice(self.USER_AGENTS),
                'Referer': 'https://www.xiaohongshu.com/',
                'Accept': 'image/webp,image/apng,image/*,video/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Origin': 'https://www.xiaohongshu.com',
            })
        return self._session
    
    def set_cookies(self, cookies):
        """设置Cookie（用于需要认证的下载）"""
        if cookies:
            for cookie in cookies:
                self.session.cookies.set(
                    cookie.get('name', ''),
                    cookie.get('value', ''),
                    domain=cookie.get('domain', '.xiaohongshu.com')
                )
    
    def _normalize_url(self, url: str) -> str:
        """标准化URL"""
        if not url:
            return ""
        if url.startswith('//'):
            return 'https:' + url
        if not url.startswith('http'):
            return 'https://' + url
        return url
    
    def download_file(self, url: str, local_path: str, 
                      stop_flag: Optional[Callable] = None,
                      min_size: int = 1024) -> Optional[str]:
        """下载单个文件"""
        url = self._normalize_url(url)
        if not url:
            return None
            
        # 检查文件是否已存在且大小正常，避免重复下载
        if os.path.exists(local_path) and os.path.getsize(local_path) >= min_size:
            self._stats['success'] += 1
            return local_path
            
        for attempt in range(self.retry_times):
            if stop_flag and stop_flag():
                return None
            try:
                response = self.session.get(url, timeout=self.timeout, stream=True)
                response.raise_for_status()
                
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                total_size = 0
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=16384):
                        if stop_flag and stop_flag():
                            f.close()
                            if os.path.exists(local_path):
                                os.remove(local_path)
                            return None
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)
                
                if total_size < min_size:
                    os.remove(local_path)
                    return None
                
                self._stats['success'] += 1
                self._stats['bytes'] += total_size
                return local_path
                
            except requests.Timeout:
                if attempt < self.retry_times - 1:
                    time.sleep(0.2 * (attempt + 1))
            except Exception:
                if attempt < self.retry_times - 1:
                    time.sleep(0.1)
        
        self._stats['failed'] += 1
        return None
    
    def download_with_session(self, url: str, local_path: str, 
                               page=None, min_size: int = 1024) -> Optional[str]:
        """使用浏览器Session下载文件（用于评论图片等需要认证的资源）
        
        如果提供了page参数，会先同步浏览器Cookie到下载器。
        这是 download_file 的便捷封装。
        """
        if page:
            try:
                cookies = page.cookies()
                if cookies:
                    self.set_cookies(cookies)
            except Exception:
                pass
        return self.download_file(url, local_path, min_size=min_size)
    
    def download_batch(self, tasks: List[Tuple[str, str]], 
                       progress_callback: Optional[Callable] = None,
                       stop_flag: Optional[Callable] = None) -> Dict[str, Optional[str]]:
        """批量并行下载"""
        if not tasks:
            return {}
            
        results = {}
        completed = 0
        total = len(tasks)
        
        if stop_flag and stop_flag():
            return results
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            for url, path in tasks:
                if stop_flag and stop_flag():
                    break
                future = executor.submit(self.download_file, url, path, stop_flag)
                future_to_task[future] = (url, path)
            
            for future in as_completed(future_to_task):
                if stop_flag and stop_flag():
                    for f in future_to_task:
                        f.cancel()
                    break
                    
                url, path = future_to_task[future]
                try:
                    results[url] = future.result(timeout=self.timeout + 5)
                except Exception:
                    results[url] = None
                    
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
        
        return results
    
    def get_stats(self) -> Dict[str, int]:
        """获取下载统计"""
        return self._stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        self._stats = {'success': 0, 'failed': 0, 'bytes': 0}
    
    def close(self):
        """关闭Session"""
        if self._session:
            self._session.close()
            self._session = None
