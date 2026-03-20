# -*- coding: utf-8 -*-
"""版本信息和可选依赖检测"""

# 版本信息
VERSION = "5.1"
APP_NAME = f"小红书爬虫终极版 v{VERSION}"

# 可选依赖检测
try:
    import customtkinter as ctk
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

try:
    from wordcloud import WordCloud
    import jieba
    HAS_WORDCLOUD = True
except Exception:
    HAS_WORDCLOUD = False

try:
    from docx import Document
    from docx.shared import Inches
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False
