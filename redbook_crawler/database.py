# -*- coding: utf-8 -*-
"""数据库管理器"""

import os
import json
import sqlite3
from datetime import datetime


class DatabaseManager:
    """数据库管理器"""
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id TEXT UNIQUE,
                title TEXT,
                author TEXT,
                content TEXT,
                tags TEXT,
                publish_time TEXT,
                ip_region TEXT,
                like_count INTEGER,
                collect_count INTEGER,
                comment_count INTEGER,
                note_type TEXT,
                note_link TEXT,
                image_urls TEXT,
                video_url TEXT,
                comments TEXT,
                keyword TEXT,
                crawl_time TEXT
            )
        ''')
        
        # 爬取任务状态表（用于断点续爬）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crawl_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_url TEXT UNIQUE,
                task_type TEXT,
                crawled_count INTEGER DEFAULT 0,
                last_note_id TEXT,
                last_update TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_note(self, note_data):
        """插入笔记"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO notes 
                (note_id, title, author, content, tags, publish_time, ip_region,
                 like_count, collect_count, comment_count, note_type, note_link,
                 image_urls, video_url, comments, keyword, crawl_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                note_data.get('note_id', ''),
                note_data.get('title', ''),
                note_data.get('author', ''),
                note_data.get('content', ''),
                json.dumps(note_data.get('tags', []), ensure_ascii=False),
                note_data.get('publish_time', ''),
                note_data.get('ip_region', ''),
                note_data.get('like_count', 0),
                note_data.get('collect_count', 0),
                note_data.get('comment_count', 0),
                note_data.get('note_type', ''),
                note_data.get('note_link', ''),
                json.dumps(note_data.get('image_urls', []), ensure_ascii=False),
                note_data.get('video_url', ''),
                json.dumps(note_data.get('comments', []), ensure_ascii=False),
                note_data.get('keyword', ''),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def get_existing_note_ids(self, keyword):
        """获取已存在的笔记ID（用于增量更新）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT note_id FROM notes WHERE keyword = ?', (keyword,))
        ids = set(row[0] for row in cursor.fetchall())
        conn.close()
        return ids
    
    def get_existing_note_ids_by_url(self, task_url):
        """根据博主URL获取已存在的笔记ID（用于断点续爬）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT note_id FROM notes WHERE keyword = ?', (task_url,))
        ids = set(row[0] for row in cursor.fetchall())
        conn.close()
        return ids
    
    def save_task_state(self, task_url, task_type, crawled_count, last_note_id):
        """保存爬取任务状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO crawl_tasks 
            (task_url, task_type, crawled_count, last_note_id, last_update)
            VALUES (?, ?, ?, ?, ?)
        ''', (task_url, task_type, crawled_count, last_note_id, 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    
    def load_task_state(self, task_url):
        """加载爬取任务状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT task_type, crawled_count, last_note_id 
            FROM crawl_tasks WHERE task_url = ?
        ''', (task_url,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                'task_type': row[0],
                'crawled_count': row[1],
                'last_note_id': row[2]
            }
        return None

    def delete_task_history(self, keyword):
        """删除特定任务的所有历史记录（包括笔记和任务队列）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM notes WHERE keyword = ?', (keyword,))
            
            # 由于由于历史原因，crawl_tasks和task_queue可能都存有
            cursor.execute('DELETE FROM crawl_tasks WHERE task_url = ?', (keyword,))
            
            # 对于task_queue，有些是博主形式
            cursor.execute('DELETE FROM task_queue WHERE target = ?', (keyword,))
            
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def get_all_task_keywords(self):
        """获取数据库中所有存在的任务/关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT keyword FROM notes WHERE keyword IS NOT NULL AND keyword != ""')
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception:
            return []
        finally:
            conn.close()
