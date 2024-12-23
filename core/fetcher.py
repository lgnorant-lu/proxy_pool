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

# import json
import asyncio
from typing import List, AsyncGenerator
from proxy_pool.utils.web_request import WebRequest
from proxy_pool.models.proxy_model import ProxyModel
from proxy_pool.utils.logger import setup_logger
from proxy_pool.core.validator import ProxyValidator


class ProxyFetcher:
    def __init__(self):
        self.logger = setup_logger()
        self.web_request = WebRequest()
        self.validator = ProxyValidator()

    async def freeProxy01(self) -> AsyncGenerator[str, None]:
        """
        66代理 http://www.66ip.cn/
        """
        url = "http://www.66ip.cn/"
        try:
            resp = await self.web_request.get(url, timeout=10)
            if resp is not None:  # 确保响应不为 None
                for tr in resp.tree.xpath("(//table)[3]//tr"):
                    ip = "".join(tr.xpath("./td[1]/text()")).strip()
                    port = "".join(tr.xpath("./td[2]/text()")).strip()
                    yield f"{ip}:{port}"
            else:
                self.logger.error("没有获取到有效的响应，返回 None")
        except Exception as e:
            self.logger.error(f"66代理获取失败: {e}")

    async def freeProxy02(self) -> AsyncGenerator[str, None]:
        """
        代理列表 http://proxy.list-unique.net/
        """
        url = "http://proxy.list-unique.net/"
        try:
            resp = await self.web_request.get(url, timeout=10)
            if resp is not None:
                for tr in resp.tree.xpath("//table//tr")[1:]:
                    ip = tr.xpath("./td[1]/text()")[0].strip()
                    port = tr.xpath("./td[2]/text()")[0].strip()
                    yield f"{ip}:{port}"
        except Exception as e:
            self.logger.error(f"代理列表获取失败: {e}")

    async def freeProxy03(self) -> AsyncGenerator[str, None]:
        """
        IP海 http://www.iphai.com/
        "http://www.iphai.com/free/ng",
        "http://www.iphai.com/free/np"
        """
        urls = ["http://ip.iphai.cn/ip.php", "http://ip.ipadsl.cn/ip.php"]
        for url in urls:
            try:
                resp = await self.web_request.get(url, timeout=10)
                if resp is not None:
                    for tr in resp.tree.xpath("//table//tr")[1:]:
                        ip = tr.xpath("./td[4]/text()")[0].strip()
                        port = tr.xpath("./td[6]/text()")[0].strip()
                        yield f"{ip}:{port}"
            except Exception as e:
                self.logger.error(f"IP海代理获取失败: {e}")

    async def freeProxy06(self) -> AsyncGenerator[str, None]:
        """
        快代理 https://www.kuaidaili.com
        """
        urls = [
            "http://www.kuaidaili.com/free/inha/",
            "http://www.kuaidaili.com/free/fps/",
        ]
        for url in urls:
            try:
                resp = await self.web_request.get(url, timeout=10)
                for tr in resp.tree.xpath("//table[@id='list']/tbody//tr")[1:]:
                    ip = tr.xpath("./td[1]/text()")[0].strip()
                    port = tr.xpath("./td[2]/text()")[0].strip()
                    yield f"{ip}:{port}"
            except Exception as e:
                self.logger.error(f"快代理获取失败: {e}")

    async def freeProxy04(self) -> AsyncGenerator[str, None]:
        """
        站大爷 https://www.zdaye.com/dayProxy.html
        """
        url = "https://www.zdaye.com/dayProxy.html"
        try:
            html_tree = await self.web_request.get(url, verify=False)
            latest_page_time = html_tree.xpath(
                "//span[@class='thread_time_info']/text()"
            )[0].strip()

            from datetime import datetime

            interval = datetime.now() - datetime.strptime(
                latest_page_time, "%Y/%m/%d %H:%M:%S"
            )

            # 只采集 5 分钟内的更新
            if interval.seconds < 300:
                target_url = (
                    "https://www.zdaye.com/"
                    + html_tree.xpath("//h3[@class='thread_title']/a/@href")[0].strip()
                )

                while target_url:
                    _tree = await self.web_request.get(target_url, verify=False)
                    # 代理获取
                    for tr in _tree.xpath("//table//tr"):
                        ip = "".join(tr.xpath("./td[1]/text()")).strip()
                        port = "".join(tr.xpath("./td[2]/text()")).strip()
                        yield "%s:%s" % (ip, port)

                    # 翻页
                    next_page = _tree.xpath(
                        "//div[@class='page']/a[@title='下一页']/@href"
                    )
                    target_url = (
                        "https://www.zdaye.com/" + next_page[0].strip()
                        if next_page
                        else False
                    )

                    # 增加异步 sleep 避免高频请求
                    await asyncio.sleep(5)
        except Exception as e:
            self.logger.error(f"站大爷代理获取失败: {e}")

    async def freeProxy05(self) -> AsyncGenerator[str, None]:
        """
        58 代理 https://www.58.com/
        """
        url = (
            "https://www.58.com/changeip/?stype=1&changeipnum=5&isp=0&protocol=2&city=0&yys=0&port=1&time=1&ts=1"
            "&fast=0&order=2&filetype=0&z=0&ip=0&area=0&region=0&cityid=0&duan=0&rt=40"
        )
        try:
            resp = await self.web_request.get(url, timeout=10)
            pattern = re.compile(r"(?P<ip>\d+\.\d+\.\d+\.\d+):(?P<port>\d+)")
            matches = pattern.findall(resp.text)
            for ip, port in matches:
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
                raw_proxies = []
                async for proxy_str in method():
                    # 转换 str 为 ProxyModel
                    proxy = self.parse_proxy(proxy_str)
                    raw_proxies.append(proxy)
                    # 批量验证代理
                    valid_proxies = await self.validator.validate_proxy(raw_proxies)
                    all_proxies.extend(valid_proxies)
            except Exception as e:
                self.logger.error(f"代理获取方法 {method.__name__} 失败: {e}")

        # # 转换为 ProxyModel  pass 掉了, 二代于, validate_proxy 修改后
        # proxy_models = self.parse_proxy_list(all_proxies)

        self.logger.info(f"获取代理 {len(all_proxies)} 个")
        return all_proxies

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
            "zdaye.com": "站大爷代理",
            "xicidaili.com": "西刺代理",
        }

        for domain, name in sources.items():
            if domain in proxy_str:
                return name
        return "未知源"

    def parse_proxy_list(self, proxies: List[str]) -> List[ProxyModel]:
        """
        将代理字符串列表解析为 ProxyModel 列表

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

    def parse_proxy(self, proxy: str) -> ProxyModel:
        """
        将代理字符串解析为 ProxyModel

        Args:
            proxy: 代理字符串

        Returns:
            代理模型
        """
        # 预检查字符串格式是否为 "ip:port" 格式
        try:
            match = re.match(r"^(?P<ip>\d+\.\d+\.\d+\.\d+):(?P<port>\d+)$", proxy)
            if match:
                # 格式正确返回
                return ProxyModel(
                    ip=match.group("ip"),
                    port=int(match.group("port")),
                    source=self._get_source_name(proxy),
                )
            else:
                # 非法格式返回
                proxy_model_none = ProxyModel(ip="0.0.0.0", port=0, source="未知来源")
                return proxy_model_none
        except ValueError as e:
            # 端口转换失败
            self.logger.warning(f"解析代理失败: {proxy}, 错误: {e}")
            proxy_model = ProxyModel(
                ip="0.0.0.0",
                port=0,
                source="未知来源",
            )
            return proxy_model
        except Exception as e:
            self.logger.warning(f"解析代理失败: {proxy}, {e}")
            # 解析失败返回
            proxy_model_none = ProxyModel(
                ip="0.0.0.0",
                port=0,
                source="未知来源",
            )
            return proxy_model_none


if __name__ == '__main__':
    async def main():
        # 创建 ProxyFetcher 实例
        fetcher = ProxyFetcher()

        # 调用 fetch_proxies 获取代理
        proxies = await fetcher.fetch_proxies()

        for proxy in proxies:
            print(f"抓取到代理: {proxy}")


    # 运行异步主函数
    asyncio.run(main())
