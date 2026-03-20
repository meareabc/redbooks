# -*- coding: utf-8 -*-
"""多任务队列管理器 - 支持多博主/多关键词独立执行，断点续爬"""

import uuid
import json
import sqlite3
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional


# 任务状态常量
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


@dataclass
class TaskItem:
    """单个爬取任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type: str = "keyword"      # keyword / blogger / hot
    target: str = ""                # 关键词或博主URL
    max_notes: int = 30
    status: str = STATUS_PENDING
    crawled_count: int = 0
    last_note_id: str = ""
    error_msg: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def to_dict(self):
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'target': self.target,
            'max_notes': self.max_notes,
            'status': self.status,
            'crawled_count': self.crawled_count,
            'last_note_id': self.last_note_id,
            'error_msg': self.error_msg,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
    
    @property
    def display_name(self):
        """显示名称"""
        if self.task_type == "blogger":
            # 从URL提取简短标识
            short_id = self.target.rstrip('/').split('/')[-1].split('?')[0]
            return f"博主_{short_id}"
        elif self.task_type == "hot":
            return f"热门_{self.target}"
        else:
            return self.target if self.target else "主页推荐"
    
    @property
    def status_display(self):
        """状态显示文字"""
        status_map = {
            STATUS_PENDING: "⏳ 待执行",
            STATUS_RUNNING: "▶️ 执行中",
            STATUS_PAUSED: "⏸ 已暂停",
            STATUS_COMPLETED: "✅ 已完成",
            STATUS_FAILED: "❌ 失败",
        }
        return status_map.get(self.status, self.status)


class TaskManager:
    """多任务队列管理器"""
    
    def __init__(self, db_path: str = "data/redbook.db"):
        self.db_path = db_path
        self.tasks: List[TaskItem] = []
        self._init_table()
        self._load_tasks()
    
    def _init_table(self):
        """确保任务列表表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_queue (
                task_id TEXT PRIMARY KEY,
                task_type TEXT,
                target TEXT,
                max_notes INTEGER DEFAULT 30,
                status TEXT DEFAULT 'pending',
                crawled_count INTEGER DEFAULT 0,
                last_note_id TEXT DEFAULT '',
                error_msg TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def _load_tasks(self):
        """从数据库加载未完成的任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, task_type, target, max_notes, status, 
                       crawled_count, last_note_id, error_msg, created_at, updated_at
                FROM task_queue 
                WHERE status IN (?, ?, ?)
                ORDER BY created_at ASC
            ''', (STATUS_PENDING, STATUS_RUNNING, STATUS_PAUSED))
            
            for row in cursor.fetchall():
                task = TaskItem(
                    task_id=row[0], task_type=row[1], target=row[2],
                    max_notes=row[3], status=row[4], crawled_count=row[5],
                    last_note_id=row[6], error_msg=row[7],
                    created_at=row[8], updated_at=row[9]
                )
                # 之前运行中但程序中断的任务，恢复为暂停状态
                if task.status == STATUS_RUNNING:
                    task.status = STATUS_PAUSED
                self.tasks.append(task)
            
            conn.close()
        except Exception:
            pass
    
    def _save_task(self, task: TaskItem):
        """保存单个任务到数据库"""
        task.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO task_queue 
                (task_id, task_type, target, max_notes, status, 
                 crawled_count, last_note_id, error_msg, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.task_id, task.task_type, task.target, task.max_notes,
                task.status, task.crawled_count, task.last_note_id,
                task.error_msg, task.created_at, task.updated_at
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    def add_task(self, task_type: str, target: str, max_notes: int = 30) -> Optional[TaskItem]:
        """添加新任务（自动检查重复）
        
        Returns:
            TaskItem 如果成功添加，None 如果已存在未完成的同名任务
        """
        target = target.strip()
        if not target:
            return None
        
        # 检查是否已存在未完成的同类任务
        existing = self.find_task(task_type, target)
        if existing and existing.status in (STATUS_PENDING, STATUS_PAUSED, STATUS_RUNNING):
            return None  # 已有未完成任务，跳过
        
        task = TaskItem(
            task_type=task_type,
            target=target,
            max_notes=max_notes,
        )
        self.tasks.append(task)
        self._save_task(task)
        return task
    
    def add_tasks_from_input(self, task_type: str, input_text: str, max_notes: int = 30) -> List[TaskItem]:
        """从用户输入解析并添加多个任务
        
        支持逗号或换行分隔多个关键词/URL
        """
        new_tasks = []
        # 分割输入（支持逗号、换行、分号）
        items = []
        for line in input_text.replace(';', ',').replace('；', ',').replace('，', ',').split('\n'):
            for item in line.split(','):
                item = item.strip()
                if item:
                    items.append(item)
        
        # 去重
        seen = set()
        for item in items:
            if item not in seen:
                seen.add(item)
                # 检查是否已存在未完成的同类任务
                existing = self.find_task(task_type, item)
                if existing and existing.status in (STATUS_PENDING, STATUS_PAUSED):
                    # 已有未完成任务，跳过
                    continue
                task = self.add_task(task_type, item, max_notes)
                new_tasks.append(task)
        
        return new_tasks
    
    def find_task(self, task_type: str, target: str) -> Optional[TaskItem]:
        """查找已有任务"""
        for task in self.tasks:
            if task.task_type == task_type and task.target == target.strip():
                return task
        return None
    
    def remove_task(self, task_id: str):
        """删除任务"""
        self.tasks = [t for t in self.tasks if t.task_id != task_id]
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM task_queue WHERE task_id = ?', (task_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    def get_next_task(self) -> Optional[TaskItem]:
        """获取下一个待执行任务（按顺序执行，支持断点续爬）"""
        for task in self.tasks:
            if task.status in (STATUS_PENDING, STATUS_PAUSED):
                return task
        return None
    
    def start_task(self, task: TaskItem):
        """标记任务为运行中"""
        task.status = STATUS_RUNNING
        self._save_task(task)
    
    def pause_task(self, task: TaskItem, error_msg: str = ""):
        """暂停任务（保存进度）"""
        task.status = STATUS_PAUSED
        task.error_msg = error_msg
        self._save_task(task)
    
    def complete_task(self, task: TaskItem):
        """标记任务为已完成"""
        task.status = STATUS_COMPLETED
        self._save_task(task)
    
    def fail_task(self, task: TaskItem, error_msg: str = ""):
        """标记任务为失败"""
        task.status = STATUS_FAILED
        task.error_msg = error_msg
        self._save_task(task)
    
    def update_progress(self, task: TaskItem, crawled_count: int, last_note_id: str = ""):
        """更新任务进度"""
        task.crawled_count = crawled_count
        if last_note_id:
            task.last_note_id = last_note_id
        self._save_task(task)
    
    def clear_completed(self):
        """清除已完成的任务"""
        completed_ids = [t.task_id for t in self.tasks if t.status == STATUS_COMPLETED]
        self.tasks = [t for t in self.tasks if t.status != STATUS_COMPLETED]
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for tid in completed_ids:
                cursor.execute('DELETE FROM task_queue WHERE task_id = ?', (tid,))
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    def has_pending_tasks(self) -> bool:
        """是否有待执行的任务"""
        return any(t.status in (STATUS_PENDING, STATUS_PAUSED) for t in self.tasks)
    
    def get_summary(self) -> str:
        """获取任务队列摘要"""
        total = len(self.tasks)
        pending = sum(1 for t in self.tasks if t.status == STATUS_PENDING)
        running = sum(1 for t in self.tasks if t.status == STATUS_RUNNING)
        paused = sum(1 for t in self.tasks if t.status == STATUS_PAUSED)
        completed = sum(1 for t in self.tasks if t.status == STATUS_COMPLETED)
        failed = sum(1 for t in self.tasks if t.status == STATUS_FAILED)
        
        parts = []
        if pending: parts.append(f"{pending}待执行")
        if running: parts.append(f"{running}执行中")
        if paused: parts.append(f"{paused}已暂停")
        if completed: parts.append(f"{completed}已完成")
        if failed: parts.append(f"{failed}失败")
        
        return f"共{total}个任务: " + ", ".join(parts) if parts else "无任务"
