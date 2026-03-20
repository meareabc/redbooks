# -*- coding: utf-8 -*-
"""工具函数集合"""

import re
from typing import List


def parse_num(text) -> int:
    """解析数字（支持万/k单位）"""
    if not text:
        return 0
    text = str(text).strip().lower()
    try:
        if '万' in text:
            return int(float(text.replace('万', '')) * 10000)
        if 'k' in text:
            return int(float(text.replace('k', '')) * 1000)
        return int(re.sub(r'[^\d]', '', text) or 0)
    except Exception:
        return 0


def is_emoji_image(url: str) -> bool:
    """检测是否是表情包图片"""
    if not url:
        return False
    url_lower = url.lower()
    
    # 1. URL关键词检测
    emoji_keywords = [
        'emoji', 'sticker', 'emote', 'emoticon', 'expression',
        'spectrum', 'meme', 'gif', 'animated', 
        '/e/', '/em/', '/stk/', '/stick/'
    ]
    for kw in emoji_keywords:
        if kw in url_lower:
            return True
    
    # 2. 小红书表情包特征：通常是小尺寸图片
    size_patterns = [
        r'/w/(\d+)',
        r'/h/(\d+)', 
        r'imageview2/\d/w/(\d+)',
        r'!nd_dft_wlteh_webp_(\d+)',
        r'_(\d+)x(\d+)\.',
    ]
    for pattern in size_patterns:
        match = re.search(pattern, url_lower)
        if match:
            try:
                size = int(match.group(1))
                if size <= 300:
                    return True
            except Exception:
                pass
    
    # 3. 检测表情包CDN特征
    emoji_cdn_patterns = [
        'fe-static',
        '/emoji/',
        'spectrum.xhscdn',
        'sticker.xhscdn',
        'ci.xiaohongshu.com/spectrum',
    ]
    for pattern in emoji_cdn_patterns:
        if pattern in url_lower:
            return True
    
    # 4. 检测非常短的图片URL（通常是内联表情）
    if len(url) < 100:
        return True
    
    # 5. 检测URL中没有常规图片路径特征
    normal_patterns = ['sns-img', 'sns-webpic', 'note', 'traceId']
    has_normal_pattern = any(p in url_lower for p in normal_patterns)
    if not has_normal_pattern and 'xhscdn' in url_lower:
        return True
        
    return False


def filter_live_images(image_urls: list) -> list:
    """过滤Live图（动态图片），只保留一张静态版本
    
    Live图特征：
    1. URL中包含 'live' 关键字
    2. 同一张图片有静态和动态两个版本
    3. URL结构相似，只是路径或参数不同
    """
    if not image_urls:
        return []
    
    # 去重
    unique_urls = list(dict.fromkeys(image_urls))
    
    def extract_image_id(url):
        """提取图片的核心ID"""
        base = url.split('?')[0]
        base = re.sub(r'![^/]+$', '', base)
        filename = base.split('/')[-1]
        filename = re.sub(r'\.(jpg|jpeg|png|webp|gif|heic)$', '', filename, flags=re.IGNORECASE)
        filename = re.sub(r'_live\d*$', '', filename)
        filename = re.sub(r'-live\d*$', '', filename)
        id_match = re.search(r'([a-z0-9]{20,})', filename, re.IGNORECASE)
        if id_match:
            return id_match.group(1).lower()
        return filename.lower()
    
    def is_live_url(url):
        """判断是否是Live图URL"""
        url_lower = url.lower()
        return 'live' in url_lower or '/live/' in url_lower
    
    # 按图片ID分组
    url_groups = {}
    for url in unique_urls:
        img_id = extract_image_id(url)
        if img_id not in url_groups:
            url_groups[img_id] = []
        url_groups[img_id].append(url)
    
    # 每组只保留一张
    filtered = []
    for img_id, urls in url_groups.items():
        if len(urls) == 1:
            filtered.append(urls[0])
        else:
            best = None
            for url in urls:
                if not is_live_url(url):
                    url_lower = url.lower()
                    if best is None:
                        best = url
                    elif '.jpg' in url_lower or '.png' in url_lower:
                        best = url
            
            if best is None:
                best = urls[0]
            
            filtered.append(best)
    
    return filtered


def is_search_recommend_card(elem) -> bool:
    """检测是否是'大家都在搜'推荐卡片"""
    try:
        text = elem.text or ""
        
        if "大家都在搜" in text:
            return True
        if "热门搜索" in text:
            return True
        
        html = elem.html or ""
        if "search-recommend" in html.lower():
            return True
        
        try:
            links = elem.eles('css:a')
            cover = elem.ele('css:a.cover, .cover', timeout=0.1)
            if len(links) > 3 and not cover:
                return True
        except Exception:
            pass
                
    except Exception:
        pass
    return False
