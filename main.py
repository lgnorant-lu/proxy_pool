import asyncio
import argparse
import sys
from datetime import datetime
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from prometheus_client import Counter, Gauge
import uvicorn
from loguru import logger

from proxy_pool.core.fetcher import ProxyFetcher
from proxy_pool.core.validator import ProxyValidator
from proxy_pool.core.storage import RedisProxyClient
from proxy_pool.core.cleaner import ProxyCleaner
# from proxy_pool.models.proxy_model import ProxyModel
from proxy_pool.utils.config import Settings
from proxy_pool.utils.logger import setup_logger


# 全局配置
settings = Settings()

# 全局共享的 Redis 客户端实例
storage = RedisProxyClient()


class Metrics:
    """ 监控指标 """
    def __init__(self):
        self.proxy_total = Gauge(
            "proxy_pool_total",
            "Total number of proxies"
        )
        self.proxy_valid = Gauge(
            "proxy_pool_valid",
            "Number of valid proxies"
        )
        self.fetch_counter = Counter(
            "proxy_pool_fetch_total",
            "Total number of fetch operations"
        )
        self.api_requests = Counter(
            "proxy_pool_api_requests",
            "Total number of API requests",
            ["endpoint", "method"]
        )


metrics = Metrics()


class ProxyResponse(BaseModel):
    """代理响应模型"""
    proxies: List[str]
    count: int
    timestamp: datetime


class ProxyPoolApplication:
    def __init__(self):
        self.config = settings
        self.fetcher = ProxyFetcher()
        self.validator = ProxyValidator()
        self.storage = storage  # 共享的 Redis 客户端
        self.cleaner = ProxyCleaner()
        self._running = True  # 控制运行状态

    async def stop(self):
        """ 关闭程序 """
        self._running = False
        # 清理资源
        logger.info("正在关闭代理池应用...")
        self.storage.close()

        await self.fetcher.close()
        logger.info("代理池应用已关闭")

    async def run(self):
        """ 主运行流程 """
        try:
            while self._running:
                try:
                    await self._run_cycle()
                except Exception as e:
                    logger.error(f"代理池运行异常: {e}")
                    await asyncio.sleep(60)
        finally:
            await self.stop()

    async def _run_cycle(self):
        """ 单次运行循环 """
        try:
            # 更新指标
            metrics.fetch_counter.inc()

            # 1. 获取代理
            raw_proxies = await self.fetcher.fetch_all()
            logger.info(f"获取原始代理 {len(raw_proxies)} 个")
            metrics.proxy_total.set(len(raw_proxies))

            # 2. 验证代理
            valid_proxies = await self.validator.validate_proxy(raw_proxies)
            logger.info(f"验证通过代理 {len(valid_proxies)} 个")
            metrics.proxy_valid.set(len(valid_proxies))

            # 3. 存储代理
            for proxy in valid_proxies:
                await self.storage.add(proxy)

            # 4. 清理无效代理
            await self.cleaner.clean_invalid_proxies()

            # 等待下一次循环
            await asyncio.sleep(self.config.FETCH_INTERVAL)

        except Exception as e:
            logger.error(f"代理池运行循环发生异常: {e}")
            raise


# FastAPI 应用
@asynccontextmanager
async def lifespan(app: FastAPI):
    """ FastAPI 生命周期管理 """
    # 启动时
    logger.info("API服务启动...")
    yield
    # 关闭时
    logger.info("API服务关闭...")
    storage.close()

app = FastAPI(
    title="代理池服务",
    description="高性能代理池服务",
    version="1.0.0",
    lifespan=lifespan
)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    """ 请求追踪中间件 """
    metrics.api_requests.labels(
        endpoint=request.url.path,
        method=request.method
    ).inc()
    return await call_next(request)


@app.get("/proxies", response_model=ProxyResponse)
async def get_proxies(
    count: int = Query(default=10, ge=1, le=100),
    # protocol: Optional[str] = Query(default=None, regex="^(http|https)?$")
):
    """ 获取代理列表 """
    try:
        proxies = await storage.random_proxy(count)
        if not proxies:
            raise HTTPException(
                status_code=404,
                detail="No proxies available"
            )
        return ProxyResponse(
            proxies=proxies,
            count=len(proxies),
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.exception("获取代理失败")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/stats")
async def get_stats():
    """ 获取统计信息 """
    try:
        total = await storage.get_proxy_count()
        return {
            "total": total,
            "fetch_count": metrics.fetch_counter.value.get(),
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.exception("获取统计信息失败")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


async def start_api_server(port: int):
    """
    启动 API 服务
    """
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_fetch_mode():
    """
    模式: fetch - 获取代理
    """
    fetcher = ProxyFetcher()

    try:
        raw_proxies = await fetcher.fetch_all()
        logger.info(f"获取代理 {len(raw_proxies)} 个")
    finally:
        await fetcher.close()


async def run_validate_mode():
    """
    模式: validate - 验证代理
    """
    try:
        validator = ProxyValidator()
        proxies_str = await storage.get_all_proxies()
        valid_proxies = await validator.validate_proxy(proxies_str)

        async with storage.pipeline() as pipe:
            for proxy in valid_proxies:
                await pipe.add(proxy)

        logger.info(f"验证有效代理 {len(valid_proxies)} 个")
    finally:
        await storage.close()


async def run_serve_mode():
    """
    模式: serve - 启动完整服务
    """
    # 启动代理池任务和API服务
    app_ = ProxyPoolApplication()
    try:
        await asyncio.gather(
            app_.run(),
            start_api_server(settings.API_PORT)
        )
    except asyncio.CancelledError:
        logger.info("服务停止中...")
    finally:
        await app_.stop()


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
    # parser.add_argument(
    #     "--port",
    #     type=int,
    #     default=5010,
    #     help="API服务端口"
    # )
    args = parser.parse_args()

    # 配置日志
    setup_logger(args.log_level)
    logger.info(f"启动模式: {args.mode}")

    try:
        if args.mode == "fetch":
            await run_fetch_mode()
        elif args.mode == "validate":
            await run_validate_mode()
        elif args.mode == "serve":
            await run_serve_mode()
    except KeyboardInterrupt:
        logger.info("服务已手动停止")
    except Exception as e:
        logger.exception(f"服务启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())  # 启动整个应用
    except KeyboardInterrupt:
        logger.info("服务已手动停止")
    except Exception as error:
        logger.error(f"服务启动失败: {error}")
