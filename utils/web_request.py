"""
----------------------------------------------------------------
File name:                  web_request.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                网络请求模块
----------------------------------------------------------------

Changed history:            网络请求模块: 代理源
                            2024/12/24: 异常处理部分优化
                            2024/12/25: 添加重试机制和响应处理优化
----------------------------------------------------------------
"""

import aiohttp
# import asyncio
from aiohttp import ClientTimeout, TCPConnector
from lxml import etree
from typing import Optional, Any, Union, Callable
from proxy_pool.utils.logger import setup_logger
from proxy_pool.utils.exceptions import RequestError


class WebRequest:
    """
    网络请求模块， aiohttp 异步实现

    功能：
    1. 异步HTTP请求
    2. 自动重试机制
    3. 代理支持
    4. HTML解析
    5. 异步上下文管理
    """

    def __init__(self):
        """ 初始化 WebRequest 实例 """
        self.logger = setup_logger()
        self._session = None
        self.default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.6",
        }

    def _get_session(self) -> aiohttp.ClientSession:
        """
        获取 / 创建 session

        Returns:
            aiohttp.ClientSession: 会话实例
        """
        if self._session is None or self._session.closed:
            connector = TCPConnector(
                ssl=False,  # 关闭 SSL/TLS 验证
                force_close=True,  # 开启 TCP 连接
                limit=100,  # 并发连接池大小
                ttl_dns_cache=300,  # DNS 缓存时间
            )
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    @staticmethod
    def _get_timeout(timeout: Union[float, ClientTimeout]) -> ClientTimeout:
        """
        获取请求超时设置

        Args:
            timeout: 超时时间 / 超时配置对象

        Returns:
            ClientTimeout: aiohttp 超时配置对象
        """
        if isinstance(timeout, (int, float)):
            return ClientTimeout(
                total=float(timeout),
                connect=min(timeout * 0.2, 5),  # 连接超时
                sock_connect=min(timeout * 0.2, 5),  # Socket 连接超时
                sock_read=timeout,  # 读取超市
            )
        return timeout

    async def _process_response(
        self,
        response: aiohttp.ClientResponse,
        url: str,
    ) -> Optional[Any]:
        """
        处理HTTP响应

        Args:
            response: aiohttp响应对象
            url: 请求URL

        Returns:
            Optional[Any]: 处理后的响应数据

        Raises:
            RequestError: 响应处理失败
        """
        if response.status >= 400:
            self.logger.warning(
                f"请求失败: {url}\n"
                f"状态码: {response.status}"
            )
            return None

        try:
            text = await response.text(errors="ignore")
            try:
                tree = etree.HTML(text)
                response.tree = tree
            except etree.ParserError as e:
                self.logger.error(
                    f"HTML解析失败: {url}\n"
                    f"状态码: {response.status}\n"
                    f"Error: {str(e)}"
                )
                response.tree = None
            return response

        except UnicodeDecodeError as e:
            self.logger.error(
                f"Unicode解码错误: {url}\n"
                f"Error: {str(e)}"
            )
            return None

    async def get_eith_retry(
        self,
        url: str,
        retry_times: int = 3,
        retry_interval: float = 1.0,
        retry_on: Optional[Callable[[Exception], bool]] = None,
        **kwargs,
    ):
        """
        重试机制 get 请求

        Args:
            url: 请求 URL
            retry_times: 最大重试次数
            retry_interval: 重试间隔
            retry_on: 重试条件函数
            **kwargs: 其他 aiohttp.ClientSession.get() 参数

        Returns:
            Optional[Any]: 请求响应

        Raises:
            RequestError: 重试机制中发生 HTTP 错误
        """
        last_error = None

        for attempt in range(retry_times + 1):
            try:
                response = await self.get(url, **kwargs)
                if response:
                    return response

            except Exception as e:
                last_error = e
                if retry_on and not retry_on(e):
                    break

                if attempt < retry_times:
                    wait_time = retry_interval * (attempt + 1)
                    self.logger.warning(
                        f"请求失败,{wait_time}秒后重试 ({attempt + 1}/{retry_times})\n"
                        f"URL: {url}\n"
                        f"Error: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)

        raise RequestError(f"重试{retry_times}次后仍然失败: {str(last_error)}")

    async def get(
        self,
        url: str,
        timeout: Union[float, ClientTimeout] = 10.0,
        headers: Optional[dict] = None,
        proxy: Optional[str] = None,
        **kwargs,
    ) -> Optional[Any]:
        """
        异步 get 请求

        Args:
            url: 请求地址
            timeout: 超时时间
            headers: 请求头
            proxy: 代理地址 ("protocol://host:port")
            **kwargs: 其他 aiohttp.ClientSession.get() 参数

        Returns:
            Optional[Any]: 请求响应
        """
        # 合并请求头
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)

        # 处理超市
        if isinstance(timeout, (int, float)):
            timeout = ClientTimeout(total=float(timeout))

        try:
            session = self._get_session()
            async with session.get(
                url,
                headers=request_headers,
                timeout=timeout,
                proxy=proxy,
                allow_redirects=True,  # 允许重定向
                **kwargs,
            ) as response:
                return await self._process_response(response, url)

        except aiohttp.ClientError as e:
            self.logger.error(
                f"aiohttp 客户端错误: {url}\n"
                f"代理: {proxy or '无'}\n"
                f"Error: {str(e)}"
            )
            return None

        except Exception as e:
            self.logger.error(
                f"未知错误: {url}\n" f"代理: {proxy or '无'}\n" f"Error: {str(e)}"
            )
            return None

    async def close(self):
        """ 关闭 aiohttp 会话 """
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """
        异步上下文管理器入口

        Returns:
            self: 自身
        """
        if self._session is None:
            self._session = self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器出口

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常 traceback

        Returns:
            bool: 关闭 aiohttp session 结果
        """
        await self.close()
        if exc_type:
            self.logger.error(
                f"上下文管理器异常:\n"
                f"Type: {exc_type.__name__}\n"
                f"Value: {str(exc_val)}"
            )


if __name__ == "__main__":
    import asyncio
    import json
    import aiohttp


    async def test_proxy(client, proxy, timeout=5):
        """测试代理是否可用"""
        try:
            response = await client.get(
                    'http://httpbin.org/ip',
                    proxy=proxy,
                    timeout=timeout,
            )

            if response:
                if response.status == 200:
                    try:
                        json_data = await response.json()
                        return True, json_data
                    except:
                        return False, "响应格式错误"
                return False, f"状态码错误: {response.status}"
            return False, "无响应"

        except aiohttp.ClientProxyConnectionError:
            return False, "代理连接错误：代理服务器拒绝连接"
        except aiohttp.ClientConnectorError:
            return False, "连接错误：代理服务器无法连接"
        except asyncio.TimeoutError:
            return False, "连接超时：代理服务器响应超时"
        except Exception as e:
            return False, f"其他错误：{str(e)}"


    async def main():
        async with WebRequest() as client:
            # 代理列表
            proxies = [
                "http://47.106.103.187:8080",
                "http://220.248.70.237:9002",
                "http://invalid.proxy:8080",  # 无效代理示例
            ]

            # 测试网站列表
            test_urls = [
                "http://httpbin.org/ip",
                "http://httpbin.org/get",
                "https://www.baidu.com",
                "http://www.example.com",
            ]

            print("=== 代理可用性测试 ===")
            valid_proxies = []
            for proxy in proxies:
                print(f"\n测试代理: {proxy}")
                is_valid, result = await test_proxy(client, proxy)
                if is_valid:
                    print("✓ 代理可用")
                    print(f"代理IP信息: {result}")
                    valid_proxies.append(proxy)
                else:
                    print("✗ 代理不可用")
                    print(f"错误信息: {result}")
                print("-" * 50)

            # 使用可用代理进行实际请求
            print("\n=== 使用可用代理访问目标网站 ===")
            for url in test_urls:
                print(f"\n访问URL: {url}")
                for proxy in (proxies or valid_proxies):
                    print(f"尝试使用代理: {proxy}")
                    try:
                        response = await client.get(
                            url,
                            proxy=proxy,
                            timeout=10.0
                        )

                        if response:
                            print(f"状态码: {response.status}")
                            content_type = response.headers.get('Content-Type', '').lower()

                            if 'json' in content_type:
                                data = await response.json()
                                print("JSON响应:")
                                print(json.dumps(data, indent=2))
                            elif 'html' in content_type:
                                title = response.tree.xpath('//title/text()')
                                print(f"HTML标题: {title}")
                            print("✓ 请求成功")
                        else:
                            print("✗ 请求失败：无响应")

                    except aiohttp.ClientProxyConnectionError:
                        print("✗ 代理错误：代理服务器拒绝连接")
                    except aiohttp.ClientConnectorError:
                        print("✗ 连接错误：无法连接到代理服务器")
                    except asyncio.TimeoutError:
                        print("✗ 超时错误：代理服务器响应超时")
                    except Exception as e:
                        print(f"✗ 其他错误：{str(e)}")

                    print("-" * 50)


    asyncio.run(main())
