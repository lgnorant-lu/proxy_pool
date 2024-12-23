"""
----------------------------------------------------------------
File name:                  storage.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理验证模块
----------------------------------------------------------------

Changed history:            代理验证模块: 验证代理可用性
                            2024/12/22
----------------------------------------------------------------
"""

import asyncio
from typing import List, Optional
import aiohttp
from aiohttp import ClientTimeout, TCPConnector
from proxy_pool.utils.logger import setup_logger
from proxy_pool.models.proxy_model import ProxyModel
from proxy_pool.utils.config import ProxyConfig


class ProxyValidator:
    def __init__(self, config: ProxyConfig = ProxyConfig()):
        self.config = config
        self.logger = setup_logger()
        self.test_urls = [
            "http://www.baidu.com",
            "https://www.qq.com",
            "http://www.taobao.com",
            "http://httpbin.org/ip",
            "http://api.ipify.org?format=json",
            "http://ip.sb/api",
        ]
        self.timeout = ClientTimeout(total=5.0)  # 超时时间
        self.concurrent_limit = 20  # 并发数
        self.retry_times = 3
        self.min_success_rate = 0.3

    async def validate_single_proxy(
            self,
            proxy: ProxyModel,
            test_url: str
    ) -> bool:
        """
        验证单个代理对单个 URL 的可用性

        Args:
            proxy: 代理模型
            test_url: 测试地址

        Returns:
            bool: 代理是否可用
        """
        proxies = {
            "http": f"{proxy.protocol}://{proxy.ip}:{proxy.port}",
            "https": f"{proxy.protocol}://{proxy.ip}:{proxy.port}"
        }

        self.logger.debug(f"开始验证代理: {proxies}")

        for attempt in range(self.retry_times):
            try:
                start_time = asyncio.get_event_loop().time()

                # 使用 TCPConnector 限制并发连接
                connector = TCPConnector(ssl=False, force_close=True)
                async with aiohttp.ClientSession(
                    timeout=self.timeout,
                    connector=connector,
                ) as session:
                    # protocol 裂项
                    proxy_url = proxies["https"] if test_url.startswith('https') else proxies["http"]

                    async with session.get(
                        test_url,
                        proxy=proxy_url,
                        ssl=False,  # 禁用 SSL 验证
                        allow_redirects=True,  # 允许重定向
                    ) as response:
                        end_time = asyncio.get_event_loop().time()
                        response_time = end_time - start_time

                        # if response.status == 200:
                        #     try:
                        #         json_response = await response.json()
                        #         # IP 字段存在性验证
                        #         if not json_response.get('origin'):
                        #             continue
                        # 尝试读取响应内容
                        if response.status < 400:
                            try:
                                content = await response.text(errors='ignore')
                                if content:  # 只要有响应内容就认为是成功的
                                    proxy.update_stats(
                                        is_success=True,
                                        response_time=response_time,
                                        status_code=response.status
                                    )
                                    self.logger.debug(
                                        f"代理 {proxy_url} 验证成功 "
                                        f"(响应时间: {response_time:.2f}s, "
                                        f"状态码: {response.status})"
                                    )
                                    return True
                            except:
                                # 如果解析 JSON 失败仍旧认为是成功的
                                pass

                            # # 更新代理统计信息
                            # proxy.update_stats(
                            #     is_success=True,
                            #     response_time=response_time,
                            #     status_code=response.status,
                            # )
                            #
                            # self.logger.debug(
                            #     f"代理 {proxy_url} 验证成功,"
                            #     f"响应时间: {response_time:.2f}s,"
                            #     f"重试次数: {attempt}"
                            # )
                            # return True
                        # else:
                        #     # 更新失败统计
                        #     proxy.update_stats(
                        #         is_success=False,
                        #         response_time=response_time,
                        #         status_code=response.status,
                        #     )
                        #
                        #     self.logger.debug(
                        #         f"代理 {proxy_url} 验证失败,"
                        #         f"响应时间: {response_time:.2f}s,"
                        #         f"重试次数: {attempt}"
                        #     )
                        #     break
                # 更新失败统计
                proxy.update_stats(
                    is_success=False,
                    response_time=self.timeout.total,
                    status_code=response.status if 'response' in locals() else None
                )

            except asyncio.TimeoutError:
                self.logger.debug(f"代理 {proxy_url} 验证超时 (尝试 {attempt + 1}/{self.retry_times})")
            except aiohttp.ClientError as e:
                self.logger.debug(f"代理 {proxy_url} 连接错误: {str(e)}")
            except Exception as e:
                self.logger.error(f"代理 {proxy_url} 验证异常: {str(e)}")
                import traceback
                self.logger.debug(traceback.format_exc())

            # 更新失败统计
            proxy.update_stats(
                is_success=False,
                response_time=self.timeout.total,
                status_code=getattr(response, 'status', None) if 'response' in locals() else None,
            )

            # 重试间隔
            if attempt < self.retry_times - 1:
                await asyncio.sleep(1)

        return False

    async def validate_proxy(
            self,
            proxies: List[ProxyModel],
            test_url: Optional[str] = None
    ) -> List[ProxyModel]:
        """
        验证单个代理可用性

        Args:
            proxies: 代理模型列表
            test_url: 测试地址

        Returns:
            可用的代理列表
        """
        if not proxies:
            return []

        # print 插桩测试
        # print(f"test_url = {test_url} \nproxies = {proxies}")

        # 使用信号量限制并发
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        valid_proxies = []

        async def _validate_with_semaphore(proxy: ProxyModel):
            async with semaphore:
                url = test_url or self.test_urls[0]
                is_valid = await self.validate_single_proxy(proxy, url)
                if is_valid and proxy.is_valid():  # ProxyModel 的 is_valid 方法
                    valid_proxies.append(proxy)

        # 创建代理验证任务
        tasks = [_validate_with_semaphore(proxy) for proxy in proxies]

        # 等待任务完成
        await asyncio.gather(*tasks, return_exceptions=True)

        self.logger.info(
            f"单 URL 验证完成: 总数 {len(proxies)},"
            f"有效数 {len(valid_proxies)},"
            f"成功率 {len(valid_proxies)/len(proxies):.1%}"
        )
        return valid_proxies

    async def batch_validate(self, proxies: List[ProxyModel]) -> List[ProxyModel]:
        """
        批量验证代理

        Args:
            proxies: 待验证代理列表

        Returns:
            可用代理列表
        """
        if not proxies:
            return []

        all_valid_proxies = set()

        for test_url in self.test_urls:
            valid_proxies = await self.validate_proxy(proxies, test_url)
            all_valid_proxies.update(valid_proxies)

        # 过滤综合达标的代理
        final_proxies = [
            proxy for proxy in all_valid_proxies
            if proxy.success_rate >= self.min_success_rate
        ]

        self.logger.info(
            f"批量验证完成: "
            f"总数 {len(proxies)},"
            f"有效数 {len(final_proxies)},"
            f"成功率 {len(final_proxies)}/len{proxies}:.1%"
        )
        return final_proxies


