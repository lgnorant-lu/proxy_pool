"""
----------------------------------------------------------------
File name:                  logger.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                日志管理模块
----------------------------------------------------------------

Changed history:            初始化日志配置,提供统一日志接口
                            2024/12/24: 重构日志系统,增加更多功能支持
----------------------------------------------------------------
"""

import logging
import sys
import json
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime


class LogConfigError(Exception):
    """ 日志配置异常 """
    pass


class JsonFormatter(logging.Formatter):
    """ 自定义 Json 格式化器 """
    def format(self, record: logging.LogRecord) -> str:
        """ Json 格式化日志记录 """
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        return json.dumps(log_data, ensure_ascii=False)


class ProxyPoolLogger:
    """
    代理池日志管理器

    特性:
    1. 多种日志处理器支持
    2. 日志结构自动轮转
    3. 结构化日志记录
    4. 不同级别日志隔离存储
    """
    def __init__(
        self,
        name: str = "proxy_pool",
        level: str = "DEBUG",  # DEBUG 以显示所有级别日志
        log_dir: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        console: bool = True,
        json_format: bool = False,
    ):
        """
        初始化日志管理器

        Args:
            name: 日志记录器名称
            level: 日志记录级别
            log_dir: 日志文件存储目录
            max_bytes: 单个日志文件大小
            backup_count: 日志备份数量
            console: 是否输出到控制台
            json_format: 是否使用 JSON 格式记录
        """
        # 日志格式
        self.DETAILED_FORMAT = (
            '%(asctime)s [%(levelname)s] '
            '%(filename)s:%(lineno)d - %(funcName)s:%(message)s'
        )
        self.SIMPLE_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'

        try:
            self.logger = logging.getLogger(name)
            self.logger.setLevel(getattr(logging, level.upper()))
            self.json_format = json_format

            # 避免重复处理
            if self.logger.handlers:
                self.logger.handlers.clear()

            # 日志目录设置
            if log_dir:
                self.log_dir = Path(log_dir)
                self.log_dir.mkdir(parents=True, exist_ok=True)

                # 清理之前的日志文件
                log_file = self.log_dir / "proxy_pool.log"
                error_file = self.log_dir / "error.log"
                if log_file.exists():
                    log_file.unlink()
                if error_file.exists():
                    error_file.unlink()

                # 常规日志文件处理器
                self._add_file_handler(
                    filename="proxy_pool.log",
                    level=logging.DEBUG,  # level setting
                    max_bytes=max_bytes,
                    backup_count=backup_count,
                )

                # 错误日志文件处理器
                self._add_file_handler(
                    filename="error.log",
                    level=logging.ERROR,
                    max_bytes=max_bytes,
                    backup_count=backup_count,
                )

            # 控制台处理器
            if console:
                self._add_console_handler()

        except Exception as e:
            raise LogConfigError(f"日志系统初始化嘎了: {e}")

    def _get_formatter(self) -> logging.Formatter:
        """ 获取日志处理器 """
        if self.json_format:
            return JsonFormatter()
        else:
            return logging.Formatter(self.DETAILED_FORMAT)

    def _add_file_handler(
        self,
        filename: str,
        level: int = logging.DEBUG,  # level setting
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        """ 添加文件处理器 """
        file_handler = RotatingFileHandler(
            self.log_dir / filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(file_handler)

    def _add_console_handler(self) -> None:
        """ 添加控制台处理器 """
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)  # 输出所有级别日志
        console_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(console_handler)

    def _log(
            self,
            level: int,
            msg: str,
            extra: Optional[Dict[str, Any]] = None,
            *args,
            **kwargs
    ) -> None:
        """统一的日志记录方法"""
        if extra:
            kwargs['extra'] = extra
        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs) -> None:
        """记录调试日志"""
        self._log(logging.DEBUG, msg, extra, *args, **kwargs)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs) -> None:
        """记录信息日志"""
        self._log(logging.INFO, msg, extra, *args, **kwargs)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs) -> None:
        """记录警告日志"""
        self._log(logging.WARNING, msg, extra, *args, **kwargs)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs) -> None:
        """记录错误日志"""
        self._log(logging.ERROR, msg, extra, *args, **kwargs)

    def critical(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs) -> None:
        """记录严重错误日志"""
        self._log(logging.CRITICAL, msg, extra, *args, **kwargs)


_logger_instance = None


def setup_logger(
        name: str = "proxy_pool",
        level: str = "INFO",
        log_dir: Optional[str] = None,
        **kwargs
) -> ProxyPoolLogger:
    """
    获取或创建日志管理器实例

    Args:
        name: 日志器名称
        level: 日志级别
        log_dir: 日志目录
        **kwargs: 其他配置参数

    Returns:
        日志管理器实例
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ProxyPoolLogger(name, level, log_dir, **kwargs)
    return _logger_instance


if __name__ == "__main__":
    # 测试日志功能
    try:
        # 确保日志目录存在且清空
        log_dir = Path("logs")
        if log_dir.exists():
            for file in log_dir.glob("*.log"):
                file.unlink()

        # 创建logger实例，明确指定DEBUG级别
        logger = setup_logger(
            name="test_logger",
            level="DEBUG",
            log_dir="logs",
            json_format=True
        )

        # 添加一些额外的debug信息
        print("开始测试日志系统...")
        print(f"Logger level: {logger.logger.level}")
        print(f"Handler levels: {[handler.level for handler in logger.logger.handlers]}")

        # 测试所有级别的日志
        logger.debug("这是一条调试日志 [DEBUG]", extra={"user": "test"})
        logger.info("这是一条信息日志 [INFO]", extra={"action": "test"})
        logger.warning("这是一条警告日志 [WARNING]")
        logger.error("这是一条错误日志 [ERROR]", extra={"error_code": 500})
        logger.critical("这是一条严重错误日志 [CRITICAL]")

        print("\n当前日志文件内容:")
        log_file = Path("logs/proxy_pool.log")
        if log_file.exists():
            print(log_file.read_text(encoding='utf-8'))

    except LogConfigError as e:
        print(f"日志配置错误: {e}")
    except Exception as e:
        print(f"未知错误: {str(e)}")
