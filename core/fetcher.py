"""
----------------------------------------------------------------
File name:                  fetcher+.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理获取模块
----------------------------------------------------------------

Changed history:            代理获取模块: 代理源
                            2024/12/26: 优化并发货区 / 日志, 增加源 / 代理评估 / 重试机制;
----------------------------------------------------------------
"""

import asyncio
import aiohttp
import re
import sys
from lxml import etree
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Set, Optional, AsyncGenerator
from charset_normalizer import from_bytes

from proxy_pool.core.validator import ProxyValidator
from proxy_pool.models.proxy_model import ProxyModel
from proxy_pool.utils.config import ProxyConfig
from proxy_pool.utils.logger import setup_logger
from proxy_pool.utils.web_request import WebRequest


@dataclass
class ProxySource:
    """ 代理源配置数据 """

    name: str                                       # 代理源名称
    urls: List[str]                                 # 代理源 url 列表
    enabled: bool = True                            # 总阀
    weight: int = 1                                 # 优先级权重
    timeout: int = 10                               # 请求超时时间 / s
    interval: int = 300                             # 抓取间隔 / s
    retry_times: int = 3                            # 重试次数
    retry_delay: int = 1                            # 重试延迟 / s
    last_fetch_time: Optional[datetime] = None      # 上次抓取时间
    headers: dict = field(default_factory=dict)     # 自定义请求头
    proxies: dict = field(default_factory=dict)     # 代理设置
    verify_ssl: bool = True                         # 验证 ssl 证书

    def __post_init__(self):
        """ 初始化后的处理 """
        # 列表过滤
        if isinstance(self.urls, str):
            self.urls = [self.urls]

        # 默认请求头设置
        if not self.headers:
            self.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/96.0.4664.110 Safari/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                # "Referer": "https://www.zdaye.com/",
            }

    def can_catch(self) -> bool:
        """ 有效性检查 """
        if not self.enabled:
            return False

        if not self.last_fetch_time:
            return True

        # 检查间隔时间
        time_passed = (datetime.now() - self.last_fetch_time).total_seconds()
        return time_passed >= self.interval

    def update_fetch_time(self):
        """ 更新抓取时间 """
        self.last_fetch_time = datetime.now()


class ProxySourceBase(ABC):
    """ 代理原基类 """

    def __init__(self, source_config: ProxySource):
        self.web_request = None
        self.config = source_config
        self.logger = setup_logger(f"proxy_source.{source_config.name}")

    def set_web_request(self, web_request: WebRequest):
        """ 设置 web_request 实例 """
        self.web_request = web_request

    async def fetch(self, session: aiohttp.ClientSession) -> AsyncGenerator[str, None]:
        """ 获取代理的基础方法 """
        try:
            async for proxy in self._fetch(session):
                yield proxy
        except Exception as e:
            self.logger.error(f"{self.name} 获取代理失败: {str(e)}")

    @abstractmethod
    async def _fetch(self, session: aiohttp.ClientSession) -> AsyncGenerator[str, None]:
        """ 获取代理的抽象方法 """
        yield  # 基础实现

    @property
    def name(self) -> str:
        return self.config.name

    async def is_available(self) -> bool:
        """ 源有效性检查 """
        if not self.web_request:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                for url in self.config.urls:
                    try:
                        async with session.get(
                            url,
                            timeout=self.config.timeout,
                            verify_ssl=self.config.verify_ssl
                        ) as response:
                            if response.status == 200:
                                return True
                    except Exception as e:
                        self.logger.error(f"可用性检查失败: {e}")
                        continue
                return False
        except Exception as e:
            self.logger.error(f"会话获取失败: {e}")
            return False


