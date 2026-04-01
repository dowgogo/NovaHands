"""
价值量化模块

量化用户价值和系统价值，用于评估 NovaHands 的实际贡献。
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json
import os


class ValueType(Enum):
    """价值类型"""
    TIME_SAVED = "time_saved"
    ACCURACY_GAIN = "accuracy_gain"
    EFFICIENCY_GAIN = "efficiency_gain"
    LEARNING_VALUE = "learning_value"


class TaskStatus(Enum):
    """任务状态"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class ExecutionRecord:
    """执行记录"""
    task_id: str
    user_id: str
    skill_name: str
    description: str
    status: TaskStatus
    duration: float  # 执行时间（秒）
    estimated_manual_time: float  # 估算手动执行时间（秒）
    error_count: int = 0
    user_rating: Optional[int] = None  # 用户评分（1-5）
    timestamp: datetime = None
    complexity: float = 1.0  # 任务复杂度（1-5）
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def calculate_time_saved(self, hourly_rate: float = 100.0) -> float:
        """
        计算时间节省的价值
        
        Args:
            hourly_rate: 用户时薪（默认 100 元/小时）
            
        Returns:
            节省时间的价值（元）
        """
        time_saved_seconds = self.estimated_manual_time - self.duration
        time_saved_hours = max(0, time_saved_seconds) / 3600
        return time_saved_hours * hourly_rate
    
    def calculate_accuracy_gain(self, avg_error_cost: float = 200.0) -> float:
        """
        计算准确性提升的价值
        
        Args:
            avg_error_cost: 平均错误成本（默认 200 元/错误）
            
        Returns:
            准确性提升的价值（元）
        """
        # 假设手动执行有 5% 的错误率，自动执行错误率降低到 0.5%
        manual_error_rate = 0.05
        auto_error_rate = self.error_count / max(1, int(self.estimated_manual_time / 60))
        
        errors_avoided = max(0, manual_error_rate - auto_error_rate)
        return errors_avoided * avg_error_cost
    
    def calculate_efficiency_gain(self, base_output: float = 5000.0) -> float:
        """
        计算效率提升的价值
        
        Args:
            base_output: 基础产出（默认 5000 元/天）
            
        Returns:
            效率提升的价值（元）
        """
        efficiency_gain = (self.estimated_manual_time / self.duration - 1) * self.complexity
        return efficiency_gain * base_output * (self.duration / 28800)  # 8小时 = 28800秒
    
    def calculate_learning_value(self, skill_value: float = 500.0) -> float:
        """
        计算学习价值
        
        Args:
            skill_value: 技能的市场价值（默认 500 元）
            
        Returns:
            学习价值（元）
        """
        # 学习价值 = 技能复杂度 × 技能市场价值 × 用户评分系数
        rating_factor = (self.user_rating or 3) / 5.0
        return self.complexity * skill_value * rating_factor


