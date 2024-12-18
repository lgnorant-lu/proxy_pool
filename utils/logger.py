"""
----------------------------------------------------------------
File name:                  logger.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                日志管理模块
----------------------------------------------------------------

Changed history:            初始化日志配置,提供统一日志接口
----------------------------------------------------------------
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(
    name: str = "proxy_pool",
    log_level: int = logging.INFO,
    # log_file: Optional[str] = None,
    # log_max_bytes: int = 1024 * 1024 * 10,  # 10MB
    log_dir: Optional[str] = None,
    # log_max_files: int = 5,  # 5个备份
) -> logging.Logger:
    """
    配置日志记录器

    Args:
        name: 日志记录器名称
        log_level: 日志记录级别
        log_dir: 日志文件存储目录

    Returns:
        配置好的日志记录器
    """
    # 日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # 格式化
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 控制台处理器添加格式化
    console_handler.setFormatter(formatter)

    # 日志记录器添加处理器
    logger.addHandler(console_handler)

    # 若有指定日志文件路径，添加文件处理器

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, f"{name}.log"),
            maxBytes=1024 * 1024 * 10,  # 10MB
            backupCount=5,  # 10个备份
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
