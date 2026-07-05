from __future__ import annotations

from pkusleeper.domain import SleepRecord, SleepReport, SleepType


class SleepReportBuilder():
    # 注意该函数只能处理单条睡眠记录评分；如果计算每日总分（包括 nap），需要在外部累加。

    def calculate_sleep_quality(self,record: SleepRecord) -> float:
        """计算睡眠质量评分"""
        # 输入：一条睡眠记录（night/nap）。
        # 输出：该记录的睡眠质量分。
        # night：0-100，nap：0-20。
        # 评分标准：睡眠类型、睡眠时长达标情况、睡眠中断次数和时长。
        
        #判断睡眠数据是否完整：
        if not record.started_at or not record.ended_at:
            return 0.0
        
        duration_minutes=(record.ended_at - record.started_at).total_seconds() / 60
        if record.sleep_type == SleepType.NIGHT:
            # 睡眠时长占 45 分。
            expected=record.expected_duration_minutes or 480
            rate=duration_minutes/expected
            duration_score=min(rate,1)*45

            # 入睡时间占 25 分。
            if record.expected_start_time==None:
                go_to_bed_time_score=25
            elif record.started_at.time()<=record.expected_start_time.time():
                go_to_bed_time_score=25
            else:
                # 目标入睡时间只表示钟点，不能直接拿日期相减。
                start_minutes=record.started_at.hour*60+record.started_at.minute
                expected_minutes=record.expected_start_time.hour*60+record.expected_start_time.minute
                if start_minutes<12*60:
                    start_minutes+=24*60
                if expected_minutes<12*60:
                    expected_minutes+=24*60
                delay_time_minutes=max(0,start_minutes-expected_minutes)
                go_to_bed_time_score=max(0.0,25*(expected-delay_time_minutes)/expected)

            # 睡眠中断占 30 分：每次中断 <=5 分钟扣 5 分，>5 分钟时每多 2 分钟再扣 1 分。
            interruption_score=30
            for every_interruption in record.interruptions:
                if every_interruption.ended_at and every_interruption.started_at:
                    interruption_duration_minutes=(every_interruption.ended_at-every_interruption.started_at).total_seconds()/60 
                else:
                    interruption_duration_minutes=1
                if interruption_duration_minutes<=5:
                    interruption_score-=5
                else:
                    interruption_score-=(5+(interruption_duration_minutes-5)/2)
            interruption_score=max(interruption_score,0)
            score_for_night_quality=duration_score+go_to_bed_time_score+interruption_score
            return score_for_night_quality
        
        if record.sleep_type == SleepType.NAP:
            # nap 时长占 20 分：0-30 分钟得 20 分，30-60 分钟得 10 分，>60 分钟得 0 分。
            if duration_minutes<=30:
                score_for_nap=20
            elif duration_minutes<=60:
                score_for_nap=10
            else:
                score_for_nap=0
            return score_for_nap
        return 0.0


    def generate_report(self,record: SleepRecord) -> str:
        """打印文本版睡眠报告摘要"""
        raise NotImplementedError

    def build(self, record: SleepRecord) -> SleepReport:
        """综合各项分析结果，生成单次睡眠记录对应评估结果"""
        actual_duration_minutes=(record.ended_at - record.started_at).total_seconds() / 60
        quality_score=self.calculate_sleep_quality(record)
        interruption_count=len(record.interruptions)
        summary=(f"record_id:{record.record_id}\n"
                 f"user_id:{record.user_id}\n"
                 f"started_at:{record.started_at}\n"
                 f"ended_at:{record.ended_at}\n"
                 f"environment:{record.environment}\n"
                 f"interruption: {interruption_count} times\n"
                 f"quality_score:{quality_score}\n")
        return SleepReport(record,actual_duration_minutes,interruption_count,quality_score,summary)
