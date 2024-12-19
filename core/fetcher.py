"""
----------------------------------------------------------------
File name:                  storage.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理获取模块
----------------------------------------------------------------

Changed history:            代理获取模块: 代理源
----------------------------------------------------------------
"""

import re
import json
from typing import List, AsyncGenerator
from ..utils.web_request import WebRequest
from ..models.proxy_model import ProxyModel
from ..utils.logger import setup_logger


class ProxyFetcher:
    def __init__(self):
        self.logger = setup_logger()
        self.web_request = WebRequest()

    async def freeProxy01(self) -> AsyncGenerator[str, None]:
        """
        66代理 http://www.66ip.cn/
        """
        url = "http://www.66ip.cn/"
        try:
            resp = await self.web_request.get(url, timeout=10)
            for i, tr in enumerate(resp.tree.xpath("(//table)[3]//tr")):
                if i > 0:
                    ip = "".join(tr.xpath("./td[1]/text()")).strip()
                    port = "".join(tr.xpath("./td[2]/text()")).strip()
                    yield f"{ip}:{port}"
        except Exception as e:
            self.logger.error(f"66代理获取失败: {e}")

    async def freeProxy02(self) -> AsyncGenerator[str, None]:
        """
        代理列表 http://proxy.list-unique.net/
        """
        url = "http://proxy.list-unique.net/"
        try:
            resp = await self.web_request.get(url, timeout=10)
            for tr in resp.tree.xpath("//table//tr")[1:]:
                ip = tr.xpath("./td[1]/text()")[0].strip()
                port = tr.xpath("./td[2]/text()")[0].strip()
                yield f"{ip}:{port}"
        except Exception as e:
            self.logger.error(f"代理列表获取失败: {e}")

    async def freeProxy03(self) -> AsyncGenerator[str, None]:
        """
        IP海 http://www.iphai.com/
        """
        urls = ["http://www.iphai.com/free/ng", "http://www.iphai.com/free/np"]
        for url in urls:
            try:
                resp = await self.web_request.get(url, timeout=10)
                async for tr in resp.tree.xpath("//table//tr")[1:]:
                    ip = tr.xpath("./td[1]/text()")[0].strip()
                    port = tr.xpath("./td[2]/text()")[0].strip()
                    yield f"{ip}:{port}"
            except Exception as e:
                self.logger.error(f"IP海代理获取失败: {e}")

    async def freeProxy04(self) -> AsyncGenerator[str, None]:
        """
        西刺代理 https://www.xicidaili.com/
        """
        url = "https://www.xicidaili.com/nn/"
        try:
            resp = await self.web_request.get(url, timeout=10)
            async for tr in resp.tree.xpath("//table[@id='ip_list']//tr")[1:]:
                ip = tr.xpath("./td[2]/text()")[0].strip()
                port = tr.xpath("./td[3]/text()")[0].strip()
                yield f"{ip}:{port}"
        except Exception as e:
            self.logger.error(f"西刺代理获取失败: {e}")

    async def freeProxy05(self) -> AsyncGenerator[str, None]:
        """快代理 https://www.kuaidaili.com"""
        url = "http://www.kuaidaili.com/free/inha/"
        try:
            resp = await self.web_request.get(url, timeout=10)
            async for tr in resp.tree.xpath("//table[@id='list']/tbody//tr")[1:]:
                ip = tr.xpath("./td[2]/text()")[0].strip()
                port = tr.xpath("./td[3]/text()")[0].strip()
                yield f"{ip}:{port}"
        except Exception as e:
            self.logger.error(f"快代理获取失败: {e}")

    async def freeProxy06(self) -> AsyncGenerator[str, None]:
        """58 代理 https://www.58.com/"""
        url = "https://www.58.com/changeip/?stype=1&changeipnum=5&isp=0&protocol=2&city=0&yys=0&port=1&time=1&ts=1&fast=0&order=2&filetype=0&z=0&ip=0&area=0&region=0&cityid=0&duan=0&rt=40"
        try:
            resp = await self.web_request.get(url, timeout=10)
            pattern = re.compile(r"(?P<ip>\d+\.\d+\.\d+\.\d+):(?P<port>\d+)")
            matches = pattern.findall(resp.text)
            async for ip, port in matches:
                yield f"{ip}:{port}"
        except Exception as e:
            self.logger.error(f"58 代理获取失败: {e}")

    async def fetch_proxies(self) -> List[ProxyModel]:
        """
        获取所有代理源的代理

        Returns:
            代理模型列表
        """
        # 所有代理获取方法
        proxy_methods = [
            self.freeProxy01,
            self.freeProxy02,
            self.freeProxy03,
            self.freeProxy04,
        ]

        # 收集所有代理
        all_proxies = []
        for method in proxy_methods:
            try:
                async for proxy in method():
                    all_proxies.append(proxy)
            except Exception as e:
                self.logger.error(f"代理获取方法 {method.__name__} 失败: {e}")

        # 转换为 ProxyModel
        proxy_models = self._parse_proxy_list(all_proxies)

        self.logger.info(f"获取代理 {len(proxy_models)} 个")
        return proxy_models

    def _parse_proxy_list(self, proxies: List[str]) -> List[ProxyModel]:
        """
        将代理字符串解析为ProxyModel

        Args:
            proxies: 代理字符串列表

        Returns:
            代理模型列表
        """
        proxy_models = []
        for proxy_str in proxies:
            try:
                ip, port = proxy_str.split(":")
                proxy = ProxyModel(
                    ip=ip.strip(),
                    port=int(port.strip()),
                    source=self._get_source_name(proxy_str),
                )
                proxy_models.append(proxy)
            except Exception as e:
                self.logger.warning(f"解析代理失败: {proxy_str}, {e}")
        return proxy_models

    @staticmethod
    def _get_source_name(proxy_str: str) -> str:
        """
        根据代理获取来源名称

        Args:
            proxy_str: 代理字符串

        Returns:
            来源名称
        """
        sources = {
            "66ip.cn": "66IP代理",
            "proxy.list-unique.net": "唯一代理列表",
            "iphai.com": "IP海代理",
            "xicidaili.com": "西刺代理",
        }

        for domain, name in sources.items():
            if domain in proxy_str:
                return name
        return "未知源"