class ValueMetrics:
    """价值指标"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.records_file = os.path.join(data_dir, "execution_records.json")
        self.records: List[ExecutionRecord] = []
        self._load_records()
    
    def _load_records(self):
        """加载执行记录"""
        if os.path.exists(self.records_file):
            with open(self.records_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.records = [
                    ExecutionRecord(
                        task_id=r["task_id"],
                        user_id=r["user_id"],
                        skill_name=r["skill_name"],
                        description=r["description"],
                        status=TaskStatus(r["status"]),
                        duration=r["duration"],
                        estimated_manual_time=r["estimated_manual_time"],
                        error_count=r.get("error_count", 0),
                        user_rating=r.get("user_rating"),
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                        complexity=r.get("complexity", 1.0)
                    )
                    for r in data
                ]
    
    def _save_records(self):
        """保存执行记录"""
        with open(self.records_file, 'w', encoding='utf-8') as f:
            data = [
                {
                    "task_id": r.task_id,
                    "user_id": r.user_id,
                    "skill_name": r.skill_name,
                    "description": r.description,
                    "status": r.status.value,
                    "duration": r.duration,
                    "estimated_manual_time": r.estimated_manual_time,
                    "error_count": r.error_count,
                    "user_rating": r.user_rating,
                    "timestamp": r.timestamp.isoformat(),
                    "complexity": r.complexity
                }
                for r in self.records
            ]
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_execution(self, record: ExecutionRecord):
        """添加执行记录"""
        self.records.append(record)
        self._save_records()
    
    def calculate_user_value(
        self,
        user_id: str,
        period: Optional[timedelta] = None,
        hourly_rate: float = 100.0
    ) -> Dict[str, float]:
        """
        计算用户价值
        
        Args:
            user_id: 用户ID
            period: 统计周期（None 表示全部）
            hourly_rate: 用户时薪
            
        Returns:
            价值明细
        """
        # 筛选记录
        now = datetime.now()
        if period:
            start_time = now - period
            records = [
                r for r in self.records
                if r.user_id == user_id and r.timestamp >= start_time
            ]
        else:
            records = [r for r in self.records if r.user_id == user_id]
        
        if not records:
            return {
                "total_value": 0.0,
                "time_saved": 0.0,
                "accuracy_gain": 0.0,
                "efficiency_gain": 0.0,
                "learning_value": 0.0,
                "total_time_saved_hours": 0.0,
                "total_tasks": 0,
                "success_rate": 0.0
            }
        
        # 计算各项价值
        total_time_saved = sum(r.calculate_time_saved(hourly_rate) for r in records)
        total_accuracy_gain = sum(r.calculate_accuracy_gain() for r in records)
        total_efficiency_gain = sum(r.calculate_efficiency_gain() for r in records)
        total_learning_value = sum(r.calculate_learning_value() for r in records)
        
        # 总价值
        total_value = (
            total_time_saved +
            total_accuracy_gain +
            total_efficiency_gain +
            total_learning_value
        )
        
        # 统计信息
        total_time_saved_hours = sum(
            max(0, r.estimated_manual_time - r.duration) / 3600
            for r in records
        )
        total_tasks = len(records)
        success_tasks = sum(1 for r in records if r.status == TaskStatus.SUCCESS)
        
        return {
            "total_value": total_value,
            "time_saved": total_time_saved,
            "accuracy_gain": total_accuracy_gain,
            "efficiency_gain": total_efficiency_gain,
            "learning_value": total_learning_value,
            "total_time_saved_hours": total_time_saved_hours,
            "total_tasks": total_tasks,
            "success_rate": success_tasks / total_tasks if total_tasks > 0 else 0.0,
            "avg_rating": sum(r.user_rating or 0 for r in records) / 
                         max(1, sum(1 for r in records if r.user_rating))
        }
    
    def calculate_system_value(
        self,
        period: Optional[timedelta] = None
    ) -> Dict[str, float]:
        """
        计算系统价值
        
        Args:
            period: 统计周期
            
        Returns:
            系统价值明细
        """
        # 筛选记录
        now = datetime.now()
        if period:
            start_time = now - period
            records = [r for r in self.records if r.timestamp >= start_time]
        else:
            records = self.records
        
        if not records:
            return {
                "total_users": 0,
                "total_executions": 0,
                "skill_usage": {},
                "user_satisfaction": 0.0,
                "total_value_created": 0.0
            }
        
        # 统计用户数
        unique_users = len(set(r.user_id for r in records))
        
        # 统计技能使用
        skill_usage = {}
        for r in records:
            if r.skill_name not in skill_usage:
                skill_usage[r.skill_name] = 0
            skill_usage[r.skill_name] += 1
        
        # 计算用户满意度
        rated_records = [r for r in records if r.user_rating is not None]
        user_satisfaction = (
            sum(r.user_rating for r in rated_records) / len(rated_records)
            if rated_records else 0.0
        )
        
        # 计算总价值创造（假设平均时薪 100 元）
        total_value_created = sum(
            r.calculate_time_saved(100.0) +
            r.calculate_accuracy_gain() +
            r.calculate_efficiency_gain() +
            r.calculate_learning_value()
            for r in records
        )
        
        return {
            "total_users": unique_users,
            "total_executions": len(records),
            "skill_usage": dict(sorted(
                skill_usage.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),  # 前 10 个最常用技能
            "user_satisfaction": user_satisfaction,
            "total_value_created": total_value_created,
            "success_rate": sum(1 for r in records if r.status == TaskStatus.SUCCESS) / len(records)
        }
    
    def generate_monthly_report(
        self,
        user_id: Optional[str] = None,
        hourly_rate: float = 100.0
    ) -> str:
        """
        生成月度报告
        
        Args:
            user_id: 用户ID（None 表示系统级报告）
            hourly_rate: 时薪
            
        Returns:
            Markdown 格式的报告
        """
        month = timedelta(days=30)
        
        if user_id:
            value = self.calculate_user_value(user_id, month, hourly_rate)
            title = f"NovaHands 月度报告 - 用户 {user_id}"
        else:
            value = self.calculate_system_value(month)
            title = "NovaHands 月度报告 - 系统总览"
        
        report = f"""# {title}

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 价值总览

