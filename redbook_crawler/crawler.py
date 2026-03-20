# -*- coding: utf-8 -*-
"""核心爬取逻辑引擎"""

import os
import re
import time
import json
import random
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Callable
from urllib.parse import quote

import pandas as pd

from .utils import parse_num, is_emoji_image, filter_live_images, is_search_recommend_card
from . import browser


class CrawlerEngine:
    """爬取核心逻辑引擎
    
    从GUI分离的爬取逻辑，通过回调函数与GUI交互。
    """
    
    def __init__(self, config, downloader, db_mgr, cookie_mgr, log_func=None, 
                 update_ui_func=None, root=None):
        """
        Args:
            config: CrawlerConfig 配置
            downloader: MediaDownloader 下载器
            db_mgr: DatabaseManager 数据库管理器
            cookie_mgr: CookieManager Cookie管理器
            log_func: 日志回调 log(message, level)
            update_ui_func: UI更新回调 update_ui(**kwargs)
            root: tkinter根窗口（用于弹窗）
        """
        self.config = config
        self.downloader = downloader
        self.db_mgr = db_mgr
        self.cookie_mgr = cookie_mgr
        self.log = log_func or (lambda msg, level="INFO": print(f"[{level}] {msg}"))
        self.update_ui = update_ui_func or (lambda **kw: None)
        self.root = root
        
        self.should_stop = False
        self.browser_page = None
        self.all_notes_data = []
        self.current_crawl_dir = ""
    
    def ensure_browser(self):
        """确保浏览器已启动并已登录"""
        if self.browser_page is not None:
            # 复用已有浏览器
            self.log("复用已打开的浏览器", "INFO")
            page = self.browser_page
            page.get('https://www.xiaohongshu.com')
            time.sleep(1.5)
            if not browser.check_login(page):
                self.log("需要重新登录", "WARNING")
                browser.wait_for_login(page, self.root, self.log, self.config, self.cookie_mgr)
            browser.sync_browser_cookies(page, self.downloader, self.log)
            return page
        
        # 首次启动浏览器
        page = browser.create_browser(self.log)
        if not page:
            return None
        self.browser_page = page
        
        page.get('https://www.xiaohongshu.com')
        time.sleep(2)
        
        if browser.check_login(page):
            self.log("登录状态有效", "SUCCESS")
            browser.sync_browser_cookies(page, self.downloader, self.log)
        else:
            self.log("需要登录", "WARNING")
            browser.wait_for_login(page, self.root, self.log, self.config, self.cookie_mgr)
            browser.sync_browser_cookies(page, self.downloader, self.log)
        
        return page
    
    def _check_and_handle_verification(self, page) -> bool:
        """检查并处理验证弹窗
        
        Returns:
            True 如果一切正常（没有验证或已通过验证），False 如果用户取消
        """
        if browser.check_verification(page):
            self.log("检测到验证弹窗！", "WARNING")
            result = browser.wait_for_verification(
                page, self.root, self.log, self.cookie_mgr
            )
            if not result:
                return False
            # 验证完成后重新同步Cookie
            browser.sync_browser_cookies(page, self.downloader, self.log)
        return True
    
    def get_sorted_note_indices(self, page) -> List[int]:
        """获取按位置排序的笔记索引（从上到下、从左到右）"""
        try:
            script = """
            return (() => {
                const notes = document.querySelectorAll('section.note-item');
                if (notes.length === 0) return [];
                
                const positions = [];
                notes.forEach((n, i) => {
                    const rect = n.getBoundingClientRect();
                    positions.push({
                        domIndex: i,
                        left: Math.round(rect.left),
                        top: Math.round(rect.top)
                    });
                });
                
                positions.sort((a, b) => a.top - b.top);
                
                const rows = [];
                let currentRow = [positions[0]];
                let rowTop = positions[0].top;
                
                for (let i = 1; i < positions.length; i++) {
                    if (positions[i].top - rowTop < 80) {
                        currentRow.push(positions[i]);
                    } else {
                        rows.push(currentRow);
                        currentRow = [positions[i]];
                        rowTop = positions[i].top;
                    }
                }
                rows.push(currentRow);
                
                const result = [];
                rows.forEach(row => {
                    row.sort((a, b) => a.left - b.left);
                    row.forEach(p => result.push(p.domIndex));
                });
                
                return result;
            })()
            """
            result = page.run_js(script)
            if result and isinstance(result, list):
                return result
        except Exception as e:
            self.log(f"[排序] 失败: {e}", "WARNING")
        return list(range(len(page.eles("css:section.note-item", timeout=0.5))))
    
    def standard_crawl(self, page, note_elements, keyword: str, start_time: float, 
                       existing_ids: set = None, task_url: str = "", 
                       start_count: int = 0) -> Tuple[int, int, int]:
        """标准模式爬取"""
        success = start_count
        images = 0
        videos = 0
        timestamp = int(time.time())
        
        if task_url:
            short_id = task_url.rstrip('/').split('/')[-1].split('?')[0]
            images_dir = f"images/博主_{short_id}"
        else:
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = keyword if keyword else "主页推荐"
            folder_name = folder_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            images_dir = f"images/{folder_name}_{time_str}"
        
        self.current_crawl_dir = images_dir
        os.makedirs(images_dir, exist_ok=True)
        
        consecutive_fails = 0
        MAX_CONSECUTIVE_FAILS = 3
        
        crawled_urls = set()
        if existing_ids:
            crawled_urls.update(existing_ids)
            self.log(f"已加载 {len(existing_ids)} 个已爬取笔记，将跳过", "INFO")
        
        if keyword:
            keyword_code = quote(quote(keyword.encode('utf-8')).encode('gb2312'))
            base_url = f'https://www.xiaohongshu.com/search_result?keyword={keyword_code}&source=web_search_result_notes'
        else:
            base_url = 'https://www.xiaohongshu.com/explore'
        
        target_notes = self.config.max_notes
        self.log(f"开始爬取，目标 {target_notes} 个笔记", "INFO")
        
        max_attempts = target_notes * 3
        attempt = 0
        last_note_id = ""
        
        while success < target_notes and attempt < max_attempts:
            if self.should_stop:
                break
            
            attempt += 1
            elapsed = int(time.time() - start_time)
            progress = (success / target_notes) * 100 if target_notes > 0 else 0
            self.update_ui(
                status=f"爬取 {success}/{target_notes}",
                notes=f"笔记: {success}",
                images=f"图片: {images}",
                videos=f"视频: {videos}",
                time=f"用时: {elapsed}秒",
                progress=progress
            )
            
            # 连续失败时重新加载页面
            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                self.log("连续失败，重新加载页面", "WARNING")
                try:
                    page.get(base_url)
                    time.sleep(2)
                    for _ in range(5):
                        page.scroll.to_bottom()
                        time.sleep(0.5)
                except Exception:
                    break
                consecutive_fails = 0
            
            try:
                # 确保在目标页面
                current_url = page.url or ""
                if '/explore/' in current_url and 'xsec_token' in current_url:
                    try:
                        page.run_js("history.back()")
                        time.sleep(0.5)
                    except Exception:
                        pass
                
                # 验证弹窗检测
                if not self._check_and_handle_verification(page):
                    self.log("用户取消验证，暂停任务", "WARNING")
                    break
                
                elements = page.eles("css:section.note-item", timeout=1)
                if not elements:
                    self.log("未找到笔记元素，尝试滚动加载", "WARNING")
                    page.scroll.to_bottom()
                    time.sleep(1)
                    consecutive_fails += 1
                    continue
                
                found_note = False
                for i, elem in enumerate(elements):
                    cover_link = elem.ele('css:a.cover', timeout=0.1)
                    if not cover_link:
                        continue
                    
                    if is_search_recommend_card(elem):
                        continue
                    
                    note_href = cover_link.attr('href') or ""
                    note_id = ""
                    id_match = re.search(r'/explore/([a-zA-Z0-9]+)', note_href)
                    if id_match:
                        note_id = id_match.group(1)
                    else:
                        note_id = note_href.split('?')[0].rstrip('/').split('/')[-1]
                    
                    if note_id and note_id in crawled_urls:
                        continue
                    
                    found_note = True
                    
                    try:
                        card_title = elem.ele('css:.title, .note-title', timeout=0.1)
                        card_title_text = (card_title.text if card_title else "")[:20]
                    except Exception:
                        card_title_text = ""
                    
                    self.log(f"[{success+1}/{target_notes}] 位置{i+1}, 标题={card_title_text}", "INFO")
                    
                    elem.scroll.to_see()
                    time.sleep(0.1)
                    cover_link.click()
                    
                    time.sleep(random.uniform(*self.config.click_delay))
                    
                    # 等待弹窗加载
                    popup_loaded = False
                    for _ in range(10):
                        try:
                            if page.ele('css:.note-content, .note-text, .author-wrapper', timeout=0.1):
                                popup_loaded = True
                                break
                        except Exception:
                            pass
                        time.sleep(0.2)
                    
                    if popup_loaded:
                        for _ in range(5):
                            try:
                                if page.ele('css:.like-wrapper .count, .engage-bar .count', timeout=0.1):
                                    break
                            except Exception:
                                pass
                            time.sleep(0.2)
                        
                        for _ in range(5):
                            try:
                                if page.ele('css:.swiper-slide img, .carousel img, [class*="slider"] img', timeout=0.2):
                                    break
                            except Exception:
                                pass
                            time.sleep(0.3)
                    
                    # 检查验证弹窗
                    if not self._check_and_handle_verification(page):
                        self.log("验证被取消，暂停任务", "WARNING")
                        self.should_stop = True
                        break
                    
                    # 检查是否无法浏览
                    try:
                        unavailable = page.ele('xpath://div[contains(text(), "暂时无法浏览")]', timeout=0.2)
                        if unavailable:
                            self.log("笔记无法浏览，跳过", "WARNING")
                            crawled_urls.add(note_id)
                            page.run_js("history.back()")
                            time.sleep(0.3)
                            break
                    except Exception:
                        pass
                    
                    # 确保URL已更新
                    current_url = page.url
                    if note_id and note_id not in current_url:
                        for _ in range(10):
                            time.sleep(0.3)
                            current_url = page.url
                            if note_id in current_url:
                                break
                    
                    # 提取数据
                    time.sleep(0.5)
                    note_data = self.extract_full_note(page, success, images_dir, timestamp, keyword)
                    crawled_urls.add(note_id)
                    
                    if note_data and note_data.get('title'):
                        self.all_notes_data.append(note_data)
                        success += 1
                        images += note_data.get('image_count', 0)
                        videos += 1 if note_data.get('video_url') else 0
                        consecutive_fails = 0
                        
                        # 通知GUI更新表格
                        if hasattr(self, '_on_note_extracted') and self._on_note_extracted:
                            self._on_note_extracted(note_data, success - 1)
                        
                        if self.config.export_to_db:
                            self.db_mgr.insert_note(note_data)
                        
                        last_note_id = note_data.get('note_id', '')
                        if task_url and last_note_id:
                            self.db_mgr.save_task_state(task_url, 'blogger', success, last_note_id)
                        
                        title = note_data.get('title', '')[:25]
                        likes = note_data.get('like_count', 0)
                        self.log(f"[{success}] {title}... ❤️{likes}", "SUCCESS")
                    else:
                        consecutive_fails += 1
                    
                    # 返回列表页
                    try:
                        page.run_js("history.back()")
                        time.sleep(0.4)
                    except Exception:
                        page.actions.key_down('Escape').key_up('Escape')
                        time.sleep(0.3)
                    
                    break
                
                # 没找到未爬取笔记，滚动加载
                if not found_note:
                    prev_count = len(elements)
                    self.log(f"当前页面 {prev_count} 个笔记已全部处理，正在深入挖掘新内容...", "INFO")
                    
                    loaded_more = False
                    for scroll_try in range(8):
                        if self.should_stop:
                            break
                        scroll_dist = random.randint(800, 1500)
                        page.run_js(f"window.scrollBy(0, {scroll_dist})")
                        time.sleep(random.uniform(0.8, 1.5))
                        
                        new_elements = page.eles("css:section.note-item", timeout=0.5)
                        if len(new_elements) > prev_count:
                            loaded_more = True
                            temp_found = False
                            for ne in new_elements[prev_count:]:
                                try:
                                    ne_cover = ne.ele('css:a.cover', timeout=0.1)
                                    if not ne_cover:
                                        continue
                                    ne_href = ne_cover.attr('href') or ""
                                    ne_id = ""
                                    id_match = re.search(r'/explore/([a-zA-Z0-9]+)', ne_href)
                                    if id_match:
                                        ne_id = id_match.group(1)
                                    else:
                                        ne_id = ne_href.split('?')[0].rstrip('/').split('/')[-1]
                                    
                                    if ne_id and ne_id not in crawled_urls:
                                        temp_found = True
                                        break
                                except Exception:
                                    continue
                            if temp_found:
                                self.log("发现新大陆！找到未爬取的笔记了。", "SUCCESS")
                                break
                        
                        if "没有更多" in page.html or "到底了" in page.html:
                            self.log("已经翻到博主老底了，没有更多内容啦", "INFO")
                            break
                    
                    if not loaded_more:
                        self.log(f"连续 8 次向下滚动均未加载出新笔记，视为触底。共爬取 {success} 个", "WARNING")
                        break
                
            except Exception as e:
                consecutive_fails += 1
                error_msg = str(e)[:50] if str(e) else "未知错误"
                self.log(f"爬取失败: {error_msg}", "ERROR")
                
                try:
                    page.run_js("history.back()")
                    time.sleep(0.5)
                except Exception:
                    pass
        
        self.log(f"爬取完成：成功 {success} 个笔记", "SUCCESS")
        return success, images, videos
    
    def fast_crawl(self, page, note_elements, keyword, start_time):
        """极速模式爬取"""
        records = []
        timestamp = int(time.time())
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = keyword if keyword else "主页推荐"
        folder_name = folder_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        images_dir = f"images/{folder_name}_{time_str}"
        self.current_crawl_dir = images_dir
        total = len(note_elements)
        
        download_tasks = []
        
        for idx in range(total):
            if self.should_stop:
                break
            
            self.update_ui(
                status=f"扫描 {idx+1}/{total}",
                progress=(idx / total) * 50
            )
            
            try:
                elements = page.eles("css:section.note-item")
                if idx >= len(elements):
                    continue
                
                elem = elements[idx]
                
                title = ""
                try:
                    t = elem.ele('xpath:.//span[contains(@class, "title")]', timeout=0.2)
                    if t:
                        title = t.text or ""
                except Exception:
                    pass
                
                if not title:
                    try:
                        lines = (elem.text or "").split('\n')
                        title = next((l for l in lines if 5 < len(l) < 100), f"笔记{idx+1}")
                    except Exception:
                        title = f"笔记{idx+1}"
                
                author = ""
                try:
                    a = elem.ele('xpath:.//span[contains(@class, "name")]', timeout=0.2)
                    if a:
                        author = a.text or ""
                except Exception:
                    pass
                
                img_url = ""
                try:
                    img = elem.ele('xpath:.//img', timeout=0.2)
                    if img:
                        img_url = img.attr('src') or ""
                except Exception:
                    pass
                
                note_link = ""
                try:
                    link = elem.ele('xpath:.//a[contains(@href, "/explore/")]', timeout=0.2)
                    if link:
                        href = link.attr('href') or ""
                        note_link = 'https://www.xiaohongshu.com' + href if href.startswith('/') else href
                except Exception:
                    pass
                
                record = {
                    'title': title[:100],
                    'author': author or "未知",
                    'note_link': note_link,
                    'note_type': '图文',
                    'keyword': keyword,
                    'image_urls': [img_url] if img_url else [],
                    'image_count': 1 if img_url else 0,
                    'batch_dir': images_dir,
                }
                
                if img_url and self.config.download_images:
                    if not is_emoji_image(img_url):
                        folder = f"{images_dir}/note_{idx+1}_{timestamp}"
                        ext = '.webp' if '.webp' in img_url else '.jpg'
                        path = f"{folder}/img_1{ext}"
                        download_tasks.append((img_url, path, len(records)))
                
                records.append(record)
                
            except Exception:
                continue
        
        # 批量下载
        if download_tasks and self.config.download_images:
            self.log(f"下载 {len(download_tasks)} 张图片...", "INFO")
            
            def prog(done, total):
                self.update_ui(status=f"下载 {done}/{total}", progress=50 + (done/total)*50)
            
            results = self.downloader.download_batch(
                [(u, p) for u, p, _ in download_tasks],
                prog,
                lambda: self.should_stop
            )
            
            for url, path, rec_idx in download_tasks:
                if results.get(url):
                    abs_path = os.path.abspath(results[url])
                    records[rec_idx]['local_images'] = [abs_path]
        
        self.all_notes_data.extend(records)
        
        img_count = sum(1 for r in records if r.get('local_images'))
        return len(records), img_count, 0
    
    def extract_full_note(self, page, idx: int, images_dir: str, 
                          timestamp: int, keyword: str) -> Optional[Dict]:
        """提取完整笔记数据"""
        try:
            current_url = page.url or ""
            self.log(f"[DEBUG] 提取笔记 idx={idx}, URL={current_url[:80]}", "INFO")
            
            data = {'keyword': keyword, 'image_count': 0, 'batch_dir': images_dir}
            
            FAST_TIMEOUT = 0.2
            
            # === 标题 ===
            title = ""
            url_note_id = None
            if '/explore/' in current_url:
                url_note_id = current_url.split('/explore/')[-1].split('?')[0].split('/')[0]
            
            # 方法1: JavaScript获取
            try:
                js_title = page.run_js("""
                    return (() => {
                        const modal = document.querySelector('.note-detail-mask, [class*="noteContainer"], .note-container');
                        if (modal) {
                            const titleEl = modal.querySelector('.title, [class*="title"]');
                            if (titleEl && titleEl.textContent.trim().length > 2) {
                                return titleEl.textContent.trim();
                            }
                        }
                        try {
                            const state = window.__INITIAL_STATE__;
                            if (state && state.note) {
                                const urlMatch = window.location.href.match(/explore\\/([a-zA-Z0-9]+)/);
                                const noteId = urlMatch ? urlMatch[1] : state.note.currentNoteId;
                                if (noteId && state.note.noteDetailMap && state.note.noteDetailMap[noteId]) {
                                    const noteData = state.note.noteDetailMap[noteId];
                                    if (noteData.note && noteData.note.title) {
                                        return noteData.note.title;
                                    }
                                }
                            }
                        } catch(e) {}
                        return '';
                    })()
                """)
                if js_title and len(js_title.strip()) > 2:
                    title = js_title.strip()
            except Exception:
                pass
            
            # 方法2: CSS选择器
            if not title:
                title_selectors = [
                    'css:.note-detail-mask .title',
                    'css:[class*="noteContainer"] .title',
                    'css:.note-content .title',
                    'css:#detail-title',
                ]
                for sel in title_selectors:
                    try:
                        e = page.ele(sel, timeout=FAST_TIMEOUT)
                        if e and e.text and len(e.text.strip()) > 2:
                            title = e.text.strip()
                            break
                    except Exception:
                        continue
            
            # 方法3: 视频笔记用内容第一行
            if not title:
                try:
                    content_el = page.ele('css:.note-detail-mask .note-text, [class*="noteContainer"] .note-text, .note-text', timeout=FAST_TIMEOUT)
                    if content_el and content_el.text:
                        first_line = content_el.text.strip().split('\n')[0]
                        if len(first_line) > 2:
                            title = first_line[:50]
                except Exception:
                    pass
            
            data['title'] = title[:200] if title else f"笔记{idx+1}"
            
            # === 作者 ===
            author = ""
            try:
                js_author = page.run_js("""
                    return (() => {
                        const modal = document.querySelector('.note-detail-mask, [class*="noteContainer"], .note-container');
                        if (modal) {
                            const authorEl = modal.querySelector('.username, .author-wrapper .name, .user-info .name');
                            if (authorEl && authorEl.textContent.trim().length > 0 && authorEl.textContent.trim().length < 50) {
                                return authorEl.textContent.trim();
                            }
                        }
                        try {
                            const state = window.__INITIAL_STATE__;
                            if (state && state.note) {
                                const urlMatch = window.location.href.match(/explore\\/([a-zA-Z0-9]+)/);
                                const noteId = urlMatch ? urlMatch[1] : state.note.currentNoteId;
                                if (noteId && state.note.noteDetailMap && state.note.noteDetailMap[noteId]) {
                                    const noteData = state.note.noteDetailMap[noteId];
                                    if (noteData.note && noteData.note.user && noteData.note.user.nickname) {
                                        return noteData.note.user.nickname;
                                    }
                                }
                            }
                        } catch(e) {}
                        return '';
                    })()
                """)
                if js_author and len(js_author.strip()) > 0:
                    author = js_author.strip()
            except Exception:
                pass
            
            if not author:
                author_selectors = [
                    'css:.note-detail-mask .username',
                    'css:[class*="noteContainer"] .username',
                    'css:.author-wrapper .username',
                    'css:.author-wrapper .name',
                    'css:.user-info .name',
                ]
                for sel in author_selectors:
                    try:
                        e = page.ele(sel, timeout=FAST_TIMEOUT)
                        if e and e.text:
                            txt = e.text.strip()
                            if txt and len(txt) < 50:
                                author = txt
                                break
                    except Exception:
                        continue
            data['author'] = author or "未知"
            
            # === 正文内容 ===
            if self.config.get_content:
                content = ""
                content_selectors = [
                    'css:.note-detail-mask .note-text',
                    'css:[class*="noteContainer"] .note-text',
                    'css:.note-text',
                    'css:.desc',
                    'css:#detail-desc',
                ]
                for sel in content_selectors:
                    try:
                        e = page.ele(sel, timeout=FAST_TIMEOUT)
                        if e and e.text:
                            txt = e.text.strip()
                            if len(txt) > len(content):
                                content = txt
                    except Exception:
                        continue
                data['content'] = content
                
                if self.config.get_tags and content:
                    tags = re.findall(r'#([^\s#]+)', content)
                    data['tags'] = list(set(tags))[:20]
            
            # === 发布时间和IP ===
            if self.config.get_publish_time:
                pub_time = ""
                ip_region = ""
                try:
                    e = page.ele('css:.date', timeout=FAST_TIMEOUT)
                    if e:
                        full_text = (e.text or "").strip()
                        if " " in full_text:
                            parts = full_text.split(" ", 1)
                            pub_time = parts[0]
                            ip_region = parts[1] if len(parts) > 1 else ""
                        else:
                            pub_time = full_text
                except Exception:
                    pass
                data['publish_time'] = pub_time
                data['ip_region'] = ip_region
            
            # === 互动数据 ===
            if self.config.get_interactions:
                data['like_count'] = 0
                data['collect_count'] = 0
                data['comment_count'] = 0
                try:
                    try:
                        interact_result = page.run_js("""
                            return (() => {
                                const parseNum = (text) => {
                                    if (!text) return 0;
                                    text = String(text).trim().toLowerCase();
                                    if (text.includes('万')) return Math.floor(parseFloat(text.replace('万', '')) * 10000);
                                    if (text.includes('k')) return Math.floor(parseFloat(text.replace('k', '')) * 1000);
                                    const num = parseInt(text.replace(/[^0-9]/g, ''));
                                    return isNaN(num) ? 0 : num;
                                };
                                
                                try {
                                    const state = window.__INITIAL_STATE__;
                                    if (state && state.note) {
                                        const urlMatch = window.location.href.match(/explore\\/([a-zA-Z0-9]+)/);
                                        const noteId = urlMatch ? urlMatch[1] : state.note.currentNoteId;
                                        if (noteId && state.note.noteDetailMap && state.note.noteDetailMap[noteId]) {
                                            const noteData = state.note.noteDetailMap[noteId].note;
                                            if (noteData && noteData.interactInfo) {
                                                return JSON.stringify({
                                                    likes: parseNum(noteData.interactInfo.likedCount),
                                                    collects: parseNum(noteData.interactInfo.collectedCount),
                                                    comments: parseNum(noteData.interactInfo.commentCount)
                                                });
                                            }
                                        }
                                    }
                                } catch(e) {}
                                
                                const modal = document.querySelector('.note-detail-mask, [class*="noteContainer"], .note-container');
                                const searchRoot = modal || document;
                                const bar = searchRoot.querySelector('.buttons.engage-bar-style, .engage-bar, .interact-container');
                                if (bar) {
                                    const likeEl = bar.querySelector('.like-wrapper .count');
                                    const collectEl = bar.querySelector('.collect-wrapper .count');
                                    const chatEl = bar.querySelector('.chat-wrapper .count');
                                    return JSON.stringify({
                                        likes: parseNum(likeEl?.textContent),
                                        collects: parseNum(collectEl?.textContent),
                                        comments: parseNum(chatEl?.textContent)
                                    });
                                }
                                return '';
                            })()
                        """)
                        if interact_result:
                            interact_data = json.loads(interact_result)
                            if interact_data.get('likes', 0) > 0:
                                data['like_count'] = int(interact_data['likes'])
                            if interact_data.get('collects', 0) > 0:
                                data['collect_count'] = int(interact_data['collects'])
                            if interact_data.get('comments', 0) > 0:
                                data['comment_count'] = int(interact_data['comments'])
                    except Exception as e:
                        self.log(f"  JS获取互动数据失败: {e}", "WARNING")
                    
                    # CSS选择器备用
                    if data['like_count'] == 0:
                        for sel in ['css:.note-detail-mask .like-wrapper .count', 'css:[class*="noteContainer"] .like-wrapper .count', 'css:.engage-bar-style .like-wrapper .count']:
                            try:
                                e = page.ele(sel, timeout=0.3)
                                if e and e.text:
                                    num = parse_num(e.text)
                                    if num > 0:
                                        data['like_count'] = num
                                        break
                            except Exception:
                                pass
                    
                    if data['collect_count'] == 0:
                        for sel in ['css:.note-detail-mask .collect-wrapper .count', 'css:[class*="noteContainer"] .collect-wrapper .count']:
                            try:
                                e = page.ele(sel, timeout=0.3)
                                if e and e.text:
                                    num = parse_num(e.text)
                                    if num > 0:
                                        data['collect_count'] = num
                                        break
                            except Exception:
                                pass
                    
                    if data['comment_count'] == 0:
                        for sel in ['css:.note-detail-mask .chat-wrapper .count', 'css:[class*="noteContainer"] .chat-wrapper .count']:
                            try:
                                e = page.ele(sel, timeout=0.3)
                                if e and e.text:
                                    num = parse_num(e.text)
                                    if num > 0:
                                        data['comment_count'] = num
                                        break
                            except Exception:
                                pass
                    
                    if data['like_count'] > 0 or data['collect_count'] > 0:
                        self.log(f"  互动: ❤️{data['like_count']} ⭐{data['collect_count']} 💬{data['comment_count']}", "INFO")
                    
                except Exception as e:
                    self.log(f"  获取互动数据失败: {e}", "WARNING")
            
            # === 笔记ID和链接 ===
            current_url = page.url
            data['note_link'] = current_url if '/explore/' in current_url else ""
            note_id = ""
            if '/explore/' in current_url:
                note_id = current_url.split('/explore/')[-1].split('?')[0].rstrip('/')
            data['note_id'] = note_id
            
            # === 视频检测 ===
            note_type = "图文"
            video_url = ""
            try:
                v = None
                for _ in range(3):
                    v = page.ele('xpath://video', timeout=0.3)
                    if v:
                        break
                    time.sleep(0.2)
                
                if v:
                    note_type = "视频"
                    self.log("  检测到视频元素", "INFO")
                    time.sleep(0.5)
                    
                    try:
                        script = """
                        return (() => {
                            // 1. Meta tag (Very reliable on newer structure)
                            const metaVideo = document.querySelector('meta[name="og:video"]') || document.querySelector('meta[property="og:video"]');
                            if (metaVideo && metaVideo.content && !metaVideo.content.startsWith('blob:')) {
                                return metaVideo.content;
                            }
                            
                            // 2. Initial State Fallback
                            try {
                                if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.note) {
                                    const urlMatch = window.location.href.match(/explore\\/([a-zA-Z0-9]+)/);
                                    const noteId = urlMatch ? urlMatch[1] : window.__INITIAL_STATE__.note.currentNoteId;
                                    let currentNote = null;
                                    
                                    if (window.__INITIAL_STATE__.note.noteDetailMap && noteId && window.__INITIAL_STATE__.note.noteDetailMap[noteId]) {
                                        currentNote = window.__INITIAL_STATE__.note.noteDetailMap[noteId];
                                    } else if (window.__INITIAL_STATE__.note.note) {
                                        currentNote = window.__INITIAL_STATE__.note; // Direct structure
                                    }
                                    
                                    if (currentNote && currentNote.note && currentNote.note.video) {
                                        const video = currentNote.note.video;
                                        if (video.consumer && video.consumer.originVideoKey) {
                                            return 'https://sns-video-bd.xhscdn.com/' + video.consumer.originVideoKey;
                                        }
                                        if (video.media && video.media.stream && video.media.stream.h264) {
                                            const streams = video.media.stream.h264;
                                            if (streams.length > 0 && streams[0].masterUrl) return streams[0].masterUrl;
                                        }
                                        if (video.url && !video.url.startsWith('blob:')) return video.url;
                                    }
                                }
                            } catch(e) {}
                            
                            // 3. Raw DOM Fallback
                            const video = document.querySelector('video');
                            if (video) {
                                if (video.src && !video.src.startsWith('blob:')) return video.src;
                                const source = video.querySelector('source');
                                if (source && source.src && !source.src.startsWith('blob:')) return source.src;
                            }
                            return '';
                        })()
                        """
                        result = page.run_js(script)
                        if result and not result.startswith('blob:') and len(result) > 20:
                            video_url = result
                            self.log(f"  视频URL获取成功: {video_url[:60]}...", "SUCCESS")
                    except Exception as e:
                        self.log(f"  JS获取视频URL失败: {e}", "WARNING")
                    
                    if not video_url or video_url.startswith('blob:'):
                        try:
                            video_url = v.attr('src') or ""
                            if video_url and video_url.startswith('blob:'):
                                video_url = ""
                        except Exception:
                            pass
                    
                    if not video_url:
                        self.log("  无法获取可下载的视频URL (可能是blob格式)", "WARNING")
                        
            except Exception as e:
                self.log(f"  视频检测异常: {e}", "WARNING")
                
            data['note_type'] = note_type
            data['video_url'] = video_url
            
            # === 获取图片URL ===
            preview_images = []
            try:
                time.sleep(0.5)
                
                try:
                    js_images = page.run_js("""
                        return (() => {
                            const images = [];
                            const noteModal = document.querySelector('.note-detail-mask, .note-container, [class*="noteContainer"], [class*="note-detail"]');
                            const searchRoot = noteModal || document.body;
                            const mediaRoot = searchRoot.querySelector('.media-container, .left-container, .note-content, .media-box') || searchRoot;
                            
                            const carouselImgs = mediaRoot.querySelectorAll('.swiper-slide img, .carousel img, [class*="slider"] img, [class*="carousel"] img');
                            for (let img of carouselImgs) {
                                const src = img.src || img.getAttribute('data-src') || '';
                                if (src.length > 50 && (src.includes('xhscdn') || src.includes('sns-')) && 
                                    !src.includes('avatar') && !src.includes('emoji') && !src.includes('icon')) {
                                    images.push(src);
                                }
                            }
                            
                            if (images.length === 0) {
                                const allImgs = mediaRoot.querySelectorAll('img');
                                for (let img of allImgs) {
                                    const src = img.src || '';
                                    if (src.length > 80 && (src.includes('xhscdn') || src.includes('sns-img') || src.includes('sns-webpic'))) {
                                        if (!src.includes('avatar') && !src.includes('emoji') && !src.includes('icon') && !src.includes('loading')) {
                                            if (img.naturalWidth > 100 || img.width > 100 || img.naturalWidth === 0) {
                                                images.push(src);
                                            }
                                        }
                                    }
                                }
                            }
                            
                            if (images.length === 0) {
                                try {
                                    const state = window.__INITIAL_STATE__;
                                    if (state && state.note && state.note.noteDetailMap) {
                                        const urlMatch = window.location.href.match(/explore\\/([a-zA-Z0-9]+)/);
                                        const noteId = urlMatch ? urlMatch[1] : state.note.currentNoteId;
                                        if (noteId && state.note.noteDetailMap[noteId]) {
                                            const noteData = state.note.noteDetailMap[noteId];
                                            if (noteData.note && noteData.note.imageList) {
                                                for (let img of noteData.note.imageList) {
                                                    const url = img.urlDefault || img.url;
                                                    if (url) images.push(url);
                                                }
                                            }
                                        }
                                    }
                                } catch(e) {}
                            }
                            
                            return JSON.stringify([...new Set(images)].slice(0, 20));
                        })()
                    """)
                    
                    if js_images:
                        preview_images = json.loads(js_images)
                        self.log(f"  JS获取到 {len(preview_images)} 张图片", "INFO")
                except Exception as e:
                    self.log(f"  JS获取图片失败: {e}", "WARNING")
                
                # CSS选择器备用
                def get_current_images():
                    urls = []
                    selectors = [
                        'css:.media-container img',
                        'css:.note-detail-mask .swiper-slide img',
                        'css:.note-container .swiper-slide img',
                        'css:.img-container img',
                        'css:.swiper-wrapper img',
                        'css:.note-slider-img img',
                        'css:.carousel-img img',
                    ]
                    for sel in selectors:
                        try:
                            imgs = page.eles(sel, timeout=0.2)
                            if imgs:
                                for img in imgs[:20]:
                                    src = img.attr('src') or ""
                                    if src and len(src) > 50:
                                        src_lower = src.lower()
                                        if 'avatar' not in src_lower and 'icon' not in src_lower and 'emoji' not in src_lower:
                                            if not is_emoji_image(src):
                                                if src not in urls:
                                                    urls.append(src)
                                if urls:
                                    break
                        except Exception:
                            pass
                    return urls
                
                if not preview_images:
                    preview_images = get_current_images()
                
                # 轮播获取更多图片
                if self.config.get_all_images and note_type != "视频":
                    max_clicks = 15
                    for click_idx in range(max_clicks):
                        if self.should_stop:
                            break
                        
                        next_clicked = False
                        next_selectors = [
                            'css:.next-btn', 'css:.swiper-button-next',
                            'css:.carousel-next', 'css:[class*="next"]',
                            'xpath://div[contains(@class, "arrow") and contains(@class, "right")]',
                            'xpath://button[contains(@class, "next")]',
                        ]
                        
                        for sel in next_selectors:
                            try:
                                next_btn = page.ele(sel, timeout=0.2)
                                if next_btn:
                                    next_btn.click()
                                    next_clicked = True
                                    time.sleep(0.3)
                                    break
                            except Exception:
                                pass
                        
                        if not next_clicked:
                            try:
                                page.actions.key_down('RIGHT').key_up('RIGHT')
                                time.sleep(0.3)
                            except Exception:
                                pass
                        
                        new_images = get_current_images()
                        old_count = len(preview_images)
                        for img in new_images:
                            if img not in preview_images:
                                preview_images.append(img)
                        
                        if len(preview_images) == old_count:
                            break
                    
                    if len(preview_images) > 1:
                        self.log(f"  轮播获取到 {len(preview_images)} 张图片", "INFO")
                
            except Exception as e:
                self.log(f"  获取图片异常: {e}", "WARNING")
            
            # 过滤Live图
            filtered_images = filter_live_images(preview_images)
            data['image_urls'] = filtered_images[:20]
            self.log(f"  共获取到 {len(data['image_urls'])} 张图片URL", "INFO")
            
            # === 下载图片 ===
            if self.config.download_images and data['image_urls'] and note_type != "视频":
                if data.get('note_id') and data.get('batch_dir', '').startswith('images/博主_'):
                    folder = f"{images_dir}/note_{data['note_id']}"
                else:
                    folder = f"{images_dir}/note_{idx+1}_{note_id}" if note_id else f"{images_dir}/note_{idx+1}_{timestamp}"
                
                tasks = []
                for i, url in enumerate(data['image_urls'], 1):
                    ext = '.webp' if '.webp' in url else '.jpg'
                    tasks.append((url, f"{folder}/img_{i}{ext}"))
                
                if tasks:
                    results = self.downloader.download_batch(tasks, None, lambda: self.should_stop)
                    data['local_images'] = [os.path.abspath(r) for r in results.values() if r]
                    data['image_count'] = len(data['local_images'])
                    self.log(f"  下载成功 {data['image_count']}/{len(tasks)} 张图片", "SUCCESS" if data['image_count'] > 0 else "WARNING")
            elif note_type == "视频":
                self.log("  视频类型跳过图片下载", "INFO")
            
            # === 下载视频 ===
            if self.config.download_videos and video_url:
                self.log("  开始下载视频...", "INFO")
                if data.get('note_id') and data.get('batch_dir', '').startswith('images/博主_'):
                    folder = f"{images_dir}/note_{data['note_id']}"
                else:
                    folder = f"{images_dir}/note_{idx+1}_{note_id}" if note_id else f"{images_dir}/note_{idx+1}_{timestamp}"
                
                os.makedirs(folder, exist_ok=True)
                video_path = f"{folder}/video.mp4"
                result = self.downloader.download_file(video_url, video_path, lambda: self.should_stop, min_size=10240)
                if result:
                    data['local_video'] = result
                    file_size = os.path.getsize(result) if os.path.exists(result) else 0
                    self.log(f"  视频下载成功: {file_size/1024/1024:.1f}MB", "SUCCESS")
                else:
                    self.log("  视频下载失败", "WARNING")
            
            # === 评论 ===
            if self.config.get_comments:
                comments = self._extract_comments(page)
                data['comments'] = comments
                if comments:
                    self.log(f"  获取到 {len(comments)} 条评论", "INFO")
                    
                    comment_images_urls = []
                    for comment in comments:
                        if comment.get('images'):
                            comment_images_urls.extend(comment.get('images', []))
                    
                    if comment_images_urls and self.config.download_images:
                        if data.get('note_id') and data.get('batch_dir', '').startswith('images/博主_'):
                            note_save_folder = f"{images_dir}/note_{data['note_id']}"
                        else:
                            note_save_folder = f"{images_dir}/note_{idx+1}_{note_id}" if note_id else f"{images_dir}/note_{idx+1}_{timestamp}"
                        
                        comments_dir = os.path.join(note_save_folder, 'comments')
                        os.makedirs(comments_dir, exist_ok=True)
                        
                        comment_img_count = 0
                        for i, img_url in enumerate(comment_images_urls[:20]):
                            try:
                                ext = '.jpg'
                                if '.png' in img_url.lower():
                                    ext = '.png'
                                elif '.webp' in img_url.lower():
                                    ext = '.webp'
                                
                                filename = f"comment_img_{i+1}{ext}"
                                filepath = os.path.join(comments_dir, filename)
                                
                                if self.downloader.download_with_session(img_url, filepath, page):
                                    comment_img_count += 1
                            except Exception:
                                pass
                        
                        if comment_img_count > 0:
                            self.log(f"  评论图片: {comment_img_count}张 (保存到 comments 文件夹)", "INFO")
                            data['comment_images_count'] = comment_img_count
            
            return data
            
        except Exception as e:
            self.log(f"提取数据失败: {e}", "ERROR")
            return None
    
    def _extract_single_comment(self, item, existing_contents: set) -> Optional[Dict]:
        """提取单条评论"""
        exclude_words = {'关注', '点赞', '收藏', '分享', '复制', '举报', '回复', '查看', '展开', '赞', '条评论', '说点什么', '取消', '发送'}
        
        try:
            name_el = item.ele('css:.name, .user-name, .author-name, .nickname', timeout=0.1)
            name = (name_el.text if name_el else "").strip()
            
            content_el = item.ele('css:.content, .comment-content, .note-text', timeout=0.1)
            content = (content_el.text if content_el else "").strip()
            
            if not content or len(content) <= 3 or len(content) >= 500:
                return None
            if content in existing_contents:
                return None
            if content in exclude_words or content.isdigit():
                return None
            
            time_el = item.ele('css:.date, .time, .info .date, .comment-time', timeout=0.1)
            time_text = (time_el.text if time_el else "").strip()
            
            ip_text = ""
            try:
                ip_el = item.ele('css:.ip, .location, .region, .area', timeout=0.1)
                if ip_el:
                    ip_text = ip_el.text.strip()
                else:
                    if time_text and " " in time_text:
                        parts = time_text.split()
                        if len(parts) >= 2:
                            last_part = parts[-1]
                            if not any(c in last_part for c in ['前', '天', '小时', '分钟', '秒', '月', '年']):
                                ip_text = last_part
                                time_text = " ".join(parts[:-1])
            except Exception:
                pass
            
            like_count = 0
            try:
                like_el = item.ele('css:.like-count, .likes, .like-num, .zan-count, [class*="like"] span', timeout=0.1)
                if like_el:
                    like_text = like_el.text.strip()
                    if like_text:
                        if '万' in like_text:
                            like_count = int(float(like_text.replace('万', '')) * 10000)
                        elif like_text.isdigit():
                            like_count = int(like_text)
            except Exception:
                pass
            
            has_image = False
            comment_images = []
            try:
                imgs = item.eles('css:img.comment-img, .comment-image img, .comment-pic img', timeout=0.1)
                if imgs:
                    has_image = True
                    for img in imgs[:3]:
                        src = img.attr('src') or ""
                        if src and 'avatar' not in src.lower() and len(src) > 30:
                            comment_images.append(src)
            except Exception:
                pass
            
            return {
                'author': name or "匿名用户",
                'content': content,
                'time': time_text,
                'ip': ip_text,
                'likes': like_count,
                'has_image': has_image,
                'images': comment_images
            }
        except Exception:
            return None
    
    def _extract_comments(self, page) -> List[Dict]:
        """提取评论内容"""
        comments = []
        max_count = self.config.comments_count
        existing_contents = set()
        
        try:
            comment_items = page.eles('css:.comment-item, .parent-comment, .comment-inner', timeout=0.5)
            
            for item in comment_items:
                if len(comments) >= max_count:
                    break
                comment = self._extract_single_comment(item, existing_contents)
                if comment:
                    comments.append(comment)
                    existing_contents.add(comment['content'])
            
            if len(comments) < max_count:
                try:
                    comments_container = page.ele('css:.comments-container, .comments-el, .note-scroller', timeout=0.3)
                    if comments_container:
                        comments_container.scroll.to_bottom()
                        time.sleep(0.3)
                        
                        new_items = page.eles('css:.comment-item, .comment-inner', timeout=0.3)
                        for item in new_items:
                            if len(comments) >= max_count:
                                break
                            comment = self._extract_single_comment(item, existing_contents)
                            if comment:
                                comments.append(comment)
                                existing_contents.add(comment['content'])
                except Exception:
                    pass
                    
        except Exception:
            pass
        
        return comments
    
    def save_data(self, data, keyword):
        """保存数据"""
        os.makedirs("data", exist_ok=True)
        timestamp = int(time.time())
        
        # 预处理数据
        processed_data = []
        for item in data:
            processed_item = item.copy()
            
            if 'comments' in processed_item and isinstance(processed_item['comments'], list):
                comments = processed_item['comments']
                if comments and isinstance(comments[0], dict):
                    comment_strs = []
                    for i, c in enumerate(comments, 1):
                        author_name = c.get('author', '') or '匿名'
                        content = c.get('content', '')
                        time_str = c.get('time', '')
                        ip_str = c.get('ip', '')
                        likes = c.get('likes', 0)
                        has_image = c.get('has_image', False)
                        
                        if content:
                            info_parts = [f"@{author_name}"]
                            if ip_str:
                                info_parts.append(ip_str)
                            if time_str:
                                info_parts.append(time_str)
                            if likes > 0:
                                info_parts.append(f"❤️{likes}")
                            if has_image:
                                info_parts.append("[含图]")
                            
                            info = " | ".join(info_parts)
                            comment_strs.append(f"[{i}] {info}: {content}")
                    processed_item['comments'] = '\n'.join(comment_strs)
                else:
                    processed_item['comments'] = '\n'.join(str(c) for c in comments)
            
            if 'tags' in processed_item and isinstance(processed_item['tags'], list):
                processed_item['tags'] = ', '.join(processed_item['tags'])
            
            if 'image_urls' in processed_item and isinstance(processed_item['image_urls'], list):
                processed_item['image_urls'] = ' | '.join(processed_item['image_urls'])
            
            if 'local_images' in processed_item and isinstance(processed_item['local_images'], list):
                processed_item['local_images'] = ' | '.join(processed_item['local_images'])
            
            processed_data.append(processed_item)
        
        df = pd.DataFrame(processed_data)
        
        column_mapping = {
            'keyword': '搜索关键词', 'title': '标题', 'author': '作者',
            'content': '正文内容', 'tags': '标签', 'publish_time': '发布时间',
            'ip_region': 'IP地区', 'like_count': '点赞数', 'collect_count': '收藏数',
            'comment_count': '评论数', 'comments': '评论内容', 'note_type': '笔记类型',
            'note_link': '笔记链接', 'note_id': '笔记ID', 'video_url': '视频链接',
            'image_urls': '图片链接', 'image_count': '图片数量',
            'local_images': '本地图片路径', 'local_video': '本地视频路径',
        }
        
        df = df.rename(columns=column_mapping)
        
        ext = self.config.export_format
        safe_keyword = keyword.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        filename = f"data/搜索结果_{safe_keyword}_{timestamp}.{ext}"
        
        if ext == "xlsx":
            df.to_excel(filename, index=False)
        elif ext == "csv":
            df.to_csv(filename, index=False, encoding='utf-8-sig')
        elif ext == "json":
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        if hasattr(self, 'current_crawl_dir') and self.current_crawl_dir:
            try:
                os.makedirs(self.current_crawl_dir, exist_ok=True)
                crawl_file = f"{self.current_crawl_dir}/搜索结果.{ext}"
                if ext == "xlsx":
                    df.to_excel(crawl_file, index=False)
                elif ext == "csv":
                    df.to_csv(crawl_file, index=False, encoding='utf-8-sig')
                elif ext == "json":
                    with open(crawl_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        
        return filename
