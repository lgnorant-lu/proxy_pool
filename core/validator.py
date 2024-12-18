"""
----------------------------------------------------------------
File name:                  storage.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理验证模块
----------------------------------------------------------------

Changed history:            代理验证模块: 验证代理可用性
----------------------------------------------------------------
"""

import asyncio
from typing import List, Optional

import aiohttp

from ..utils.logger import setup_logger
from ..models.proxy_model import ProxyModel
from ..utils.config import ProxyConfig


class ProxyValidator:
    def __init__(self, config: ProxyConfig = ProxyConfig()):
        self.config = config
        self.logger = setup_logger()

    async def validate_proxy(
        self, proxy: ProxyModel, test_url: Optional[str] = None
    ) -> bool:
        """
        验证单个代理可用性

        Args:
            proxy: 代理模型
            test_url: 测试地址

        Returns:
            是否可用
        """
        test_url = test_url or "http://httpbin.org/ip"

        try:
            start_time = asyncio.get_event_loop().time()

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    test_url, proxy=f"http://{proxy.ip}:{proxy.port}", timeout=10.0
                ) as response:
                    # 响应成功
                    if response.status == 200:
                        end_time = asyncio.get_event_loop().time()

                        # 更新代理模型
                        proxy.update_stats(
                            is_success=True, response_time=end_time - start_time
                        )
                        return True
        except Exception as e:
            # 验证失败
            proxy.update_stats(is_success=False)

        return False

    async def batch_validate(self, proxies: List[ProxyModel]) -> List[ProxyModel]:
        """
        批量验证代理

        Args:
            proxies: 待验证代理列表

        Returns:
            可用代理列表
        """
        # 并发验证
        tasks = [self.validate_proxy(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks)

        # 过滤可用代理
        valid_proxies = [proxy for proxy, is_valid in zip(proxies, results) if is_valid]

        self.logger.info(f"验证通过 {len(valid_proxies)}/{len(proxies)} 个代理")
        return valid_proxies
