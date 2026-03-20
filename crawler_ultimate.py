# -*- coding: utf-8 -*-
"""
小红书爬虫终极版 v5.1 - 兼容入口
===================
此文件保留为向后兼容的启动入口。
实际代码已重构到 redbook_crawler/ 包中。

运行方式：
  python crawler_ultimate.py
或：
  python -m redbook_crawler
"""

from redbook_crawler.gui.app import CrawlerApp

if __name__ == '__main__':
    app = CrawlerApp()
    app.run()
