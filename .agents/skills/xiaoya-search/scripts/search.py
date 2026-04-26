#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小雅影视库搜索脚本 - 内外网自适应版 (纯净链接)
"""
import requests
import sys
import os
import re
from urllib.parse import quote

def search_xiaoya(keyword):
    # 路径配置
    INTRA_URL = "http://192.168.100.99:5678"
    EXTRA_URL = "https://xiaoya.luoyujun.eu.org"
    
    # 尝试顺序：优先内网，失败则回退公网
    targets = [INTRA_URL, EXTRA_URL]
    
    encoded_keyword = quote(keyword)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1"
    }

    # 如果有 Token，搜索请求依然带上以确保能拿到 HTML
    ALIST_TOKEN = os.environ.get('ALIST_TOKEN', '')
    if ALIST_TOKEN:
        headers["Authorization"] = f"Bearer {ALIST_TOKEN}"

    for base_url in targets:
        search_url = f"{base_url}/search?box={encoded_keyword}&url=&type=video"
        headers["Referer"] = f"{base_url}/"
        
        try:
            timeout = 3 if base_url == INTRA_URL else 10
            response = requests.get(search_url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                html_content = response.text
                pattern = r'<a href=([^>]+)>([^<]+)</a>'
                matches = re.findall(pattern, html_content)
                
                results = []
                for href, text in matches:
                    if href.startswith('/') and not href.startswith('//') and text != "返回小雅首页":
                        # 返回纯净的公网链接，不携带敏感 Token
                        full_link = f"{EXTRA_URL}{href}"
                        results.append({"name": text, "url": full_link})
                
                if results:
                    return results, base_url
        except Exception:
            continue
            
    return [], None

def main():
    if len(sys.argv) < 2:
        print("用法: python search.py <搜索关键词>")
        return

    search_keyword = sys.argv[1]
    results, used_url = search_xiaoya(search_keyword)
    
    if results:
        mode_str = "🏠 内网模式" if "192.168" in used_url else "🌍 公网模式"
        print(f"✅ [{mode_str}] 找到 {len(results)} 个匹配项:")
        for i, item in enumerate(results, 1):
            print(f"{i}. [{item['name']}]({item['url']})")
    else:
        print("📭 未找到匹配的影视资源。")

if __name__ == "__main__":
    main()
