import asyncio
import argparse
from typing import List

from loguru import logger

from core.fetcher import ProxyFetcher
from core.validator import ProxyValidator
from core.storage import RedisProxyClient
from core.cleaner import ProxyCleaner
from models.proxy_model import ProxyModel
from utils.config import get_config
from utils.logger import setup_logger


class ProxyPoolApplication:
    def __init__(self):
        self.config = get_config()
        self.fetcher = ProxyFetcher()
        self.validator = ProxyValidator()
        self.storage = RedisProxyClient()
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
                valid_proxies: List[ProxyModel] = await self.validator.validate(raw_proxies)
                logger.info(f"验证通过代理 {len(valid_proxies)} 个")

                # 3. 存储代理
                await self.storage.save(valid_proxies)

                # 4. 清理无效代理
                await self.cleaner.clean()

                # 等待下一次循环
                await asyncio.sleep(self.config.fetch_interval)

            except Exception as error:
                logger.error(f"代理池运行异常: {error}")
                await asyncio.sleep(60)  # 异常后等待重试


def parse_arguments():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description="代理池服务")
    parser.add_argument("--mode",
                        choices=['fetch', 'validate', 'serve'],
                        default='serve',
                        help="运行模式")
    parser.add_argument("--log-level",
                        default="INFO",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help="日志级别")
    parser.add_argument("--port",
                        type=int,
                        default=5010,
                        help="API服务端口")
    return parser.parse_args()


async def start_api_server(port):
    """
    启动 API 服务
    """
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI(title="代理池服务")

    @app.get("/proxies")
    async def get_proxies(count: int = 10):
        storage = RedisProxyClient()
        return await storage.get(count)

    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    # 解析参数
    args = parse_arguments()

    # 配置日志
    setup_logger(args.log_level)

    logger.info(f"启动模式: {args.mode}")

    # 模式执行
    if args.mode == 'fetch':
        # 仅获取
        fetcher = ProxyFetcher()
        raw_proxies = await fetcher.fetch_proxies()
        logger.info(f"获取代理 {len(raw_proxies)} 个")

    elif args.mode == 'validate':
        # 仅验证
        validator = ProxyValidator()
        storage = RedisProxyClient()
        proxies = await storage.get_all()
        valid_proxies = await validator.validate(proxies)
        await storage.save(valid_proxies)
        logger.info(f"验证有效代理 {len(valid_proxies)} 个")

    elif args.mode == 'serve':
        # 启动完整服务
        await asyncio.gather(
            ProxyPoolApplication().run(),
            start_api_server(args.port)
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务已手动停止")
    except Exception as error:
        logger.error(f"服务启动失败: {error}")
