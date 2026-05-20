"""睡眠数据分析与处理方法"""

from models import SleepRecord, SleepReport
from typing import Protocol


class SleepReportBuilder(Protocol):
    def calculate_sleep_quality(record: SleepRecord) -> float:
        """计算睡眠质量评分"""
        raise NotImplementedError

    def evaluate_environment(record: SleepRecord) -> float:
        """计算睡眠环境评分"""
        raise NotImplementedError

    def sleep_score(record: SleepRecord) -> float:
        """综合睡眠质量和环境评分等，计算最终睡眠得分"""
        raise NotImplementedError

    def generate_report(record: SleepRecord) -> str:
        """打印文本版睡眠报告摘要"""
        raise NotImplementedError

    def build(self, record: SleepRecord) -> SleepReport:
        """综合各项分析结果，生成最终睡眠报告"""
        raise NotImplementedError
