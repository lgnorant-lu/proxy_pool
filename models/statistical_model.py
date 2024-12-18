"""
----------------------------------------------------------------
File name:                  statistical_model.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理统计模型与评估模块
----------------------------------------------------------------

Changed history:            实现基于统计的代理评估算法
----------------------------------------------------------------
"""

import numpy as np
from scipy import stats
from datetime import datetime
from typing import List, Tuple, Dict

# 显式导入模型和配置
from .proxy_model import ProxyModel
from ..utils.config import ProxyConfig


class ProxyStatisticalModel:
    """
    代理统计评估模型

    提供基于统计的代理评估方法:
    1. 置信区间计算
    2. 贝叶斯概率更新
    3. 代理评分计算
    """

    @staticmethod
    def calculate_confidence_interval(
        success_rates: List[float],
        confidence_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        计算成功率置信区间

        Args:
            success_rates: 成功率列表
            confidence_level: 置信水平

        Returns:
            置信区间 (下限, 上限)
        """
        # 处理空列表情况
        if not success_rates:
            return 0.0, 0.0

        mean = np.mean(success_rates)
        std_error = stats.sem(success_rates)

        return stats.t.interval(
            confidence_level,
            len(success_rates) - 1,
            loc=mean,
            scale=std_error
        )

    @staticmethod
    def bayesian_update(
        prior_alpha: float,
        prior_beta: float,
        new_success: bool
    ) -> Tuple[float, float]:
        """
        贝叶斯概率更新

        Args:
            prior_alpha: 先验成功次数
            prior_beta: 先验失败次数
            new_success: 新的结果

        Returns:
            更新后的 (alpha, beta)
        """
        if new_success:
            return prior_alpha + 1, prior_beta
        else:
            return prior_alpha, prior_beta + 1

    @classmethod
    def proxy_score_calculation(
        cls,
        proxy_model: ProxyModel,
        config: ProxyConfig = ProxyConfig()
    ) -> int:  # 修改为 int 类型
        """
        基于统计特征计算代理评分

        Args:
            proxy_model: 代理模型
            config: 配置参数

        Returns:
            代理评分(整数)
        """
        # 成功率权重
        success_rate_weight = int(proxy_model.success_rate * 100)

        # 响应时间惩罚
        response_time_penalty = max(
            0,
            int(100 - proxy_model.avg_response_time * 10)
        )

        # 最近检查时间奖励
        recency_bonus = 0
        if proxy_model.last_check_time:
            hours_since_check = (
                datetime.now() - proxy_model.last_check_time
            ).total_seconds() / 3600
            recency_bonus = max(0, int(10 - hours_since_check))

        # 总体评分计算
        total_score = (
            success_rate_weight +
            response_time_penalty +
            recency_bonus
        )

        # 确保评分在合理范围
        return max(
            config.MIN_SCORE,
            min(int(total_score), config.MAX_SCORE)
        )

    @classmethod
    def evaluate_proxy_quality(
        cls,
        proxy_models: List[ProxyModel]
    ) -> Dict[str, int]:  # 修改返回值类型为 int
        """
        批量评估代理质量

        Args:
            proxy_models: 代理模型列表

        Returns:
            代理质量评估结果
        """
        return {
            f"{proxy.ip}:{proxy.port}": cls.proxy_score_calculation(proxy)
            for proxy in proxy_models
        }