class ProxyFetcher:
    """ 代理获取器 """

    def __init__(self, config: ProxyConfig = ProxyConfig()):
        self.web_request = WebRequest()
        self.config = config
        self.logger = setup_logger("fetcher")
        self.validator = ProxyValidator()

        # 代理源注册
        self.sources = {}
        self._register_sources()

        self._proxy_cache: Set[str] = set()
        self.stats = {
            "total_fetch": 0,
            "valid_count": 0,
            "invalid_count": 0,
        }

    @staticmethod
    def _validate_ip_port(ip: str, port: int) -> bool:
        """验证 ip 和端口的有效性"""
        try:
            # IP地址验证
            parts = ip.split(".")
            if len(parts) != 4:
                return False
            for part in parts:
                if not 0 <= int(part) <= 255:
                    return False

            # 端口验证
            if not 1 <= port <= 65535:
                return False

            return True

        except:
            return False

    @staticmethod
    def _get_source_name(proxy_str: str) -> str:
        """获取代理来源"""
        sources = {
            "66ip.cn": "66IP代理",
            "kuaidaili.com": "快代理",
            "zdaye.com": "站大爷",
            "ip3366.net": "云代理",
            # 更多代理
        }

        for domain, name in sources.items():
            if domain in proxy_str:
                return name
        return "未知来源"

    def _parse_proxy(self, proxy_str: str) -> Optional[ProxyModel]:
        """解析代理字符串为代理模型"""
        try:
            if not proxy_str:
                return None

            match = re.match(
                r"^(?P<ip>\d{1,3}(\.\d{1,3}){3}):(?P<port>\d+)$",
                proxy_str.strip()
            )
            if not match:
                return None

            ip = match.group("ip")
            port = int(match.group("port"))

            # 基本验证
            if not self._validate_ip_port(ip, port):
                return None

            # 创建代理模型
            proxy = ProxyModel(
                ip=ip,
                port=port,
                protocol="http",
                source=self._get_source_name(proxy_str),
            )

            # 去重检查
            proxy_key = f"{ip}:{port}"
            if proxy_key in self._proxy_cache:
                return None
            self._proxy_cache.add(proxy_key)

            return proxy

        except Exception as e:
            self.logger.warning(f"解析代理失败: {proxy_str}, {e}")
            return None

    def _register_sources(self):
        """注册所有代理源"""
        # 参数按需配置
        source_configs = {
            # "zdaye": ProxySource(
            #     name="站大爷",
            #     urls=["https://www.zdaye.com/dayProxy.html"],
            #     interval=600,
            #     verify_ssl=False,
            #     weight=2,
            #     timeout=20,
            #     enabled=False,
            #     headers={
            #         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            #                       "Chrome/91.0.4472.124 Safari/537.36",
            #         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            #         "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            #         "Accept-Encoding": "gzip, deflate",
            #         "Connection": "keep-alive",
            #         "Upgrade-Insecure-Requests": "1",
            #         "Cache-Control": "max-age=0",
            #     }
            # ),
            # "66ip": ProxySource(
            #     name="66IP",
            #     urls=["http://www.66ip.cn/"],
            #     timeout=20,
            # ),
            "kuaidaili": ProxySource(
                name="快代理",
                urls=[
                    "https://www.kuaidaili.com/free/dps/",
                    "https://www.kuaidaili.com/free/inha/",
                    "https://www.kuaidaili.com/free/intr/",
                    "https://www.kuaidaili.com/free/fps/",
                ],
                interval=180,
                weight=2,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control": "max-age=0",
                },
            ),
            "ip3366": ProxySource(
                name="云代理",
                urls=[
                    "http://www.ip3366.net/free/?stype=1",
                    "http://www.ip3366.net/free/?stype=2",
                ],
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control": "max-age=0",
                },
            ),
            # 其他代理源
        }

        # 创建代理源实例
        self.sources = {
            name: self._create_source(name, config)
            for name, config in source_configs.items()
        }

    async def fetch_from_source(self, source: ProxySourceBase, session: aiohttp.ClientSession) -> List[ProxyModel]:
        """ 从单个代理获取代理 """
        proxies = []
        try:
            async for proxy_str in source.fetch(session):
                if not proxy_str:
                    continue

                proxy = self._parse_proxy(proxy_str)
                if proxy:
                    proxies.append(proxy)
                    proxy.source = source.name
        except Exception as e:
            self.logger.error(f"从 {source.name} 获取代理失败: {str(e)}")
        return proxies

    async def _verify_proxies(self, proxies: List[ProxyModel]) -> List[ProxyModel]:
        """ 验证代理有效性 """
        if not proxies:
            self.logger.warning("没有代理需要验证")
            return []

        tasks = [self._verify_proxy(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks)
        valid_proxies = [proxy for proxy, is_valid in zip(proxies, results) if is_valid]

        return valid_proxies

    async def _verify_proxy(self, proxy: ProxyModel) -> bool:
        """ 验证单个代理 """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        'http://www.baidu.com',
                        proxy=f"http://{proxy.ip}:{proxy.port}",
                        timeout=5
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    def _update_stats(
            self, all_proxies: List[ProxyModel], valid_proxies: List[ProxyModel]
    ):
        """更新统计信息"""
        self.stats["total_fetch"] += len(all_proxies)
        self.stats["valid_count"] += len(valid_proxies)
        self.stats["invalid_count"] += len(all_proxies) - len(valid_proxies)

        if len(all_proxies) > 0:
            success_rate = len(valid_proxies) / len(all_proxies)
        else:
            success_rate = 0

        self.logger.info(
            f"代理获取完成:"
            f"总数 {len(all_proxies)},"
            f"有效 {len(valid_proxies)},"
            f"成功率 {success_rate:.1%}"
        )

    async def close(self):
        """ 关闭资源 """
        if hasattr(self, 'web_request') and self.web_request:
            await self.web_request.close()

    async def fetch_all(self) -> List[ProxyModel]:
        """ 获取所有代理源的代理 """
        try:
            # 确保 web_request 已初始化
            if not hasattr(self, 'web_request') or self.web_request is None:
                self.web_request = WebRequest()

            async with aiohttp.ClientSession() as session:
                tasks = []
                # 仅使用启用的代理源
                for source in self.sources.values():
                    if source.config.enabled:
                        tasks.append(self.fetch_from_source(source, session))

                # 设置全局超时
                results = await asyncio.gather(*tasks, return_exceptions=True)

                all_proxies = []
                for result in results:
                    if isinstance(result, Exception):
                        self.logger.error(f"抓取代理时发生错误: {result}")
                    if isinstance(result, list):
                        all_proxies.extend(result)

                if self.config.verify_proxy:
                    valid_proxies = await self._verify_proxies(all_proxies)
                else:
                    valid_proxies = all_proxies

                self._update_stats(all_proxies, valid_proxies)
                self.logger.info(
                    f"代理获取完成:"
                    f"总数 {len(all_proxies)},"
                    f"有效 {len(valid_proxies)},"
                    f"成功率 {len(valid_proxies) / len(all_proxies) * 100 if all_proxies else 0:.1f}%"
                )
                return valid_proxies

        except asyncio.TimeoutError:
            self.logger.error("代理获取超时")
            return []
        except Exception as e:
            self.logger.error(f"代理获取异常: {str(e)}")
            return []
        # finally:
        #     # 只在所有操作完成后关闭会话
        #     await self.close()

    def _create_source(self, name: str, config: ProxySource) -> ProxySourceBase:
        """ 创建代理源实例 """
        source_classes = {
            # "zdaye": ZdayeProxySource,
            # "66ip": Ip66ProxySource,
            "kuaidaili": KuaidailiProxySource,
            "ip3366": Ip3366ProxySource,
            # 其他代理
        }

        if name not in source_classes:
            raise ValueError(f"未知代理源 {name}")

        source = source_classes[name](config)
        # 插桩测试
        print(f"cz|source: {source}")

        source.set_web_request(self.web_request)  # 设置 web_request
        return source


class ZdayeProxySource(ProxySourceBase):
    """ 站大爷 """

    async def _fetch(self, session: aiohttp.ClientSession) -> AsyncGenerator[str, None]:
        if not self.web_request:  # 新增检查
            return

        start_url = self.config.urls[0]
        try:
            async with session.get(
                    start_url,
                    headers=self.config.headers,
                    verify_ssl=self.config.verify_ssl,
                    timeout=self.config.timeout,
            ) as response:
                if response.status != 200:
                    self.logger.error(f"请求失败，状态码: {response.status}")
                    return

                response_text = await response.text()  # 自动检测编码
                if not response_text:
                    self.logger.error("响应内容为空")
                    return

                html = etree.HTML(response_text)
                if html is None:
                    self.logger.error("HTML 解析失败")
                    return

                # 添加更多的错误处理和日志
                time_elements = html.xpath("//span[@class='thread_time_info']/text()")
                if not time_elements:
                    self.logger.error("未找到时间信息")
                    return

                latest_page_time = time_elements[0].strip()
                if not latest_page_time:
                    self.logger.error("时间信息为空")
                    return

                try:
                    interval = datetime.now() - datetime.strptime(
                        latest_page_time, "%Y/%m/%d %H:%M:%S"
                    )
                except ValueError as e:
                    self.logger.error(f"时间格式解析失败: {e}")
                    return

                if interval.seconds < 300:  # 只采集 5 分钟内的更新
                    target_urls = html.xpath("//h3[@class='thread_title']/a/@href")
                    if not target_urls:
                        self.logger.error("未找到目标URL")
                        return

                    target_url = "https://www.zdaye.com/" + target_urls[0].strip()

                    while target_url:
                        try:
                            async with session.get(
                                    target_url,
                                    headers=self.config.headers,
                                    verify_ssl=False,
                                    timeout=self.config.timeout,
                            ) as resp:
                                if resp.status != 200:
                                    self.logger.error(f"获取详情页失败: {resp.status}")
                                    break

                                detail_text = await resp.text()
                                detail_html = etree.HTML(detail_text)

                                # 提取代理信息
                                for tr in detail_html.xpath("//table//tr"):
                                    try:
                                        ip = "".join(tr.xpath("./td[1]/text()")).strip()
                                        port = "".join(tr.xpath("./td[2]/text()")).strip()
                                        if ip and port:
                                            yield f"{ip}:{port}"
                                    except Exception as e:
                                        self.logger.error(f"解析代理信息失败: {e}")
                                        continue

                                # 获取下一页
                                next_pages = detail_html.xpath(
                                    "//div[@class='page']/a[@title='下一页']/@href"
                                )
                                target_url = (
                                    "https://www.zdaye.com/" + next_pages[0].strip()
                                    if next_pages
                                    else None
                                )

                                if target_url:
                                    await asyncio.sleep(5)  # 避免请求过快

                        except Exception as e:
                            self.logger.error(f"处理详情页失败: {e}")
                            break

        except Exception as e:
            self.logger.error(f"站大爷代理获取失败: {e}")
            # self.logger.exception(e)  # 打印完整堆栈信息


class Ip66ProxySource(ProxySourceBase):
    """66 代理源"""

    async def _fetch(self, session: aiohttp.ClientSession) -> AsyncGenerator[str, None]:
        if not self.web_request:  # 新增检查
            return

        start_url = self.config.urls[0]
        try:
            async with session.get(
                    start_url,
                    headers=self.config.headers,
                    verify_ssl=self.config.verify_ssl,
                    timeout=self.config.timeout,
            ) as response:
                if response.status != 200:
                    return
                # 编码校正尝试
                if response.status == 200:
                    try:
                        response_text = await response.text(encoding='utf-8')
                    except UnicodeDecodeError:
                        try:
                            response_text = await response.text(encoding='gbk')
                        except UnicodeDecodeError:
                            response_text = await response.text(encoding='gb2312')

                html = etree.HTML(response_text)
                if html is not None:
                    proxy_list = html.xpath('//div[@id="main"]//table//tr[position()>1]')
                    for proxy in proxy_list:
                        try:
                            ip = proxy.xpath('./td[1]/text()')[0]
                            port = proxy.xpath('./td[2]/text()')[0]
                            proxy_str = f"{ip}:{port}"
                            yield proxy_str
                        except (IndexError, Exception) as e:
                            self.logger.error(f"解析代理失败: {str(e)}")
                            continue
                else:
                    self.logger.error("HTML 解析失败")
        except Exception as e:
            self.logger.error(f"66代理获取失败: {e}")


class KuaidailiProxySource(ProxySourceBase):
    """快代理源"""

    async def _fetch(self, session: aiohttp.ClientSession) -> AsyncGenerator[str, None]:
        if not self.web_request:  # 新增检查
            return

        for url in self.config.urls:
            try:
                async with session.get(
                        url,
                        headers=self.config.headers,
                        verify_ssl=self.config.verify_ssl,
                        timeout=self.config.timeout,
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"快代理请求失败: {response.status}")
                        continue
                    # 读取二进制内容
                    content = await response.read()
                    # 使用 charset-normalizer 检测编码
                    result = from_bytes(content).best()
                    html_text = str(result)
                    html = etree.HTML(html_text)
                    if html is None:
                        self.logger.error("快代理页面解析失败")
                        continue

                    rows = html.xpath('//table//tr')
                    self.logger.info(f"找到 {len(rows)} 个代理")

                    for row in rows:
                        try:
                            ip = row.xpath("./td[1]/text()")[0].strip()
                            port = row.xpath("./td[2]/text()")[0].strip()
                            if ip and port:
                                proxy =  f"{ip}:{port}"
                                self.logger.debug(f"获取到代理: {proxy}")
                                yield proxy
                        except IndexError:
                            continue

                    await asyncio.sleep(5)  # 避免请求过快

            except Exception as e:
                self.logger.error(f"处置快二逼页面嘎了: {str(e)}")
                continue


class Ip3366ProxySource(ProxySourceBase):
    """云代理源"""

    async def _fetch(self, session: aiohttp.ClientSession) -> AsyncGenerator[str, None]:
        if not self.web_request:  # 新增检查
            return

        for url in self.config.urls:
            start_url = url
            try:
                async with session.get(
                        start_url,
                        headers=self.config.headers,
                        verify_ssl=self.config.verify_ssl,
                        timeout=self.config.timeout,
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"云代理请求失败: {response.status}")
                        continue

                    # 读取二进制内容
                    content = await response.read()
                    # 使用 charset-normalizer 检测编码
                    result = from_bytes(content).best()
                    html_text = str(result)
                    html = etree.HTML(html_text)
                    if html is None:
                        self.logger.error("快代理页面解析失败")
                        continue

                    rows = html.xpath('//table//tr')
                    self.logger.info(f"找到 {len(rows)} 个代理")

                    for row in rows:
                        try:
                            ip = row.xpath("./td[1]/text()")[0].strip()
                            port = row.xpath("./td[2]/text()")[0].strip()
                            if ip and port:
                                proxy = f"{ip}:{port}"
                                self.logger.debug(f"获取到代理: {proxy}")
                                yield proxy
                        except IndexError:
                            continue

                    await asyncio.sleep(5)  # 避免请求过快

            except Exception as e:
                self.logger.error(f"云二逼又嘎了: {e}")


# 更多代理源...

if __name__ == "__main__":
    async def test_fetcher():
        fetcher = None
        try:
            fetcher = ProxyFetcher()
            proxies = await fetcher.fetch_all()
            print(f"获取到的代理数量: {len(proxies)}")
            for proxy in proxies:
                print(proxy)
        except Exception as e:
            print(f"出现错误: {e}")
        finally:
            if fetcher:
                await fetcher.close()


    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_fetcher())
