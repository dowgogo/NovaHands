import argparse
import threading
import time
from core.controller import Controller
from core.safe_guard import SafeGuard
from core.nl_executor import NLExecutor
from skills.skill_manager import SkillManager
from models.model_manager import ModelManager
from learning.action_recorder import ActionRecorder
from learning.skill_generator import SkillGenerator
from rl.environment import NovaHandsEnv
from rl.policy import PolicyModel
from rl.collector import DataCollector
from rl.trainer import RLFineTuner
from rl.evolution import SkillEvolution
from utils.config_loader import ConfigLoader
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description='NovaHands - Intelligent Desktop Assistant')
    parser.add_argument('--gui', action='store_true', help='Launch GUI')
    parser.add_argument('--learn', action='store_true', help='Record actions and generate skills')
    parser.add_argument('--rl', action='store_true', help='Start RL data collection')
    args = parser.parse_args()

    config = ConfigLoader()
    controller = Controller()
    safe_guard = SafeGuard()
    skill_manager = SkillManager()
    model_manager = ModelManager()

    if args.learn:
        recorder = ActionRecorder(safe_guard)
        recorder.start_recording()
        input("Learning mode enabled. Press Enter to stop...")
        recorder.stop_recording()
        generator = SkillGenerator(recorder)
        new_skills = generator.generate_skills(output_dir="skills/user")
        logger.info(f"Generated {len(new_skills)} new skills")
        for skill in new_skills:
            print(f"  - {skill.name}: {skill.description}")
        return

    if args.rl:
        # RL mode: collect data
        # 安全说明：默认使用 MockController，不会操控真实鼠标键盘
        # 若需接入真实环境，请传入 real_controller=controller 并确保在沙箱中运行
        env = NovaHandsEnv(skill_manager=skill_manager)
        policy = PolicyModel(skill_list=skill_manager.list_skills())
        collector = DataCollector(env, policy)
        logger.info("Starting RL data collection. Press Ctrl+C to stop.")
        try:
            while True:
                collector.collect_episode()
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    if args.gui:
        from gui.main_window import MainWindow
        app = MainWindow(controller, skill_manager, model_manager)
        app.run()
    else:
        executor = NLExecutor(skill_manager, model_manager)
        print("NovaHands CLI mode. Enter natural language commands, or 'quit' to exit.")
        while True:
            cmd = input("> ")
            if cmd == 'quit':
                break
            executor.execute(cmd, controller, current_app=safe_guard.get_current_app())


if __name__ == '__main__':
    main()
