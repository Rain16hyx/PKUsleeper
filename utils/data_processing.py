"""睡眠数据分析与处理方法"""

from models import SleepRecord, SleepReport
from typing import Protocol


class SleepReportBuilder(Protocol):
    def build(self, record: SleepRecord) -> SleepReport:
        """初始化睡眠报告"""
        raise NotImplementedError

    def calculate_sleep_quality(record: SleepRecord) -> float:
        """计算单个睡眠记录的质量评分"""
        raise NotImplementedError

    def evaluate_environment(record: SleepRecord) -> str:
        """根据单个睡眠记录评估睡眠环境"""
        raise NotImplementedError

    def generate_report(record: SleepRecord) -> str:
        """从单个睡眠记录生成文本报告"""
        raise NotImplementedError
