"""
----------------------------------------------------------------
File name:                  statistical_model.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理统计模型与评估模块
----------------------------------------------------------------

Changed history:            实现基于统计的代理评估算法
                            2024/12/25: 增加时序分析和异常检测
----------------------------------------------------------------
"""

import numpy as np
from scipy import stats
from datetime import datetime
from typing import List, Tuple, Dict, Sequence
from dataclasses import dataclass

from proxy_pool.models.proxy_model import ProxyModel
from proxy_pool.utils.config import ProxyConfig
from proxy_pool.utils.logger import setup_logger


@dataclass
class ProxyScore:
    """ 代理评分详情 """
    total_score: int
    success_rate_score: int
    response_time_score: int
    stability_score: int
    recency_score: int
    reliability_score: int


class ProxyStatisticalModel:
    """ 代理统计评估模型 """
    def __init__(self):
        """ 初始化统计模型 """
        self.config = ProxyConfig()
        self.logger = setup_logger()

    def calculate_confidence_interval(
        self,
        rate_sequence: Sequence[float],
        confidence_level: float = 0.95,
    ) -> Tuple[float, float]:
        """
        计算成功率置信区间

        Args:
            rate_sequence: 成功率序列
            confidence_level: 置信水平

        Returns:
            置信区间 (下限, 上限)
        """
        if not rate_sequence:
            return 0.0, 0.0

        try:
            mean = float(np.mean(rate_sequence))
            if len(rate_sequence) < 2:
                return mean, mean

            std_error = float(stats.sem(rate_sequence))
            # confidence_interval
            ci = stats.t.interval(
                confidence_level,
                len(rate_sequence) - 1,
                loc=mean,
                scale=std_error,
            )
            return max(0.0, ci[0]), min(1.0, ci[1])

        except Exception as e:
            self.logger.error(f"计算置信区间失败: {e}")
            return 0.0, 0.0

    def detect_anomalies(
            self,
            response_times: List[float],
            threshold: float = 2.0
    ) -> List[bool]:
        """
        检测响应时间异常值

        Args:
            response_times: 响应时间列表
            threshold: Z分数阈值

        Returns:
            异常值标记列表
        """
        if not response_times or len(response_times) < 2:
            return [False] * len(response_times)

        try:
            z_scores = np.abs(stats.zscore(response_times))
            return [z > threshold for z in z_scores]
        except Exception as e:
            self.logger.error(f"异常值检测失败: {str(e)}")
            return [False] * len(response_times)

    def calculate_reliability_score(
            self,
            proxy: ProxyModel,
            window_size: int = 10
    ) -> float:
        """
        计算代理可靠性得分

        Args:
            proxy: 代理模型
            window_size: 时间窗口大小

        Returns:
            可靠性得分 (0-1)
        """
        if not proxy.response_times:
            return 0.0

        recent_times = proxy.response_times[-window_size:]

        try:
            # 计算稳定性
            stability = 1.0 - np.std(recent_times) / np.mean(recent_times)

            # 计算异常比例
            anomaly_flags = self.detect_anomalies(recent_times)
            anomaly_ratio = 1.0 - sum(anomaly_flags) / len(anomaly_flags)

            # 计算时间衰减
            time_decay = 0.0
            if proxy.last_success_time:
                hours_since_success = (
                                              datetime.now() - proxy.last_success_time
                                      ).total_seconds() / 3600
                time_decay = np.exp(-hours_since_success / 24)  # 24小时衰减

            return stability * 0.4 + anomaly_ratio * 0.4 + time_decay * 0.2

        except Exception as e:
            self.logger.error(f"计算可靠性得分失败: {str(e)}")
            return 0.0

    def calculate_detailed_score(
            self,
            proxy: ProxyModel
    ) -> ProxyScore:
        """
        计算详细的代理评分

        Args:
            proxy: 代理模型

        Returns:
            详细评分对象
        """
        try:
            # 成功率得分 (40分)
            success_rate_score = int(proxy.success_rate * 40.0)

            # 响应时间得分 (25分)
            response_time_score = int(
                max(0.0, 25.0 - proxy.avg_response_time * 2.5)
            )

            # 稳定性得分 (15分)
            stability_score = int(
                15.0 * (1.0 - min(proxy.consecutive_failed_times / 5.0, 1.0))
            )

            # 时效性得分 (10分)
            recency_score = 0.0
            if proxy.last_check_time:
                hours_since_check = (
                                            datetime.now() - proxy.last_check_time
                                    ).total_seconds() / 3600.0
                recency_score = int(
                    max(0.0, 10.0 * (1.0 - hours_since_check / 24.0))
                )

            # 可靠性得分 (10分)
            reliability_score = int(
                self.calculate_reliability_score(proxy) * 10.0
            )

            # 总分
            total_score = sum([
                success_rate_score,
                response_time_score,
                stability_score,
                recency_score,
                reliability_score
            ])

            # 确保在有效范围内
            total_score = max(
                self.config.MIN_SCORE,
                min(total_score, self.config.MAX_SCORE)
            )

            return ProxyScore(
                total_score=total_score,
                success_rate_score=success_rate_score,
                response_time_score=response_time_score,
                stability_score=stability_score,
                recency_score=recency_score,
                reliability_score=reliability_score
            )

        except Exception as e:
            self.logger.error(f"计算详细评分失败: {str(e)}")
            return ProxyScore(0, 0, 0, 0, 0, 0)

    def evaluate_proxy_quality(
            self,
            proxy_models: List[ProxyModel]
    ) -> Dict[str, ProxyScore]:
        """
        批量评估代理质量

        Args:
            proxy_models: 代理模型列表

        Returns:
            代理质量评估结果
        """
        results = {}
        for proxy in proxy_models:
            try:
                proxy_key = f"{proxy.ip}:{proxy.port}"
                results[proxy_key] = self.calculate_detailed_score(proxy)
            except Exception as e:
                self.logger.error(f"评估代理质量失败 {proxy.ip}:{proxy.port}: {str(e)}")

        return results


if __name__ == "__main__":
    # 测试代码
    model = ProxyStatisticalModel()

    # 创建测试代理
    test_proxy = ProxyModel(
        ip="220.248.70.237",
        port=9002,
        response_times=[0.1, 0.2, 0.15, 0.3, 0.25]
    )

    # 测试置信区间
    rate_sequence = [0.8, 0.85, 0.9, 0.87, 0.83]
    ci_low, ci_high = model.calculate_confidence_interval(rate_sequence)
    print(f"置信区间: ({ci_low:.2f}, {ci_high:.2f})")

    # 测试异常检测
    anomalies = model.detect_anomalies(test_proxy.response_times)
    print(f"异常值检测结果: {anomalies}")

    # 测试评分计算
    score = model.calculate_detailed_score(test_proxy)
    print(f"代理评分详情:")
    print(f"总分: {score.total_score}")
    print(f"成功率得分: {score.success_rate_score}")
    print(f"响应时间得分: {score.response_time_score}")
    print(f"稳定性得分: {score.stability_score}")
    print(f"时效性得分: {score.recency_score}")
    print(f"可靠性得分: {score.reliability_score}")
