import argparse
import threading
import time
from core.controller import Controller
from core.safe_guard import SafeGuard
from core.nl_executor import NLExecutor
from skills.skill_manager import SkillManager
from models.model_manager import ModelManager
from utils.config_loader import ConfigLoader
from utils.logger import setup_logger, logger as _default_logger
# 注意：RL / learning 相关模块在各自的 args 分支内懒导入，
# 避免未安装 torch/gymnasium 等重量级依赖时启动失败。


def main():
    parser = argparse.ArgumentParser(description='NovaHands - Intelligent Desktop Assistant')
    parser.add_argument('--gui', action='store_true', help='Launch GUI')
    parser.add_argument('--learn', action='store_true', help='Record actions and generate skills')
    parser.add_argument('--rl', action='store_true', help='Start RL data collection')
    args = parser.parse_args()

    config = ConfigLoader()

    # ── config 配置项真正生效 ─────────────────────────────────
    # logging.level：控制台日志级别（DEBUG/INFO/WARNING/ERROR）
    log_level = config.get('logging.level', 'INFO')
    log_file  = config.get('logging.file', None)
    logger = setup_logger(log_level=log_level, log_file=log_file)

    controller = Controller()
    safe_guard = SafeGuard()
    skill_manager = SkillManager()
    model_manager = ModelManager()

    if args.learn:
        from learning.action_recorder import ActionRecorder
        from learning.skill_generator import SkillGenerator
        recorder = ActionRecorder(safe_guard)
        recorder.start_recording()
        input("Learning mode enabled. Press Enter to stop...")
        recorder.stop_recording()
        generator = SkillGenerator(recorder)
        # 默认持久化到 skills/user/ 目录
        user_skill_dir = config.get('skill_dirs.user', 'skills/user')
        new_skills = generator.generate_skills(output_dir=user_skill_dir)
        logger.info(f"Generated {len(new_skills)} new skills")
        for skill in new_skills:
            print(f"  - {skill.name}: {skill.description}")
        return

    if args.rl:
        from rl.environment import NovaHandsEnv
        from rl.policy import PolicyModel
        from rl.collector import DataCollector
        # RL mode: collect data
        # 安全说明：默认使用 MockController，不会操控真实鼠标键盘
        # 若需接入真实环境，请传入 real_controller=controller 并确保在沙箱中运行
        print("RL 数据采集模式启动中...")
        print("注意：RL 策略依赖本地 LLM（PolicyModel），首次运行将自动下载模型（约 500MB）。")
        print("若不需要 LLM 策略，可在 rl/policy.py 中修改为随机策略。")
        env = NovaHandsEnv(skill_manager=skill_manager)
        policy = PolicyModel(skill_list=skill_manager.list_skills())
        # rl.exploration_prob / rl.train_frequency 从 config 读取
        exploration_prob  = config.get('rl.exploration_prob', 0.1)
        train_frequency   = config.get('rl.train_frequency', 100)
        collector = DataCollector(
            env, policy,
            epsilon=exploration_prob,
            train_frequency=train_frequency
        )
        logger.info("Starting RL data collection. Press Ctrl+C to stop.")
        try:
            while True:
                collector.collect_episode()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nRL data collection stopped.")
        return

    if args.gui:
        from gui.main_window import MainWindow
        app = MainWindow(controller, skill_manager, model_manager)
        app.run()
    else:
        executor = NLExecutor(skill_manager, model_manager)
        print("NovaHands CLI mode. Enter natural language commands, or 'quit' to exit.")
        print("(按 Ctrl+C 或输入 'quit' 退出)")
        # 修复：捕获 KeyboardInterrupt，优雅退出而非打印堆栈跟踪
        try:
            while True:
                try:
                    cmd = input("> ")
                except EOFError:
                    break
                if cmd.strip().lower() in ('quit', 'exit', 'q'):
                    break
                if not cmd.strip():
                    continue
                executor.execute(cmd, controller, current_app=safe_guard.get_current_app())
        except KeyboardInterrupt:
            pass
        print("\nGoodbye!")


if __name__ == '__main__':
    main()

