"""
价值系统测试

测试技能市场和价值量化功能。
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

# 设置 UTF-8 编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.skill_marketplace import (
    SkillMarketplace,
    SkillTier,
    SkillStatus,
    RevenueShareCalculator
)
from core.value_metrics import (
    ValueMetrics,
    ExecutionRecord,
    TaskStatus,
    ValueType
)


def test_skill_marketplace():
    """测试技能市场"""
    print("\n=== 测试技能市场 ===\n")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        marketplace = SkillMarketplace(temp_dir)
        
        # 测试发布技能
        print("[测试 1] 发布技能...")
        skill = marketplace.publish_skill(
            skill_id="skill_001",
            name="Excel 自动化报告",
            author="Alice",
            description="自动生成 Excel 月度报告",
            version="1.0.0",
            category="办公自动化",
            price=49.0,
            tier=SkillTier.BASIC
        )
        print(f"  ✓ 技能已发布: {skill.name}")
        print(f"    状态: {skill.status.value}")
        print(f"    价格: ¥{skill.price}")
        
        # 测试认证技能
        print("\n[测试 2] 认证技能...")
        marketplace.certify_skill("skill_001", certified=True)
        skill = marketplace.skills["skill_001"]
        print(f"  ✓ 技能已认证: {skill.name}")
        print(f"    新状态: {skill.status.value}")
        print(f"    新等级: {skill.tier.value}")
        
        # 测试评价技能
        print("\n[测试 3] 评价技能...")
        rating1 = marketplace.rate_skill("skill_001", 5)
        rating2 = marketplace.rate_skill("skill_001", 4)
        rating3 = marketplace.rate_skill("skill_001", 5)
        print(f"  ✓ 用户评价完成")
        print(f"    评分1: 5, 评分2: 4, 评分3: 5")
        print(f"    平均评分: {rating3:.2f}")
        
        # 测试记录下载
        print("\n[测试 4] 记录下载...")
        for i in range(100):
            marketplace.record_download("skill_001")
        skill = marketplace.skills["skill_001"]
        print(f"  ✓ 下载记录完成")
        print(f"    下载次数: {skill.downloads}")
        
        # 测试搜索技能
        print("\n[测试 5] 搜索技能...")
        # 发布更多技能
        marketplace.publish_skill(
            "skill_002", "邮件批量处理", "Bob", "批量发送邮件",
            "1.0.0", "办公自动化", 29.0, SkillTier.BASIC
        )
        marketplace.publish_skill(
            "skill_003", "截图标注工具", "Charlie", "截图并添加标注",
            "2.0.0", "图像处理", 99.0, SkillTier.PREMIUM
        )
        
        results = marketplace.search_skills(
            query="自动化",
            sort_by="downloads"
        )
        print(f"  ✓ 搜索完成")
        print(f"    找到 {len(results)} 个技能")
        for i, skill in enumerate(results, 1):
            print(f"    {i}. {skill['name']} - ¥{skill['price']} ({skill['downloads']} 下载)")
        
        # 测试排行榜
        print("\n[测试 6] 技能排行榜...")
        leaderboard = marketplace.get_leaderboard(limit=5)
        print(f"  ✓ 排行榜生成")
        for i, skill in enumerate(leaderboard, 1):
            print(f"    {i}. {skill['name']} - {skill['downloads']} 下载")
        
        # 测试贡献者统计
        print("\n[测试 7] 贡献者统计...")
        stats = marketplace.get_contributor_stats("Alice")
        print(f"  ✓ 贡献者统计完成")
        print(f"    作者: Alice")
        print(f"    技能数: {stats['total_skills']}")
        print(f"    总下载: {stats['total_downloads']}")
        print(f"    平均评分: {stats['average_rating']:.2f}")
        print(f"    总收益: ¥{stats['total_revenue']:.2f}")
        
        # 测试收益分成
        print("\n[测试 8] 收益分成计算...")
        share1 = RevenueShareCalculator.calculate(49.0, 10, has_referrer=True)
        share2 = RevenueShareCalculator.calculate(99.0, 5, has_referrer=False)
        print(f"  ✓ 收益分成计算完成")
        print(f"    销售 10 个 ¥49 技能（有推荐人）:")
        print(f"      总收入: ¥{share1['total_revenue']:.2f}")
        print(f"      开发者: ¥{share1['developer_share']:.2f} (70%)")
        print(f"      推荐人: ¥{share1['referrer_share']:.2f} (5%)")
        print(f"      平台: ¥{share1['platform_share']:.2f} (25%)")
        print(f"    销售 5 个 ¥99 技能（无推荐人）:")
        print(f"      总收入: ¥{share2['total_revenue']:.2f}")
        print(f"      开发者: ¥{share2['developer_share']:.2f} (70%)")
        print(f"      平台: ¥{share2['platform_share']:.2f} (30%)")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
    
    print("\n✅ 技能市场测试完成\n")


def test_value_metrics():
    """测试价值量化"""
    print("\n=== 测试价值量化 ===\n")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        metrics = ValueMetrics(temp_dir)
        
        # 模拟执行记录
        print("[测试 1] 添加执行记录...")
        
        records = [
            # 用户 Alice 的记录
            ExecutionRecord(
                task_id="task_001",
                user_id="Alice",
                skill_name="open_app",
                description="打开记事本",
                status=TaskStatus.SUCCESS,
                duration=2.5,
                estimated_manual_time=10.0,
                user_rating=5,
                complexity=1.0
            ),
            ExecutionRecord(
                task_id="task_002",
                user_id="Alice",
                skill_name="open_app",
                description="打开 Chrome",
                status=TaskStatus.SUCCESS,
                duration=3.0,
                estimated_manual_time=15.0,
                user_rating=4,
                complexity=1.0
            ),
            ExecutionRecord(
                task_id="task_003",
                user_id="Alice",
                skill_name="excel_automation",
                description="生成月度报告",
                status=TaskStatus.SUCCESS,
                duration=120.0,
                estimated_manual_time=1200.0,
                user_rating=5,
                complexity=3.0
            ),
            # 用户 Bob 的记录
            ExecutionRecord(
                task_id="task_004",
                user_id="Bob",
                skill_name="email_automation",
                description="批量发送邮件",
                status=TaskStatus.PARTIAL,
                duration=60.0,
                estimated_manual_time=300.0,
                error_count=1,
                user_rating=3,
                complexity=2.0
            ),
            # 模拟历史记录（30天前）
            ExecutionRecord(
                task_id="task_005",
                user_id="Alice",
                skill_name="file_manager",
                description="整理桌面文件",
                status=TaskStatus.SUCCESS,
                duration=180.0,
                estimated_manual_time=1800.0,
                user_rating=5,
                complexity=2.0,
                timestamp=datetime.now() - timedelta(days=20)
            ),
        ]
        
        for record in records:
            metrics.add_execution(record)
        
        print(f"  ✓ 已添加 {len(records)} 条执行记录")
        
        # 测试用户价值计算
        print("\n[测试 2] 计算用户价值（Alice，本月）...")
        alice_value = metrics.calculate_user_value("Alice", timedelta(days=30), hourly_rate=100.0)
        print(f"  ✓ 用户价值计算完成")
        print(f"    总价值创造: ¥{alice_value['total_value']:.2f}")
        print(f"      - 时间节省: ¥{alice_value['time_saved']:.2f}")
        print(f"      - 准确性提升: ¥{alice_value['accuracy_gain']:.2f}")
        print(f"      - 效率提升: ¥{alice_value['efficiency_gain']:.2f}")
        print(f"      - 学习价值: ¥{alice_value['learning_value']:.2f}")
        print(f"    总节省时间: {alice_value['total_time_saved_hours']:.1f} 小时")
        print(f"    执行任务数: {alice_value['total_tasks']}")
        print(f"    成功率: {alice_value['success_rate'] * 100:.1f}%")
        print(f"    平均评分: {alice_value['avg_rating']:.1f} / 5.0")
        
        # 测试系统价值计算
        print("\n[测试 3] 计算系统价值（本月）...")
        system_value = metrics.calculate_system_value(timedelta(days=30))
        print(f"  ✓ 系统价值计算完成")
        print(f"    活跃用户数: {system_value['total_users']}")
        print(f"    总执行次数: {system_value['total_executions']}")
        print(f"    用户满意度: {system_value['user_satisfaction']:.1f} / 5.0")
        print(f"    成功率: {system_value['success_rate'] * 100:.1f}%")
        print(f"    总价值创造: ¥{system_value['total_value_created']:.2f}")
        
        # 测试月度报告生成
        print("\n[测试 4] 生成月度报告...")
        report = metrics.generate_monthly_report(user_id="Alice", hourly_rate=100.0)
        print("  ✓ 月度报告生成完成")
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)
        
        # 测试价值趋势
        print("\n[测试 5] 获取价值趋势...")
        trends = metrics.get_value_trends(user_id="Alice", days=10)
        print("  ✓ 价值趋势获取完成")
        print("\n最近 10 天价值趋势:")
        for trend in trends[-5:]:  # 只显示最后 5 天
            if trend['tasks'] > 0:
                print(f"  {trend['date']}: ¥{trend['value']:.2f} ({trend['tasks']} 任务, {trend['success_rate']*100:.0f}% 成功)")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
    
    print("\n✅ 价值量化测试完成\n")


def test_integration():
    """测试集成场景"""
    print("\n=== 测试集成场景 ===\n")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        marketplace = SkillMarketplace(temp_dir)
        metrics = ValueMetrics(temp_dir)
        
        # 场景：用户 Bob 使用技能并贡献技能
        
        # 步骤 1: 发布技能
        print("[步骤 1] Bob 发布技能...")
        marketplace.publish_skill(
            "skill_csv_export",
            "CSV 数据导出",
            "Bob",
            "将数据库数据导出为 CSV 格式",
            "1.0.0",
            "数据处理",
            price=39.0,
            tier=SkillTier.BASIC
        )
        marketplace.certify_skill("skill_csv_export", certified=True)
        print("  ✓ 技能已发布并认证")
        
        # 步骤 2: 用户使用技能
        print("\n[步骤 2] 用户使用技能...")
        for i in range(50):
            marketplace.record_download("skill_csv_export")
        
        # 模拟执行
        for i in range(30):
            metrics.add_execution(ExecutionRecord(
                task_id=f"task_{i}",
                user_id=f"user_{i % 10}",
                skill_name="skill_csv_export",
                description="导出订单数据",
                status=TaskStatus.SUCCESS if i % 10 != 5 else TaskStatus.PARTIAL,
                duration=30.0,
                estimated_manual_time=300.0,
                user_rating=5 if i % 10 != 5 else 4,
                complexity=2.0
            ))
        
        print("  ✓ 技能使用完成（50 下载，30 执行）")
        
        # 步骤 3: 用户评价
        print("\n[步骤 3] 用户评价...")
        for i in range(20):
            marketplace.rate_skill("skill_csv_export", 5)
        for i in range(10):
            marketplace.rate_skill("skill_csv_export", 4)
        
        print("  ✓ 评价完成（30 次评价）")
        
        # 步骤 4: 计算收益
        print("\n[步骤 4] 计算 Bob 的收益...")
        stats = marketplace.get_contributor_stats("Bob")
        revenue_share = RevenueShareCalculator.calculate(39.0, 50)
        
        print(f"  Bob 的贡献统计:")
        print(f"    技能数: {stats['total_skills']}")
        print(f"    总下载: {stats['total_downloads']}")
        print(f"    平均评分: {stats['average_rating']:.2f}")
        print(f"    总收益分成:")
        print(f"      开发者收入: ¥{revenue_share['developer_share']:.2f}")
        print(f"      平台收入: ¥{revenue_share['platform_share']:.2f}")
        
        # 步骤 5: 系统价值
        print("\n[步骤 5] 计算系统价值...")
        system_value = metrics.calculate_system_value()
        print(f"  ✓ 系统价值:")
        print(f"    总用户数: {system_value['total_users']}")
        print(f"    总执行次数: {system_value['total_executions']}")
        print(f"    用户满意度: {system_value['user_satisfaction']:.1f} / 5.0")
        print(f"    总价值创造: ¥{system_value['total_value_created']:.2f}")
        
        # 步骤 6: 排行榜
        print("\n[步骤 6] 更新排行榜...")
        leaderboard = marketplace.get_leaderboard(limit=10)
        print("  ✓ 技能排行榜 TOP 5:")
        for i, skill in enumerate(leaderboard[:5], 1):
            print(f"    {i}. {skill['name']} - {skill['downloads']} 下载, ¥{skill['price']} (评分: {skill['rating']:.1f})")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
    
    print("\n✅ 集成测试完成\n")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("NovaHands 价值系统测试")
    print("=" * 60)
    
    try:
        test_skill_marketplace()
        test_value_metrics()
        test_integration()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60 + "\n")
        
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
