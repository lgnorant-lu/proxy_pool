"""
----------------------------------------------------------------
File name:                  proxy_model.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理模型定义模块
----------------------------------------------------------------

Changed history:            定义代理模型,包含统计特征
----------------------------------------------------------------
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ProxyModel:
    """
    代理模型,封装代理详细信息和统计特征

    包含:
    1. 基本代理信息
    2. 性能统计指标
    3. 状态更新方法
    """

    ip: str
    port: int
    protocol: str = "http"
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    last_check_time: datetime = field(default_factory=datetime.now)
    consecutive_failed_times: int = 0

    def update_stats(
            self,
            is_success: bool,
            response_time: float) -> None:
        """
        更新代理统计特征

        Args:
            is_success: 请求是否成功
            response_time: 响应时间
        """
        # 更新成功率
        total_checks = self.consecutive_failed_times + 1
        self.success_rate = (
                (self.success_rate * (total_checks - 1) + (1 if is_success else 0))
                / total_checks
        )

        # 更新响应时间
        self.avg_response_time = (
                (self.avg_response_time * (total_checks - 1) + response_time)
                / total_checks
        )

        # 更新失败次数
        if is_success:
            self.consecutive_failed_times = 0
        else:
            self.consecutive_failed_times += 1

        # 更新最后检查时间
        self.last_check_time = datetime.now()

    def __str__(self) -> str:
        """
        代理模型字符串表示

        Returns:
            代理信息的可读字符串
        """
        return (
            f"Proxy: {self.ip}:{self.port} "
            f"(Protocol: {self.protocol}, "
            f"Success Rate: {self.success_rate:.2%}, "
            f"Avg Response Time: {self.avg_response_time:.2f}s)"
        )
