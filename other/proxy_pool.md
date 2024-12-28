# 《代理池验证器中的概数设计》
  
***

> **项目地址:**[ **proxy_pool by lgnorant_lu**](https://github.com/lgnorant-lu/proxy_pool)

***

## 1. 置信区间计算

**应用:** 评估代理成功率的可信范围, 判断代理的真实性能.

```txt
def calculate_confidence_interval(self, rate_sequence, confidence_level=0.95):
    if not rate_sequence:
        return 0.0, 0.0
    try:
        mean = np.mean(rate_sequence)
        std_error = stats.sem(rate_sequence)
        ci = stats.t.interval(confidence_level, len(rate_sequence)-1, loc=mean, scale=std_error)
        return max(0.0, ci[0]), min(1.0, ci[1])
    except Exception as e:
        self.logger.error(f"计算置信区间失败: {e}")
        return 0.0, 0.0
```

**数学原理:**  
$$
\left[ \bar{x} - t_{\alpha/2, n-1} \cdot \frac{s}{\sqrt{n}}, \bar{x} + t_{\alpha/2, n-1} \cdot \frac{s}{\sqrt{n}} \right]
$$  
[ x̄ - t(α/2,n-1) * s/√n, x̄ + t(α/2,n-1) * s/√n ]

**计算实例:**  
假设某代理近10次请求的成功率序列: [0.8, 0.85, 0.9, 0.87, 0.83, 0.88, 0.86, 0.89, 0.84, 0.82]

- 样本均值 $\bar{x} = 0.854$
- 样本标准差 $s = 0.0305$
- 自由度 $df = 9$
- 置信水平 95% ($\alpha = 0.05$)

查t分布表, $t_{0.025,9} = 2.262$

标准误 $SE = \frac{0.0305}{\sqrt{10}} \approx 0.00964$

置信区间:
$$
[0.854 - 2.262 \cdot 0.00964, 0.854 + 2.262 \cdot 0.00964] = [0.832, 0.876]
$$

如所示,有95%的置信度认为代理的真实成功率在83.2%到87.6%之间.

---

## 2. Z-score异常检测
**应用:** 识别响应时间中的异常值, 剔除性能不稳定的代理.

```txt
def detect_anomalies(self, response_times, threshold=2.0):
    if not response_times or len(response_times) < 2:
        return [False] * len(response_times)
    try:
        z_scores = np.abs(stats.zscore(response_times))
        return [z > threshold for z in z_scores]
    except Exception as e:
        self.logger.error(f"异常值检测失败: {str(e)}")
        return [False] * len(response_times)
```

**数学原理:**  
$$
Z = \frac{x - \mu}{\sigma}
$$  
Z = (x - μ) / σ

**计算实例:**  
> 1. 计算响应时间序列的均值($\mu$)和标准差($\sigma$)
> 2. 对每个响应时间$x$, 计算Z分数:
   $$
   Z = \frac{x - \mu}{\sigma}
   $$
> 3. 如果$|Z| > 2$, 则判定为异常值  

假设一组响应时间序列: [0.5, 0.6, 0.55, 2.1, 0.58, 0.52]

- $\mu = 0.81$
- $\sigma \approx 0.63$

Z-scores:

- $Z_1 = \frac{0.5 - 0.81}{0.63} \approx -0.49$
- $Z_2 = \frac{0.6 - 0.81}{0.63} \approx -0.33$
- $Z_3 = \frac{0.55 - 0.81}{0.63} \approx -0.41$
- $Z_4 = \frac{2.1 - 0.81}{0.63} \approx 2.05$
- $Z_5 = \frac{0.58 - 0.81}{0.63} \approx -0.37$
- $Z_6 = \frac{0.52 - 0.81}{0.63} \approx -0.46$

如所示, 2.1秒对应的Z分数为2.05, 大于2, 判定为异常值.

---

## 3. 贝叶斯概率更新
**应用:** 动态更新代理的可靠性估计, 随着新数据的加入不断调整概率估计.

```txt
def update_beta_parameters(self, alpha, beta, success=True):
    if success:
        alpha += 1
    else:
        beta += 1
    return alpha, beta
```

**数学原理:**  
$$
P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}
$$  
P(A|B) = P(B|A) * P(A) / P(B)

**计算实例:**  
> 简化为 Beta 分布更新:
> - 先验分布：Beta($\alpha$, $\beta$)
> - 观察到成功时，$\alpha' = \alpha + 1$
> - 观察到失败时，$\beta' = \beta + 1$

初始参数 $\alpha=2$, $\beta=1$

假设连续观察:

1. 成功: $\alpha=3$, $\beta=1$
2. 成功: $\alpha=4$, $\beta=1$
3. 失败: $\beta=2$

最终可靠性估计:
$$
\frac{\alpha}{\alpha + \beta} = \frac{4}{6} \approx 0.67
$$

按照计算所示,在观察到两次成功和一次失败后, 代理的可靠性估计为67%.

---

## 4. 指数衰减时间权重
```txt
def calculate_time_decay(self, hours_since_success, tau=24):
    return np.exp(-hours_since_success / tau)
```

**数学原理:**  
$$
w(t) = e^{-\frac{t}{\tau}}
$$  
w(t) = e^(-t/τ)

**计算实例:**  
假设某次检查距现在：

- 1小时: $w = e^{-1/24} \approx 0.959$
- 12小时: $w = e^{-12/24} \approx 0.607$
- 24小时: $w = e^{-24/24} \approx 0.368$

如所示, 越近的检查结果权重越大, 影响评分更多.

---

## 5. 综合评分系统
```txt
def calculate_detailed_score(self, proxy):
    try:
        success_rate_score = int(proxy.success_rate * 40.0)
        response_time_score = int(max(0.0, 25.0 - proxy.avg_response_time * 2.5))
        stability_score = int(15.0 * (1.0 - min(proxy.consecutive_failed_times / 5.0, 1.0)))
        recency_score = int(max(0.0, 10.0 * (1.0 - hours_since_check / 24.0)))
        reliability_score = int(self.calculate_reliability_score(proxy) * 10.0)
        total_score = success_rate_score * 0.4 + response_time_score * 0.25 + stability_score * 0.15 + reliability_score * 0.1 + recency_score * 0.1
        return ProxyScore(total_score, success_rate_score, response_time_score, stability_score, recency_score, reliability_score)
    except Exception as e:
        self.logger.error(f"计算详细评分失败: {str(e)}")
        return ProxyScore(0, 0, 0, 0, 0, 0)
```

**数学原理:**  
$$
Score = \sum_{i} (w_i \cdot s_i)
$$  
Score = Σ(w_i * s_i)

**计算实例:**  
假设代理数据:

- 成功率=0.85 (85分)
- 响应时间=0.6s (70分)
- 稳定性=0.9 (90分)
- 可靠性=0.7 (70分)
- 时效性=0.8 (80分)

最终得分:
$$
85 \cdot 0.4 + 70 \cdot 0.25 + 90 \cdot 0.15 + 70 \cdot 0.1 + 80 \cdot 0.1 = 80.5 \text{分}
$$

---