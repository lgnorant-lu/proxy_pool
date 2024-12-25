"""
----------------------------------------------------------------
File name:                  validator.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理验证模块
----------------------------------------------------------------

Changed history:            代理验证模块: 验证代理可用性
                            2024/12/22
                            2024/12/26: 日志输出和错误处理的优化, 添加统计功能, 检验流程优化;
----------------------------------------------------------------
"""

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

from proxy_pool.models.proxy_model import ProxyModel
from proxy_pool.utils.config import ProxyConfig
from proxy_pool.utils.logger import setup_logger


class ProxyProtocol(Enum):
    """代理协议枚举"""

    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


@dataclass
class ValidationResult:
    """验证结果数据类"""

    is_valid: bool
    response_time: float
    status_code: Optional[int]
    error_msg: Optional[str] = None


#  主类重构
class ProxyValidator:
    """代理验证 qiqi"""

    def __init__(
        self,
        config: ProxyConfig = ProxyConfig(),
        timeout: float = 5.0,
        concurrent_limit: int = 20,
        retry_times: int = 3,
        min_success_rate: float = 0.3,
    ):
        """
        初始化代理验证器

        Args:
            config: 代理配置
            timeout: 超时时间
            concurrent_limit: 并发数限制
            retry_times: 重试次数
            min_success_rate: 最低成功率
        """
        self.config = config
        self.logger = setup_logger("validator")

        # 验证配置
        self.timeout = ClientTimeout(total=timeout)
        self.concurrent_limit = concurrent_limit
        self.retry_times = retry_times
        self.min_success_rate = min_success_rate

        # 测试 urls 配置
        self._test_urls = [
            "http://www.baidu.com",
            "https://www.qq.com",
            "http://www.taobao.com",
            "http://httpbin.org/ip",
            "http://api.ipify.org?format=json",
            "http://ip.sb/api",
        ]

        # 统计配置
        self._stats = {
            "total": 0,
            "success": 0,
            "fail": 0,
            "timeout": 0,
        }

    @property
    def test_urls(self) -> List[str]:
        """获取测试 urls 列表"""
        return self._test_urls.copy()

    @test_urls.setter
    def test_urls(self, urls: List[str]):
        """设置测试 urls 列表"""
        if not urls:
            raise ValueError("测试 urls 列表不能为空")
        self._test_urls = urls.copy()

    @staticmethod
    def _build_proxy_url(proxy: ProxyModel) -> str:
        """构建代理 url"""
        return f"{proxy.protocol}://{proxy.ip}:{proxy.port}"

    def _create_session(self) -> aiohttp.ClientSession:
        """创建 HTTP 会话"""
        return aiohttp.ClientSession(
            timeout=self.timeout,
            connector=TCPConnector(ssl=False, force_close=True),
        )

    async def _check_url_accessibility(self, url: str) -> bool:
        """检查测试 url 有效性"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    return response.status == 200
        except:
            return False

    async def _validate_test_urls(self) -> List[str]:
        """验证并过滤测试 url"""
        valid_urls = []
        for url in self._test_urls:
            if await self._check_url_accessibility(url):
                valid_urls.append(url)
        return valid_urls

    def _update_stats(self, result: ValidationResult):
        """更新统计信息"""
        self._stats["total"] += 1
        if result.is_valid:
            self._stats["success"] += 1
        else:
            self._stats["fail"] += 1
            if isinstance(result.error_msg, asyncio.TimeoutError):
                self._stats["timeout"] += 1

    async def validate_single_proxy(
        self,
        proxy: ProxyModel,
        test_url: str,
    ) -> ValidationResult:
        """
        验证单个代理对单个 URL 的可用性

        Args:
            proxy: 代理模型
            test_url: 测试地址

        Returns:
            ValidationResult: 验证结果
        """
        proxy_url = self._build_proxy_url(proxy)
        self.logger.debug(f"开始验证代理: {proxy_url} -> {test_url}")

        for attempt in range(self.retry_times):
            try:
                start_time = asyncio.get_event_loop().time()
                async with self._create_session() as session:
                    async with session.get(
                        test_url,
                        proxy=proxy_url,
                        ssl=False,  # 禁用 SSL 验证
                        allow_redirects=True,  # 允许重定向
                    ) as response:
                        response_time = asyncio.get_event_loop().time() - start_time

                        if response.status < 400:
                            content = await response.text(errors="ignore")
                            if content:
                                result = ValidationResult(
                                    is_valid=True,
                                    response_time=response_time,
                                    status_code=response.status,
                                )
                                self._update_stats(result)
                                proxy.update_stats(
                                    is_success=True,
                                    response_time=response_time,
                                    status_code=response.status,
                                )
                                self.logger.debug(
                                    f"代理验证成功: {proxy_url} "
                                    f"(响应时间: {response_time:.2f}s, "
                                    f"状态码: {response.status}, "
                                    f"尝试次数: {attempt + 1})"
                                )

                                return result

                result = ValidationResult(
                    is_valid=False,
                    response_time=response_time,
                    status_code=response.status,
                    error_msg="Invalid response",
                )

            except asyncio.TimeoutError:
                self.logger.debug(
                    f"代理 {proxy_url} 验证超时"
                    f"尝试次数 {attempt + 1}/{self.retry_times}"
                )
                result = ValidationResult(
                    is_valid=False,
                    response_time=self.timeout.total,
                    status_code=(
                        getattr(response, "status", None)
                        if "response" in locals()
                        else None
                    ),
                    error_msg="Timeout",
                )

            except aiohttp.ClientError as e:
                self.logger.debug(f"代理 {proxy_url} 连接错误: {str(e)}")
                result = ValidationResult(
                    is_valid=False,
                    response_time=self.timeout.total,
                    status_code=(
                        getattr(response, "status", None)
                        if "response" in locals()
                        else None
                    ),
                    error_msg=str(e),
                )

            except Exception as e:
                self.logger.error(f"代理 {proxy_url} 验证异常: {str(e)}")
                # import traceback
                # self.logger.debug(traceback.format_exc())
                result = ValidationResult(
                    is_valid=False,
                    response_time=self.timeout.total,
                    status_code=(
                        getattr(response, "status", None)
                        if "response" in locals()
                        else None
                    ),
                    error_msg=str(e),
                )

            # 更新失败统计
            self._update_stats(result)
            proxy.update_stats(
                is_success=False,
                response_time=self.timeout.total,
                status_code=(getattr(response, "status", None) if "response" in locals() else None),
            )

            # 重试间隔
            if attempt < self.retry_times - 1:
                await asyncio.sleep(1)

        return result

    async def validate_proxy(
        self, proxies: List[ProxyModel], test_url: Optional[str] = None
    ) -> List[ProxyModel]:
        """
        验证单个代理可用性

        Args:
            proxies: 代理列表
            test_url: 测试 url

        Returns:
            List[ProxyModel]: 有效代理列表
        """
        if not proxies:
            self.logger.warning("没有代理需要验证")
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
        await asyncio.gather(*tasks, return_exceptions=True)

        self.logger.info(
            f"单 URL 验证完成:"
            f"总数 {len(proxies)},"
            f"有效数 {len(valid_proxies)},"
            f"成功率 {len(valid_proxies)/len(proxies):.1%}"
        )
        return valid_proxies

    async def batch_validate(self, proxies: List[ProxyModel]) -> List[ProxyModel]:
        """
        批量验证代理

        Args:
            proxies: 代理列表

        Returns:
            List[ProxyModel]: 有效代理列表
        """
        if not proxies:
            self.logger.warning("没有代理需要验证")
            return []

        self.logger.info(f"开始批量验证 {len(proxies)} 锅代理")
        all_valid_proxies = set()

        # 验证代理有效性
        valid_urls = await self._validate_test_urls()
        if not valid_urls:
            self.logger.warning("全嘎了, 去检查一下吧")
            return []

        for test_url in valid_urls:
            self.logger.info(f"使用测试URL: {test_url}")
            valid_proxies = await self.validate_proxy(proxies, test_url)
            all_valid_proxies.update(valid_proxies)
            self.logger.info(
                f"当前URL验证结果: "
                f"通过 {len(valid_proxies)}/{len(proxies)} "
                f"({len(valid_proxies) / len(proxies):.1%})"
            )

        # 过滤最低界线以上的代理
        final_proxies = [
            proxy
            for proxy in all_valid_proxies
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

    import random


    async def test_validator():
        """测试代理验证器"""
        # 配置日志
        logging.basicConfig(level=logging.DEBUG)

        # 创建验证器实例
        validator = ProxyValidator(
            timeout=3.0,
            concurrent_limit=10,
            retry_times=2
        )

        # 生成测试代理
        def generate_test_proxies(count: int) -> List[ProxyModel]:
            proxies = []
            for _ in range(count):
                ip = ".".join(str(random.randint(1, 255)) for _ in range(4))
                port = random.randint(1000, 65535)
                protocol = random.choice(["http", "https"])
                proxies.append(ProxyModel(
                    ip=ip,
                    port=port,
                    protocol=protocol,
                    success_rate=random.random(),
                    response_times=[random.uniform(0.1, 2.0)],
                    last_check_time=datetime.now(),
                    fail_count=random.randint(0, 5)
                ))
            return proxies

        # 测试场景
        async def run_test_cases():
            print("\n=== 开始代理验证测试 ===")

            # 测试1: 空代理列表
            print("\n测试1: 空代理列表")
            result = await validator.batch_validate([])
            assert len(result) == 0
            print("✓ 通过: 正确处理空代理列表")

            # 测试2: 单个代理验证
            print("\n测试2: 单个代理验证")
            test_proxy = generate_test_proxies(1)[0]
            result = await validator.validate_single_proxy(
                test_proxy,
                "http://httpbin.org/ip"
            )
            print(f"单个代理验证结果: {result}")

            # 测试3: 批量代理验证
            print("\n测试3: 批量代理验证")
            test_proxies = generate_test_proxies(5)
            results = await validator.batch_validate(test_proxies)
            print(f"批量验证结果: {len(results)}/{len(test_proxies)} 个代理可用")

            # 测试4: 验证统计
            print("\n测试4: 验证统计")
            print(f"总验证次数: {validator._stats['total']}")
            print(f"成功次数: {validator._stats['success']}")
            print(f"失败次数: {validator._stats['fail']}")
            print(f"超时次数: {validator._stats['timeout']}")

            print("\n=== 测试完成 ===")

        # 运行测试
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        await run_test_cases()


    # 执行测试
    asyncio.run(test_validator())

    # async def main():
    #     test_proxies = [
    #         ProxyModel(ip="47.106.103.187", port=8080, protocol="http"),
    #         ProxyModel(ip="122.136.212.132", port=53281, protocol="http"),
    #         ProxyModel(ip="8.8.4.4", port=8080),
    #         ProxyModel(ip="208.67.222.222", port=8080),
    #         ProxyModel(ip="192.168.0.1", port=8080),
    #         ProxyModel(ip="192.168.1.1", port=8080),
    #         ProxyModel(ip="8.8.8.8", port=8080),
    #         ProxyModel(ip="1.1.1.1", port=8080),
    #     ]
    #
    #     validator = ProxyValidator()
    #
    #     # 单URL验证测试
    #     print("\n=== 单URL验证测试 ===")
    #     valid_proxies = await validator.validate_proxy(test_proxies)
    #     print(f"验证通过: {len(valid_proxies)}/{len(test_proxies)}")
    #     for proxy in valid_proxies:
    #         print(f"\n代理详情:")
    #         print(f"地址: {proxy.ip}:{proxy.port}")
    #         print(f"协议: {proxy.protocol}")
    #         print(f"成功率: {proxy.success_rate:.1%}")
    #         print(f"响应时间: {proxy.avg_response_time:.2f}s")
    #         print(f"状态码: {proxy.last_status_code}")
    #
    #     # 多URL验证测试
    #     print("\n=== 多URL验证测试 ===")
    #     valid_proxies = await validator.batch_validate(test_proxies)
    #     print(f"批量验证通过: {len(valid_proxies)}/{len(test_proxies)}")
    #     for proxy in valid_proxies:
    #         print(f"\n代理详情:")
    #         print(f"地址: {proxy.ip}:{proxy.port}")
    #         print(f"协议: {proxy.protocol}")
    #         print(f"成功率: {proxy.success_rate:.1%}")
    #         print(f"响应时间: {proxy.avg_response_time:.2f}s")
    #         print(f"状态码: {proxy.last_status_code}")
    #
    # asyncio.run(main())
