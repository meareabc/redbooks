# -*- coding: utf-8 -*-
"""python -m redbook_crawler 入口"""

from .gui.app import CrawlerApp

if __name__ == '__main__':
    app = CrawlerApp()
    app.run()
