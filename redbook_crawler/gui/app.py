# -*- coding: utf-8 -*-
"""爬虫GUI应用主模块 - 组装各页面、协调爬取流程"""

import os
import re
import time
import queue
import shutil
import zipfile
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime
from urllib.parse import quote

from ..constants import HAS_CTK, APP_NAME
if HAS_CTK:
    import customtkinter as ctk

from ..config import CrawlerConfig
from ..logger import FileLogger
from ..cookie_manager import CookieManager
from ..database import DatabaseManager
from ..downloader import MediaDownloader
from ..crawler import CrawlerEngine
from ..task_manager import TaskManager, STATUS_PENDING, STATUS_PAUSED, STATUS_COMPLETED

from .main_page import create_main_page, refresh_task_list
from .result_page import create_result_page, populate_results
from .content_page import create_content_page
from .analysis_page import create_analysis_page
from .settings_page import create_settings_page


class CrawlerApp:
    """爬虫GUI应用"""
    
    def __init__(self):
        # 创建窗口
        if HAS_CTK:
            self.root = ctk.CTk()
            self.root.configure(fg_color="#f5f5f5")
        else:
            self.root = tk.Tk()
        
        self.root.title(APP_NAME)
        self.root.minsize(900, 650)
        
        # 配置
        self.config = CrawlerConfig()
        self.config.load_from_file()
        
        win_x = self.config.window_x if self.config.window_x >= 0 else 100
        win_y = self.config.window_y if self.config.window_y >= 0 else 100
        self.root.geometry(f"1000x700+{win_x}+{win_y}")
        
        # 核心组件
        self.downloader = MediaDownloader()
        self.cookie_mgr = CookieManager(self.config.cookies_file)
        self.file_logger = FileLogger(self.config.log_file)
        self.db_mgr = DatabaseManager(self.config.db_path)
        self.task_manager = TaskManager(self.config.db_path)
        
        # 状态
        self.log_queue = queue.Queue()
        self.is_running = False
        self.should_stop = False
        self.all_notes_data = []
        self.current_crawl_dir = ""
        self.browser_page = None
        self.crawler_engine = None
        
        # 构建UI
        self._setup_styles()
        self._create_ui()
        self._start_log_consumer()
        self._restore_gui_settings()
        
        # 退出时保存配置
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def run(self):
        """运行应用"""
        self.root.mainloop()
    
    # ========== UI构建 ==========
    
    def _setup_styles(self):
        """设置样式主题"""
        if HAS_CTK:
            ctk.set_appearance_mode("System")
            ctk.set_default_color_theme("blue")
            
        style = ttk.Style()
        style.theme_use("default")
        
        # 兼容深浅色的Treeview样式
        bg_color = "#ffffff" if ctk.get_appearance_mode() == "Light" else "#2b2b2b"
        fg_color = "#000000" if ctk.get_appearance_mode() == "Light" else "#ffffff"
        sel_bg = "#3b82f6" if ctk.get_appearance_mode() == "Light" else "#1f538d"
        sel_fg = "#ffffff"
        
        style.configure("Treeview", background=bg_color, foreground=fg_color,
                        fieldbackground=bg_color, rowheight=38, borderwidth=0,
                        font=('Microsoft YaHei UI', 12))
        style.configure("Treeview.Heading", background=bg_color, foreground=fg_color,
                        font=('Microsoft YaHei UI', 13, 'bold'), borderwidth=1, relief="flat")
        style.map("Treeview", background=[('selected', sel_bg)], foreground=[('selected', sel_fg)])
        style.map("Treeview.Heading", background=[('active', sel_bg)])

    def _create_ui(self):
        """创建界面 - 现代侧边栏布局"""
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        
        # === 侧边栏 ===
        self.sidebar_frame = ctk.CTkFrame(self.root, width=180, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1) # Spacer
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="小红书爬虫", font=ctk.CTkFont('Microsoft YaHei UI', size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))
        
        self.sidebar_buttons = []
        btn_data = [
            ("搜索爬取", self._show_main_page),
            ("爬取结果", self._show_result_page),
            ("内容选项", self._show_content_page),
            ("数据分析", self._show_analysis_page),
            ("高级设置", self._show_settings_page)
        ]
        
        for i, (text, command) in enumerate(btn_data, 1):
            btn = ctk.CTkButton(self.sidebar_frame, text=text, command=command,
                                font=ctk.CTkFont('Microsoft YaHei UI', size=15),
                                fg_color="transparent", text_color=("gray10", "gray90"),
                                hover_color=("gray70", "gray30"), anchor="w")
            btn.grid(row=i, column=0, padx=20, pady=10, sticky="ew")
            self.sidebar_buttons.append(btn)
            
        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="主题模式:", anchor="w")
        self.appearance_mode_label.grid(row=7, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionmenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["System", "Light", "Dark"],
                                                               command=self.change_appearance_mode_event)
        self.appearance_mode_optionmenu.grid(row=8, column=0, padx=20, pady=(10, 20))
        
        # === 主区域 ===
        self.main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Pages dict
        self.pages = {}
        for name in ["main", "result", "content", "analysis", "settings"]:
            frame = ctk.CTkFrame(self.main_container, corner_radius=0, fg_color="transparent")
            self.pages[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        # 调用各页面模块创建UI
        create_main_page(self, self.pages["main"])
        create_result_page(self, self.pages["result"])
        create_content_page(self, self.pages["content"])
        create_analysis_page(self, self.pages["analysis"])
        create_settings_page(self, self.pages["settings"])
        
        # 显示默认页
        self._show_main_page()
        
    def _select_sidebar_btn(self, index):
        for i, btn in enumerate(self.sidebar_buttons):
            if i == index:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")
                
    def _show_main_page(self):
        self._select_sidebar_btn(0)
        self.pages["main"].tkraise()
        
    def _show_result_page(self):
        self._select_sidebar_btn(1)
        self.pages["result"].tkraise()
        
    def _show_content_page(self):
        self._select_sidebar_btn(2)
        self.pages["content"].tkraise()
        
    def _show_analysis_page(self):
        self._select_sidebar_btn(3)
        self.pages["analysis"].tkraise()
        
    def _show_settings_page(self):
        self._select_sidebar_btn(4)
        self.pages["settings"].tkraise()

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        self._setup_styles()
    
    # ========== 日志系统 ==========
    
    def _start_log_consumer(self):
        """启动日志消费者"""
        def consume():
            try:
                while not self.log_queue.empty():
                    msg, level = self.log_queue.get_nowait()
                    self._write_log(msg, level)
            except Exception:
                pass
            self.root.after(100, consume)
        self.root.after(100, consume)
    
    def _log(self, message, level="INFO"):
        """添加日志"""
        self.log_queue.put((message, level))
        if hasattr(self, 'file_logger') and self.config.log_to_file:
            self.file_logger.log(message, level)
    
    def _write_log(self, message, level="INFO"):
        """写入日志到GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        level_icons = {
            "INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️",
            "ERROR": "❌", "DEBUG": "🔍"
        }
        icon = level_icons.get(level, "")
        
        log_line = f"[{timestamp}] {icon} {message}\n"
        
        try:
            if HAS_CTK:
                self.log_text.configure(state="normal")
                self.log_text.insert("end", log_line)
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
            else:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, log_line, level)
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
        except Exception:
            pass
    
    # ========== GUI设置恢复 ==========
    
    def _restore_gui_settings(self):
        """恢复上次的GUI设置"""
        try:
            if hasattr(self, 'max_notes_var'):
                self.max_notes_var.set(str(self.config.max_notes))
            if hasattr(self, 'keyword_var') and self.config.keyword:
                self.keyword_var.set(self.config.keyword)
            if hasattr(self, 'crawl_mode_var'):
                self.crawl_mode_var.set(self.config.crawl_mode)
            if hasattr(self, 'crawl_type_var'):
                self.crawl_type_var.set(self.config.crawl_type)
            if hasattr(self, 'blogger_url_var') and self.config.blogger_url:
                self.blogger_url_var.set(self.config.blogger_url)
            if hasattr(self, 'export_format_var'):
                self.export_format_var.set(self.config.export_format)
        except Exception:
            pass
        
        # 刷新任务列表
        if hasattr(self, 'task_manager'):
            refresh_task_list(self)
    
    def _save_gui_settings(self):
        """保存GUI设置到配置"""
        try:
            self.config.keyword = self.keyword_var.get()
            self.config.max_notes = int(self.max_notes_var.get())
            self.config.crawl_mode = self.crawl_mode_var.get()
            self.config.crawl_type = self.crawl_type_var.get()
            self.config.blogger_url = self.blogger_url_var.get()
            self.config.export_format = self.export_format_var.get()
            self.config.download_images = self.download_images_var.get()
            self.config.download_videos = self.download_videos_var.get()
            self.config.get_all_images = self.get_all_images_var.get()
            self.config.get_content = self.get_content_var.get()
            self.config.get_tags = self.get_tags_var.get()
            self.config.get_publish_time = self.get_time_var.get()
            self.config.get_comments = self.get_comments_var.get()
            self.config.comments_count = int(self.comments_count_var.get())
            self.config.get_interactions = self.get_interactions_var.get()
            self.config.export_to_db = self.export_db_var.get()
            self.config.save_cookies = self.save_cookies_var.get()
            self.config.log_to_file = self.log_to_file_var.get()
            self.config.min_likes = int(self.min_likes_var.get())
            self.config.max_likes = int(self.max_likes_var.get())
            self.config.note_type_filter = self.note_type_var.get()
            self.config.date_filter = self.date_filter_var.get()
            
            try:
                self.config.click_delay = (float(self.click_min_var.get()), float(self.click_max_var.get()))
                self.config.scroll_delay = (float(self.scroll_min_var.get()), float(self.scroll_max_var.get()))
            except Exception:
                pass
            
            geo = self.root.geometry()
            match = re.match(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', geo)
            if match:
                self.config.window_x = int(match.group(3))
                self.config.window_y = int(match.group(4))
            
            self.config.save_to_file()
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    # ========== 爬取控制 ==========
    
    def _start_crawl(self):
        """开始爬取"""
        if self.is_running:
            self._log("已有爬取任务在运行", "WARNING")
            return
        
        self._save_gui_settings()
        
        # 如果没有待执行任务，尝试直接添加当前输入框的内容
        if not self.task_manager.has_pending_tasks():
            from .main_page import _add_tasks_to_queue
            _add_tasks_to_queue(self)
            
            # 如果还是没有，提示用户
            if not self.task_manager.has_pending_tasks():
                from tkinter import messagebox
                messagebox.showinfo("提示", "请先在左侧输入目标，并添加到任务队列")
                return
        
        self._log(f"开始执行任务队列", "INFO")
        
        # 设置运行状态
        self.is_running = True
        self.should_stop = False
        self.all_notes_data = []
        
        # 更新按钮
        if HAS_CTK:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
        
        # 在线程中执行
        thread = threading.Thread(target=self._run_tasks, daemon=True)
        thread.start()
    
    def _run_tasks(self):
        """执行任务队列（后台线程）"""
        try:
            # 初始化爬取引擎
            self.crawler_engine = CrawlerEngine(
                config=self.config,
                downloader=self.downloader,
                db_mgr=self.db_mgr,
                cookie_mgr=self.cookie_mgr,
                log_func=self._log,
                update_ui_func=self._update_crawl_ui,
                root=self.root,
            )
            self.crawler_engine.browser_page = self.browser_page
            self.crawler_engine._on_note_extracted = self._on_note_extracted
            
            # 启动浏览器
            self._log("正在启动浏览器...", "INFO")
            page = self.crawler_engine.ensure_browser()
            if not page:
                self._log("浏览器启动失败", "ERROR")
                self._on_crawl_done()
                return
            self.browser_page = self.crawler_engine.browser_page
            
            # 执行任务队列
            while self.task_manager.has_pending_tasks() and not self.should_stop:
                task = self.task_manager.get_next_task()
                if not task:
                    break
                
                self._log(f"\n{'='*50}", "INFO")
                self._log(f"开始任务: {task.display_name} ({task.task_type})", "INFO")
                if task.crawled_count > 0:
                    self._log(f"  从断点恢复: 已完成 {task.crawled_count}/{task.max_notes}", "INFO")
                self._log(f"{'='*50}", "INFO")
                
                self.task_manager.start_task(task)
                refresh_task_list_safe(self)
                
                try:
                    self._execute_single_task(task, page)
                except InterruptedError:
                    self._log(f"任务被取消: {task.display_name}", "WARNING")
                    self.task_manager.pause_task(task, "用户取消")
                except Exception as e:
                    self._log(f"任务失败: {task.display_name} - {e}", "ERROR")
                    self.task_manager.fail_task(task, str(e)[:200])
                
                refresh_task_list_safe(self)
            
            # 保存数据
            if self.all_notes_data:
                keyword = self.all_notes_data[0].get('keyword', 'unknown')
                saved = self.crawler_engine.save_data(self.all_notes_data, keyword)
                self._log(f"数据已保存: {saved}", "SUCCESS")
                
                # 更新结果页
                self.root.after(0, lambda: populate_results(self))
            
            self._log(f"\n所有任务执行完毕！{self.task_manager.get_summary()}", "SUCCESS")
            
        except Exception as e:
            self._log(f"执行异常: {e}", "ERROR")
        finally:
            self._on_crawl_done()
    
    def _execute_single_task(self, task, page):
        """执行单个任务"""
        self.config.max_notes = task.max_notes
        self.crawler_engine.config = self.config
        self.crawler_engine.should_stop = self.should_stop
        
        start_time = time.time()
        crawl_mode = self.config.crawl_mode
        
        # 根据任务类型导航
        if task.task_type == "keyword":
            keyword = task.target
            keyword_code = quote(quote(keyword.encode('utf-8')).encode('gb2312'))
            url = f'https://www.xiaohongshu.com/search_result?keyword={keyword_code}&source=web_search_result_notes'
            self._log(f"打开搜索页: {keyword}", "INFO")
            page.get(url)
            time.sleep(2)
            
        elif task.task_type == "blogger":
            url = task.target
            self._log(f"打开博主主页: {url}", "INFO")
            page.get(url)
            time.sleep(2)
            keyword = task.display_name
            
        elif task.task_type == "hot":
            category = task.target
            page.get('https://www.xiaohongshu.com/explore')
            time.sleep(2)
            keyword = f"热门_{category}"
        
        # 滚动加载
        self._log("正在加载笔记...", "INFO")
        scroll_count = int(self.config.scroll_times)
        for i in range(scroll_count):
            if self.should_stop:
                break
            page.scroll.to_bottom()
            time.sleep(0.5)
            self._update_crawl_ui(status=f"加载中 {i+1}/{scroll_count}")
        
        # 获取笔记元素
        note_elements = page.eles("css:section.note-item", timeout=2)
        self._log(f"找到 {len(note_elements)} 个笔记元素", "INFO")
        
        if not note_elements:
            self._log("未找到笔记，可能需要登录或页面加载失败", "WARNING")
            self.task_manager.fail_task(task, "未找到笔记元素")
            return
        
        # 加载已有笔记ID（用于断点续爬）
        existing_ids = set()
        if task.task_type == "blogger":
            existing_ids = self.db_mgr.get_existing_note_ids_by_url(task.target)
        elif task.task_type == "keyword":
            existing_ids = self.db_mgr.get_existing_note_ids(task.target)
        
        # 执行爬取
        if crawl_mode == "standard" or crawl_mode == "turbo":
            success, images, videos = self.crawler_engine.standard_crawl(
                page, note_elements, keyword if task.task_type != "blogger" else task.target,
                start_time, existing_ids, 
                task_url=task.target if task.task_type == "blogger" else "",
                start_count=task.crawled_count
            )
        elif crawl_mode == "fast":
            success, images, videos = self.crawler_engine.fast_crawl(
                page, note_elements, keyword, start_time
            )
        else:
            success, images, videos = self.crawler_engine.standard_crawl(
                page, note_elements, keyword, start_time, existing_ids,
                start_count=task.crawled_count
            )
        
        # 同步引擎数据
        self.all_notes_data = self.crawler_engine.all_notes_data
        
        # 更新任务状态
        self.task_manager.update_progress(task, success, "")
        
        if self.should_stop or self.crawler_engine.should_stop:
            self.task_manager.pause_task(task, "用户暂停")
        elif success >= task.max_notes:
            self.task_manager.complete_task(task)
        else:
            self.task_manager.complete_task(task)
        
        elapsed = int(time.time() - start_time)
        self._log(f"任务完成: {task.display_name} - {success}笔记 {images}图 {videos}视频 用时{elapsed}秒", "SUCCESS")
    
    def _on_note_extracted(self, note_data, index):
        """笔记提取完成回调"""
        # 在主线程更新结果表格
        self.root.after(0, lambda: populate_results(self))
    
    def _update_crawl_ui(self, **kwargs):
        """更新爬取UI（从后台线程调用）"""
        def update():
            try:
                if 'status' in kwargs:
                    self.status_var.set(kwargs['status'])
                if 'notes' in kwargs:
                    self.notes_var.set(kwargs['notes'])
                if 'images' in kwargs:
                    self.images_var.set(kwargs['images'])
                if 'videos' in kwargs:
                    self.videos_var.set(kwargs['videos'])
                if 'time' in kwargs:
                    self.time_var.set(kwargs['time'])
                if 'progress' in kwargs:
                    prog = min(100, max(0, kwargs['progress']))
                    self.total_progress['value'] = prog
                    self.progress_label.config(text=f"{prog:.0f}%")
            except Exception:
                pass
        self.root.after(0, update)
    
    def _stop_crawl(self):
        """停止爬取"""
        self.should_stop = True
        if self.crawler_engine:
            self.crawler_engine.should_stop = True
        self._log("正在停止...", "WARNING")
        self.status_var.set("正在停止...")
    
    def _on_crawl_done(self):
        """爬取完成后的清理"""
        self.is_running = False
        
        def update():
            try:
                if HAS_CTK:
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                else:
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                
                self.status_var.set("就绪")
                refresh_task_list(self)
            except Exception:
                pass
        
        self.root.after(0, update)
    
    # ========== 工具功能 ==========
    
    def _use_saved_cookies(self):
        """使用已保存的Cookie"""
        if self.cookie_mgr.exists():
            saved_time = self.cookie_mgr.get_saved_time()
            msg = "将在爬取时自动加载Cookie，可跳过登录"
            if saved_time and saved_time != '未知':
                msg += f"\n\n保存时间: {saved_time}"
            messagebox.showinfo("Cookie信息", msg)
        else:
            messagebox.showwarning("提示", "未找到保存的Cookie\n请先完成一次登录，系统会自动保存")
    
    def _open_data_dir(self):
        """打开数据目录"""
        os.makedirs("data", exist_ok=True)
        os.startfile("data")
    
    def _zip_images(self):
        """打包图片"""
        if not os.path.exists("images"):
            messagebox.showinfo("提示", "没有找到图片目录")
            return
        
        timestamp = int(time.time())
        zip_name = f"data/images_{timestamp}.zip"
        os.makedirs("data", exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk("images"):
                    for file in files:
                        filepath = os.path.join(root, file)
                        arcname = os.path.relpath(filepath, "images")
                        zf.write(filepath, arcname)
            
            size_mb = os.path.getsize(zip_name) / 1024 / 1024
            messagebox.showinfo("完成", f"图片已打包: {zip_name}\n大小: {size_mb:.1f}MB")
        except Exception as e:
            messagebox.showerror("错误", f"打包失败: {e}")
    
    def _open_log_file(self):
        """打开日志文件"""
        if os.path.exists(self.config.log_file):
            os.startfile(self.config.log_file)
        else:
            messagebox.showinfo("提示", "日志文件不存在")
    
    def _clear_log_file(self):
        """清空日志文件"""
        try:
            if os.path.exists(self.config.log_file):
                with open(self.config.log_file, 'w') as f:
                    f.write("")
                messagebox.showinfo("完成", "日志已清空")
        except Exception as e:
            messagebox.showerror("错误", f"清空失败: {e}")
    
    def _browse_db_path(self):
        """浏览数据库路径"""
        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite数据库", "*.db")]
        )
        if path:
            self.db_path_var.set(path)
    
    def _on_closing(self):
        """关闭窗口"""
        self._save_gui_settings()
        
        if self.browser_page:
            try:
                self.browser_page.quit()
            except Exception:
                pass
        
        self.downloader.close()
        self.root.destroy()


def refresh_task_list_safe(app):
    """线程安全的任务列表刷新"""
    app.root.after(0, lambda: refresh_task_list(app))
