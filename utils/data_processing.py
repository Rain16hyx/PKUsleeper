"""睡眠数据分析与处理方法"""
#Q:如果睡眠数据不完整，是否考虑提示用户补全？目前方法是直接返回0分
from models import SleepRecord,SleepEnvironment,SleepInterruption
from typing import Protocol
from storage import *
from datetime import *
from pathlib import Path
# 获取record的评分：
# grader = SleepReportBuilder()   
# score=grader.calculate_sleep_quality(record)
class SleepReportBuilder():
    #注意该函数只能处理单个睡眠记录评分，如果计算每天睡眠总分（即包括nap），需要在外部把两个评分相加

    def calculate_sleep_quality(self,record: SleepRecord) -> float:
        """计算睡眠质量评分"""
        #input:a sleep record(night/nap)
        #output:a sleep quality score for this sleep record
        #night:0-100, nap:0-20
        #评分标准：睡眠类型（晚上or午睡），睡眠时长达标情况，睡眠中断次数和时长
        
        #判断睡眠数据是否完整：
        if not record.started_at or not record.ended_at:
            return 0.0
        
        duration_minutes=(record.ended_at - record.started_at).total_seconds() / 60
        if record.sleep_type=="night":
            #45 for duration
            expected=record.expected_duration_minutes or 480
            rate=duration_minutes/expected
            duration_score=min(rate,1)*45

            #25 for go-to-bed-time
            if record.expected_start_time==None:
                go_to_bed_time_score=25
            elif record.started_at.time()<=record.expected_start_time.time():
                go_to_bed_time_score=25
            else:
                delay_time_minutes=(record.started_at-record.expected_start_time).total_seconds()/60
                go_to_bed_time_score=max(0.0,25*(record.expected_duration_minutes-delay_time_minutes)/record.expected_duration_minutes)

            #30 for interruptions：每次间断，<=5min-5，>5min多5分钟每2min扣1分，最多30分
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
        
        if record.sleep_type=="nap":
            #20 for nap duration: 0-30min:20, 30-60min:10, >60min:0
            if duration_minutes<=30:
                score_for_nap=20
            elif duration_minutes<=60:
                score_for_nap=10
            else:
                score_for_nap=0
            return score_for_nap


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
        
    
class StatisticDataAnalyzer:
    def __init__(self,user_id: str, data_dir: Path | str):
        self.user_id=user_id
        self.data_dir=data_dir
    #平均睡眠时长
    #达标率
    #睡眠时长统计图
    #入睡时间统计图

    def get_filtered_records(self,days):
        '''筛选出距当前时刻days天内的所有night睡眠数据'''
        get_data=SleepRecordRepository(self.user_id,self.data_dir)
        now=datetime.now()
        start_time=now-timedelta(days=days)
        return [r for r in get_data.user_list(self.user_id) if r.started_at>=start_time and r.sleep_type=="night"]
    
    def calculate_avg_durationtime(self,all_night_records:list[SleepRecord]):
        '''计算平均睡眠时长minutes'''
        all_complete_night_records=[]
        for r in all_night_records:
            if r.started_at and r.ended_at:
                all_complete_night_records.append(r)
        days=len(all_complete_night_records)
        average=0.0
        if days==0:
            return 0.0
        for r in all_complete_night_records:
            duration_minutes=(r.ended_at - r.started_at).total_seconds() / 60
            average+=duration_minutes/days
        #注意还要转换成时+分格式
        return average
    
    def calculate_reachgoal_rate(self,all_night_records:list[SleepRecord]):
        '''计算睡眠时长达标的数据占比(night)(0-1格式)'''
        all_complete_night_records=[]
        for r in all_night_records:
            if r.started_at and r.ended_at:
                all_complete_night_records.append(r)
        recorded_days=len(all_complete_night_records)
        if recorded_days==0:
            return 0.0
        achieved_days=0
        for r in all_complete_night_records:
            duration_minutes=(r.ended_at - r.started_at).total_seconds() / 60
            if not r.expected_duration_minutes:
                expected_duration=480
            else:
                expected_duration=r.expected_duration_minutes
            if duration_minutes>=expected_duration:
                achieved_days+=1
        return achieved_days/recorded_days

    #生成统计图时，若天数过多，可把几天平均作为单个数据点
    def last_month():
        raise NotImplementedError
    def last_3months():
        raise NotImplementedError
    def last_6months():
        raise NotImplementedError
    



# @dataclass(frozen=True, slots=True)
# class SleepRecord:
#     record_id: str
#     user_id: str
#     started_at: datetime
#     ended_at: datetime
#     expected_duration_minutes: int | None
#     sleep_type: SleepType
#     environment: SleepEnvironment
#     interruptions: tuple[SleepInterruption, ...] = ()