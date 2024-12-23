import asyncio
import argparse
from fastapi import FastAPI, HTTPException
import uvicorn
from typing import List

from loguru import logger

from proxy_pool.core.fetcher import ProxyFetcher
from proxy_pool.core.validator import ProxyValidator
from proxy_pool.core.storage import RedisProxyClient
from proxy_pool.core.cleaner import ProxyCleaner
from proxy_pool.models.proxy_model import ProxyModel
from proxy_pool.utils.config import get_config
from proxy_pool.utils.logger import setup_logger


# 全局共享的 Redis 客户端实例
storage = RedisProxyClient()


class ProxyPoolApplication:
    def __init__(self):
        self.config = get_config()
        self.fetcher = ProxyFetcher()
        self.validator = ProxyValidator()
        self.storage = storage  # 共享的 Redis 客户端
        self.cleaner = ProxyCleaner()

    async def run(self):
        """
        主运行流程
        """
        while True:
            try:
                # 1. 获取代理
                raw_proxies = await self.fetcher.fetch_proxies()
                logger.info(f"获取原始代理 {len(raw_proxies)} 个")

                # 2. 验证代理
                valid_proxies: List[ProxyModel] = await self.validator.validate_proxy(
                    raw_proxies
                )
                logger.info(f"验证通过代理 {len(valid_proxies)} 个")

                # 3. 存储代理 逐个传入
                for valid_proxy in valid_proxies:
                    await self.storage.add(valid_proxy)

                # 4. 清理无效代理
                await self.cleaner.clean_invalid_proxies()

                # 等待下一次循环
                await asyncio.sleep(self.config.Fetch_INTERVAL)

            except Exception as e:
                logger.error(f"代理池运行异常: {e}")
                await asyncio.sleep(60)  # 异常后等待重试


async def start_api_server(port):
    """
    启动 API 服务
    """
    app = FastAPI(title="代理池服务")

    @app.get("/proxies", response_model=List[str])
    async def get_proxies(count: int = 10):
        """
        获取代理列表

        Args:
            count: 返回的代理数量

        Returns:
            代理列表
        """
        try:
            proxies = await storage.random_proxy(count)
            if not proxies:
                raise HTTPException(status_code=404, detail="代理列表为空")
            return proxies
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取代理列表出错: {str(e)}")

    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()


async def run_fetch_mode():
    """
    模式: fetch - 获取代理
    """
    fetcher = ProxyFetcher()
    raw_proxies = await fetcher.fetch_proxies()
    logger.info(f"获取代理 {len(raw_proxies)} 个")


async def run_validate_mode():
    """
    模式: validate - 验证代理
    """
    validator = ProxyValidator()
    proxies_str = await storage.get_all_proxies()
    proxies = ProxyFetcher().parse_proxy_list(proxies_str)
    valid_proxies = await validator.validate_proxy(proxies)

    for valid_proxy in valid_proxies:
        await storage.add(valid_proxy)

    logger.info(f"验证有效代理 {len(valid_proxies)} 个")


async def run_serve_mode():
    """
    模式: serve - 启动完整服务
    """
    # 启动代理池任务和API服务
    await asyncio.gather(
        ProxyPoolApplication().run(),  # 代理池任务
        start_api_server(5010),  # 启动 FastAPI 服务
    )


async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="代理池服务")
    parser.add_argument(
        "--mode",
        choices=["fetch", "validate", "serve"],
        default="serve",
        help="运行模式",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5010,
        help="API服务端口"
    )
    args = parser.parse_args()

    # 配置日志
    setup_logger(args.log_level)

    logger.info(f"启动模式: {args.mode}")

    # 根据不同模式执行
    if args.mode == "fetch":
        await run_fetch_mode()
    elif args.mode == "validate":
        await run_validate_mode()
    elif args.mode == "serve":
        await run_serve_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())  # 启动整个应用
    except KeyboardInterrupt:
        logger.info("服务已手动停止")
    except Exception as error:
        logger.error(f"服务启动失败: {error}")
