"""
----------------------------------------------------------------
File name:                  storage.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                网络请求模块
----------------------------------------------------------------

Changed history:            网络请求模块: 代理源
----------------------------------------------------------------
"""

import aiohttp
from lxml import etree
from typing import Optional, Any


class WebRequest:
    """
    网络请求模块，使用 aiohttp 实现
    """
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def get(self, url: str, timeout: float = 10, headers: Optional[dict] = None) -> Any:
        """
        通用网络请求方法

        Args:
            url: 请求地址
            timeout: 超时时间
            headers: 请求头

        Returns:
            requests响应对象，附加了tree属性
        """
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/91.0.4472.124 Safari/537.36"
        }
        headers = headers or default_headers

        try:
            async with self.session.get(url, headers=headers, timeout=timeout) as response:
                # html 解析
                text = await response.text()  # 异步获取 text 响应
                tree = etree.HTML(text)  # lxml 解析
                response.tree = tree
                return response
        except Exception as e:
            print(f"Request failed: {e}")
            return None

    async def close(self):
        """
        关闭 aiohttp session
        """
        await self.session.close()