if __name__ == "__main__":
    async def main():
        test_proxies = [
            ProxyModel(ip="47.106.103.187", port=8080, protocol="http"),
            ProxyModel(ip="122.136.212.132", port=53281, protocol="http"),
            ProxyModel(ip="8.8.4.4", port=8080),
            ProxyModel(ip="208.67.222.222", port=8080),
            ProxyModel(ip="192.168.0.1", port=8080),
            ProxyModel(ip="192.168.1.1", port=8080),
            ProxyModel(ip="8.8.8.8", port=8080),
            ProxyModel(ip="1.1.1.1", port=8080),
        ]

        validator = ProxyValidator()

        # 单URL验证测试
        print("\n=== 单URL验证测试 ===")
        valid_proxies = await validator.validate_proxy(test_proxies)
        print(f"验证通过: {len(valid_proxies)}/{len(test_proxies)}")
        for proxy in valid_proxies:
            print(f"\n代理详情:")
            print(f"地址: {proxy.ip}:{proxy.port}")
            print(f"协议: {proxy.protocol}")
            print(f"成功率: {proxy.success_rate:.1%}")
            print(f"响应时间: {proxy.avg_response_time:.2f}s")
            print(f"状态码: {proxy.last_status_code}")

        # 多URL验证测试
        print("\n=== 多URL验证测试 ===")
        valid_proxies = await validator.batch_validate(test_proxies)
        print(f"批量验证通过: {len(valid_proxies)}/{len(test_proxies)}")
        for proxy in valid_proxies:
            print(f"\n代理详情:")
            print(f"地址: {proxy.ip}:{proxy.port}")
            print(f"协议: {proxy.protocol}")
            print(f"成功率: {proxy.success_rate:.1%}")
            print(f"响应时间: {proxy.avg_response_time:.2f}s")
            print(f"状态码: {proxy.last_status_code}")


    asyncio.run(main())
