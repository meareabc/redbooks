# -*- coding: utf-8 -*-
"""浏览器管理模块 - 启动、登录检测、Cookie同步、验证弹窗检测"""

import os
import time
import threading
import tkinter as tk
from tkinter import messagebox

from DrissionPage import ChromiumPage, ChromiumOptions


def create_browser(log_func=None):
    """创建并启动浏览器实例"""
    try:
        user_data_dir = os.path.abspath("data/browser_profile")
        os.makedirs(user_data_dir, exist_ok=True)
        
        co = ChromiumOptions()
        co.set_user_data_path(user_data_dir)
        co.set_argument('--no-first-run')
        co.set_argument('--no-default-browser-check')
        
        page = ChromiumPage(co)
        if log_func:
            log_func("浏览器启动成功", "SUCCESS")
        return page
    except Exception as e:
        if log_func:
            log_func(f"浏览器启动失败: {e}", "ERROR")
        return None


def check_login(page) -> bool:
    """检查是否已登录（优先检测登录弹窗）"""
    try:
        # ===== 第一优先级：检查是否有登录弹窗（未登录标志）=====
        qrcode = page.ele('xpath://img[contains(@src, "qrcode")]', timeout=0.3)
        if qrcode:
            return False
        
        login_hint = page.ele('xpath://span[contains(text(), "登录后查看") or contains(text(), "扫码登录") or contains(text(), "手机号登录")]', timeout=0.3)
        if login_hint:
            return False
        
        close_icon = page.ele('css:.close-icon', timeout=0.2)
        if close_icon:
            try:
                parent = close_icon.parent()
                if parent:
                    parent_text = parent.text or ""
                    if "登录" in parent_text or "扫码" in parent_text:
                        return False
            except Exception:
                pass
        
        login_btn = page.ele('css:.login-btn, button.login-btn', timeout=0.2)
        if login_btn:
            btn_text = login_btn.text or ""
            if "登录" in btn_text:
                return False
        
        # ===== 第二优先级：检查已登录标志 =====
        user_profile = page.ele('css:.user.side-bar-component a[href*="/user/profile/"]', timeout=0.3)
        if user_profile:
            return True
        
        avatar = page.ele('css:.side-bar .reds-avatar', timeout=0.2)
        if avatar:
            return True
        
        try:
            sidebar = page.ele('css:.side-bar', timeout=0.2)
            if sidebar:
                text = sidebar.text or ""
                if "我" in text and "发现" in text and "登录" not in text:
                    return True
                if "登录" in text:
                    return False
        except Exception:
            pass
        
        return False
        
    except Exception:
        return False


def check_verification(page) -> bool:
    """检测是否出现验证弹窗（滑块验证/图片验证码/行为验证）
    
    Returns:
        True 如果检测到验证弹窗
    """
    try:
        selectors = [
            'css:.captcha-container',
            'css:[class*="captcha"]',
            'css:[class*="verify"]',
            'css:.slider-container',
            'css:#captcha',
            'css:.geetest_panel',
            'css:.tcaptcha_transform',
            'xpath://div[contains(text(),"验证")]',
            'xpath://div[contains(text(),"滑动")]',
            'xpath://div[contains(text(),"请完成安全验证")]',
            'xpath://div[contains(text(),"点击按住滑块")]',
        ]
        for sel in selectors:
            try:
                el = page.ele(sel, timeout=0.3)
                if el:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def wait_for_login(page, root, log_func=None, config=None, cookie_mgr=None):
    """等待用户登录
    
    Args:
        page: 浏览器页面
        root: tkinter根窗口
        log_func: 日志函数
        config: 配置对象
        cookie_mgr: Cookie管理器
    
    Raises:
        InterruptedError: 用户取消
    """
    if log_func:
        log_func("请在浏览器中完成登录", "WARNING")
    
    login_event = threading.Event()
    cancelled = [False]
    
    def show_dialog():
        result = messagebox.askokcancel(
            "等待登录",
            "请在浏览器中完成登录\n\n登录完成后点击【确定】\n点击【取消】停止爬取"
        )
        if not result:
            cancelled[0] = True
        login_event.set()
    
    root.after(0, show_dialog)
    login_event.wait()
    
    if cancelled[0]:
        raise InterruptedError("用户取消")
    
    # 登录完成后立即保存Cookie
    if config and config.save_cookies and cookie_mgr:
        try:
            time.sleep(1)
            if cookie_mgr.save(page):
                if log_func:
                    log_func("Cookie已保存，下次可自动登录", "SUCCESS")
        except Exception as e:
            if log_func:
                log_func(f"Cookie保存失败: {e}", "WARNING")


def wait_for_verification(page, root, log_func=None, cookie_mgr=None):
    """等待用户完成验证弹窗
    
    Args:
        page: 浏览器页面  
        root: tkinter根窗口
        log_func: 日志函数
        cookie_mgr: Cookie管理器
    
    Returns:
        True 如果用户完成验证，False 如果用户取消
    """
    if log_func:
        log_func("检测到验证弹窗，等待用户完成验证...", "WARNING")
    
    verify_event = threading.Event()
    cancelled = [False]
    
    def show_dialog():
        result = messagebox.askokcancel(
            "验证弹窗",
            "检测到安全验证弹窗！\n\n"
            "请在浏览器中完成验证（如滑块验证等）\n\n"
            "完成后点击【确定】继续爬取\n"
            "点击【取消】暂停当前任务"
        )
        if not result:
            cancelled[0] = True
        verify_event.set()
    
    root.after(0, show_dialog)
    verify_event.wait()
    
    if cancelled[0]:
        return False
    
    # 验证完成后更新Cookie
    if cookie_mgr:
        try:
            time.sleep(0.5)
            cookie_mgr.save(page)
            if log_func:
                log_func("验证完成，Cookie已更新", "SUCCESS")
        except Exception:
            pass
    
    return True


def sync_browser_cookies(page, downloader, log_func=None):
    """将浏览器Cookie同步到下载器"""
    try:
        cookies = page.cookies()
        if cookies:
            downloader.set_cookies(cookies)
            if log_func:
                log_func(f"  已同步 {len(cookies)} 个Cookie到下载器", "INFO")
    except Exception as e:
        if log_func:
            log_func(f"  同步Cookie失败: {e}", "WARNING")