"""
        
        if user_id:
            report += f"""
### 用户价值指标

| 指标 | 数值 |
|------|------|
| **总价值创造** | ¥{value['total_value']:.2f} |
| 时间节省价值 | ¥{value['time_saved']:.2f} |
| 准确性提升价值 | ¥{value['accuracy_gain']:.2f} |
| 效率提升价值 | ¥{value['efficiency_gain']:.2f} |
| 学习价值 | ¥{value['learning_value']:.2f} |
| **总节省时间** | {value['total_time_saved_hours']:.1f} 小时 |
| **执行任务数** | {value['total_tasks']} |
| **成功率** | {value['success_rate'] * 100:.1f}% |
| **平均评分** | {value['avg_rating']:.1f} / 5.0 |
"""
        else:
            report += f"""
### 系统价值指标

| 指标 | 数值 |
|------|------|
| **活跃用户数** | {value['total_users']} |
| **总执行次数** | {value['total_executions']} |
| **用户满意度** | {value['user_satisfaction']:.1f} / 5.0 |
| **成功率** | {value['success_rate'] * 100:.1f}% |
| **总价值创造** | ¥{value['total_value_created']:.2f} |

### 最常用技能 TOP 10

| 排名 | 技能名称 | 使用次数 |
|------|----------|----------|
"""
            for i, (skill_name, count) in enumerate(value['skill_usage'].items(), 1):
                report += f"| {i} | {skill_name} | {count} |\n"
        
        report += """
---

## 总结

本月 NovaHands 为用户创造了显著价值，通过自动化任务节省了大量时间，提高了工作效率。建议继续探索更多技能，进一步提升生产力。

*本报告基于实际执行记录生成，数据仅供参考。*
"""
        
        return report
    
    def get_value_trends(
        self,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> List[Dict]:
        """
        获取价值趋势
        
        Args:
            user_id: 用户ID（None 表示系统级）
            days: 天数
            
        Returns:
            每日价值数据
        """
        trends = []
        now = datetime.now()
        
        for i in range(days):
            date = now - timedelta(days=days - i - 1)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            # 筛选当天记录
            records = [
                r for r in self.records
                if start_of_day <= r.timestamp < end_of_day
            ]
            
            if user_id:
                records = [r for r in records if r.user_id == user_id]
            
            if records:
                daily_value = sum(
                    r.calculate_time_saved() +
                    r.calculate_accuracy_gain() +
                    r.calculate_efficiency_gain() +
                    r.calculate_learning_value()
                    for r in records
                )
                
                trends.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "value": daily_value,
                    "tasks": len(records),
                    "success_rate": sum(1 for r in records if r.status == TaskStatus.SUCCESS) / len(records)
                })
            else:
                trends.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "value": 0.0,
                    "tasks": 0,
                    "success_rate": 0.0
                })
        
        return trends
