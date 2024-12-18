# __main__.py
import asyncio
from utils.logger import setup_logger
from proxy_pool.main import main  # 从 main.py 导入 main 函数

if __name__ == "__main__":
    logger = setup_logger()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务已手动停止")
    except Exception as error:
        logger.error(f"服务启动失败: {error}")
