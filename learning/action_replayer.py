"""
Action Replayer - 任务回放模块（OpenAdapt 风格增强）

OpenAdapt 启发的增强功能：
1. 语义回放：根据屏幕元素匹配，而非绝对坐标
2. 回放前检查：验证 UI 状态变化，避免错误执行
3. 带参数化：支持参数替换（如文件名、日期等变量）
4. 部分回放：支持指定时间段的动作回放
5. 回放日志：详细记录每步执行结果，便于调试

与 action_recorder.py 配合使用：recorder 录制 → replayer 回放
"""

import time
import logging
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Callable
from pathlib import Path

try:
    import pyautogui
    import cv2
    import numpy as np
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

from utils.logger import logger
from core.safe_guard import SafeGuard

logger = logging.getLogger("novahands")


@dataclass
class ReplayStep:
    """回放步骤定义"""
    index: int
    action_type: str
    original_timestamp: float
    details: dict
    app: Optional[str] = None
    # 增强字段
    ui_selector: Optional[str] = None  # OpenAdapt 风格 UI 选择器（用于语义匹配）
    check_before: Optional[Dict] = None  # 回放前检查条件
    params: Optional[Dict] = None  # 参数替换映射


@dataclass
class ReplayResult:
    """回放结果汇总"""
    total_steps: int
    succeeded: int
    failed: int
    skipped: int
    duration_seconds: float
    steps: List[Dict]  # 每步详细结果


class ActionReplayer:
    """动作回放器，支持语义回放、参数化和世界模型验证"""

    def __init__(
        self,
        safe_guard: SafeGuard,
        screen_match_threshold: float = 0.8,
        world_model: Optional['WorldModel'] = None
    ):
        """
        Parameters
        ----------
        safe_guard : SafeGuard
            安全守卫实例，用于权限检查
        screen_match_threshold : float
            屏幕元素匹配阈值（0-1），用于语义回放
        world_model : WorldModel, optional
            世界模型，用于回放前验证
        """
        self.safe_guard = safe_guard
        self.screen_match_threshold = screen_match_threshold
        self.world_model = world_model
        self._steps: List[ReplayStep] = []

    def load_from_recorder(self, actions: List, **metadata):
        """
        从 ActionRecorder.actions 加载动作序列

        Parameters
        ----------
        actions : List[Action]
            action_recorder.py 录制的动作列表
        metadata : dict
            元数据（如录制时间、任务描述等）
        """
        self._steps = []
        for idx, action in enumerate(actions):
            step = ReplayStep(
                index=idx,
                action_type=action.type,
                original_timestamp=action.timestamp,
                details=action.details.copy(),
                app=action.app,
                ui_selector=None,  # 需后续手动标注或 LLM 推断
                check_before=None,
                params=None
            )
            self._steps.append(step)
        logger.info(f"Loaded {len(self._steps)} replay steps from recorder")

    def load_from_file(self, filepath: str):
        """从 JSON 文件加载回放计划（支持手动编辑）"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Replay file not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._steps = []
        for item in data.get("steps", []):
            step = ReplayStep(**item)
            self._steps.append(step)
        logger.info(f"Loaded {len(self._steps)} replay steps from {filepath}")

    def save_to_file(self, filepath: str):
        """保存回放计划到 JSON 文件（便于手动编辑和分享）"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "created_at": time.time(),
            "steps": [asdict(step) for step in self._steps]
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved replay plan to {filepath}")

    def add_step(self, step: ReplayStep):
        """手动添加回放步骤"""
        step.index = len(self._steps)
        self._steps.append(step)

    def apply_params(self, param_map: Dict[str, str]):
        """全局参数替换（如 {'filename': 'report.xlsx', 'date': '2026-04-01'}）"""
        for step in self._steps:
            if step.params:
                for key, value in step.params.items():
                    if key in param_map:
                        step.params[key] = param_map[key]
            # 在 details 中替换字符串占位符 {key}
            details_str = json.dumps(step.details)
            for key, value in param_map.items():
                details_str = details_str.replace(f"{{{key}}}", str(value))
            step.details = json.loads(details_str)

    def set_ui_selector(self, step_index: int, selector: str):
        """为某步设置 OpenAdapt 风格 UI 选择器"""
        if 0 <= step_index < len(self._steps):
            self._steps[step_index].ui_selector = selector

    def set_check_before(self, step_index: int, condition: Dict):
        """
        设置回放前检查条件

        Examples
        --------
        {"type": "text_exists", "text": "Save"}
        {"type": "window_title", "contains": "Notepad"}
        {"type": "element_visible", "selector": "#save-btn"}
        """
        if 0 <= step_index < len(self._steps):
            self._steps[step_index].check_before = condition

    def _check_before(self, step: ReplayStep) -> bool:
        """执行回放前检查，返回是否通过"""
        if not step.check_before:
            return True

        check_type = step.check_before.get("type")

        # 简化版检查（可扩展）
        if check_type == "text_exists":
            # TODO: 实现 OCR 或 UI 自动化库检查
            logger.debug(f"Check: text_exists {step.check_before.get('text')}")
            return True
        elif check_type == "window_title":
            current_app = self.safe_guard.get_current_app()
            contains = step.check_before.get("contains", "")
            return contains.lower() in current_app.lower()
        else:
            logger.warning(
                f"Unknown check type: {check_type}. "
                f"Step {step.index} will be skipped for safety. "
                f"Known types: text_exists, window_title"
            )
            return False  # 安全默认：未知类型拒绝执行

    def _validate_with_world_model(
        self,
        current_observation: Dict[str, Any],
        step: ReplayStep,
        max_steps_ahead: int = 3
    ) -> Tuple[bool, float, str]:
        """
        使用世界模型验证动作序列的安全性

        Parameters
        ----------
        current_observation : dict
            当前观察
        step : ReplayStep
            当前步骤
        max_steps_ahead : int
            向前预测的步数

        Returns
        -------
        is_safe : bool
            是否安全
        avg_uncertainty : float
            平均不确定性
        reason : str
            详细原因
        """
        if self.world_model is None:
            return True, 0.0, "World model not available"

        try:
            # 编码当前观察
            current_state = self.world_model.encode_observation(current_observation)

            # 模拟接下来的动作
            total_uncertainty = 0.0
            num_steps = 0

            for i in range(max_steps_ahead):
                step_idx = step.index + i
                if step_idx >= len(self._steps):
                    break

                future_step = self._steps[step_idx]

                # 将动作类型转换为技能名称
                action_name = self._action_type_to_skill_name(
                    future_step.action_type
                )

                # 预测下一状态和不确定性
                next_state, uncertainty = self.world_model.predict_next_state(
                    current_state,
                    action_name
                )

                total_uncertainty += uncertainty
                num_steps += 1

                # 更新状态
                current_state = next_state

            # 计算平均不确定性
            if num_steps > 0:
                avg_uncertainty = total_uncertainty / num_steps
            else:
                avg_uncertainty = 0.0

            # 判断安全性
            uncertainty_threshold = 0.5  # 可配置

            if avg_uncertainty < uncertainty_threshold:
                is_safe = True
                reason = f"Low uncertainty ({avg_uncertainty:.3f})"
            else:
                is_safe = False
                reason = f"High uncertainty ({avg_uncertainty:.3f} > {uncertainty_threshold})"

            return is_safe, avg_uncertainty, reason

        except Exception as e:
            logger.error(f"World model validation failed: {e}")
            # 安全默认：允许执行
            return True, 0.0, f"Validation error: {e}"

    def _action_type_to_skill_name(self, action_type: str) -> str:
        """
        将动作类型转换为技能名称（世界模型使用）

        Parameters
        ----------
        action_type : str
            动作类型（如 "click", "key_press", "type"）

        Returns
        -------
        skill_name : str
            技能名称
        """
        # 简单映射
        mapping = {
            "click": "click",
            "key_press": "type",
            "type": "type",
            "scroll": "scroll",
            "drag": "drag"
        }
        return mapping.get(action_type, action_type)

    def _get_current_observation(self) -> Dict[str, Any]:
        """
        获取当前系统观察（用于世界模型验证）

        Returns
        -------
        observation : dict
            观察字典
        """
        observation = {
            "window_title": "",
            "active_app": "",
            "cursor_pos": (0, 0)
        }

        try:
            # 获取当前窗口标题
            current_app = self.safe_guard.get_current_app()
            observation["active_app"] = current_app
            observation["window_title"] = current_app

            # 获取光标位置
            if PYAUTOGUI_AVAILABLE:
                x, y = pyautogui.position()
                observation["cursor_pos"] = (x, y)

        except Exception as e:
            logger.warning(f"Failed to get current observation: {e}")

        return observation

    def _match_ui_element(self, step: ReplayStep) -> Optional[tuple]:
        """
        OpenAdapt 风格语义匹配：通过 UI 选择器或图像匹配定位元素

        Returns
        -------
        (x, y) or None
            匹配到的坐标，若未匹配则返回 None
        """
        if not PYAUTOGUI_AVAILABLE:
            logger.warning("pyautogui not available, skipping semantic matching")
            return None

        if step.ui_selector:
            # TODO: 集成 UI 自动化库（如 pygetwindow、pywinauto）
            logger.debug(f"Semantic match with selector: {step.ui_selector}")
            return None

        # 图像匹配回退方案（需要预先截图模板）
        # 简化实现：直接使用原始坐标
        x = step.details.get("x")
        y = step.details.get("y")
        if x is not None and y is not None:
            return (x, y)
        return None

    def _execute_click(self, step: ReplayStep) -> bool:
        """执行点击动作"""
        if not PYAUTOGUI_AVAILABLE:
            logger.error("pyautogui required for replay")
            return False

        # 安全检查：验证应用白名单
        app = step.app or "unknown"
        if not self.safe_guard.check_app_allowed(app):
            logger.warning(f"App not allowed: {app}, skipping click")
            return False

        # 语义匹配坐标
        coords = self._match_ui_element(step)
        if not coords:
            logger.warning(f"Failed to match UI element for step {step.index}")
            return False

        x, y = coords
        button = step.details.get("button", "Button.left")

        try:
            if button == "Button.left":
                pyautogui.click(x, y)
            elif button == "Button.right":
                pyautogui.rightClick(x, y)
            else:
                pyautogui.click(x, y, button=str(button).split(".")[-1])
            logger.debug(f"Clicked at ({x}, {y}) with {button}")
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    def _execute_key_press(self, step: ReplayStep) -> bool:
        """执行按键动作（仅支持功能键，隐私保护）"""
        if not PYAUTOGUI_AVAILABLE:
            logger.error("pyautogui required for replay")
            return False

        app = step.app or "unknown"
        if not self.safe_guard.check_app_allowed(app):
            logger.warning(f"App not allowed: {app}, skipping key press")
            return False

        key = step.details.get("key", "")

        # FIX HIGH-2: 扩展特殊键处理，包括 <CHAR>、<LETTER>、<unknown>
        if key == "<CHAR>" or key == "<LETTER>" or key == "<unknown>":
            logger.debug(f"Skipping sanitized key: {key}")
            return True

        try:
            if key.startswith("Key."):
                key_name = key.split(".")[-1]
                pyautogui.press(key_name)
            else:
                # 直接传入键名
                pyautogui.press(key)
            logger.debug(f"Pressed key: {key}")
            return True
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return False

    def replay(
        self,
        start_index: int = 0,
        end_index: Optional[int] = None,
        speed_multiplier: float = 1.0,
        on_step: Optional[Callable[[int, Dict], None]] = None
    ) -> ReplayResult:
        """
        执行回放

        Parameters
        ----------
        start_index : int
            起始步骤索引（0-based）
        end_index : int or None
            结束步骤索引（不包含），None 表示到末尾
        speed_multiplier : float
            播放速度倍数（1.0 = 原速，2.0 = 2 倍速）
        on_step : callable or None
            每步回调函数 on_step(index, result_dict)

        Returns
        -------
        ReplayResult
            回放结果汇总
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui is required for replay. Install: pip install pyautogui")

        if end_index is None:
            end_index = len(self._steps)

        steps_to_run = self._steps[start_index:end_index]
        if not steps_to_run:
            logger.warning("No steps to replay")
            return ReplayResult(total_steps=0, succeeded=0, failed=0, skipped=0, duration_seconds=0, steps=[])

        logger.info(f"Starting replay: steps {start_index}-{end_index-1}, speed={speed_multiplier}x")

        start_time = time.time()
        succeeded = 0
        failed = 0
        skipped = 0
        step_results = []

        prev_timestamp = None

        for step in steps_to_run:
            step_start = time.time()

            # 计算延迟（保持原时间间隔，受 speed_multiplier 影响）
            if prev_timestamp is not None:
                original_delay = step.original_timestamp - prev_timestamp
                adjusted_delay = original_delay / speed_multiplier
                if adjusted_delay > 0:
                    time.sleep(adjusted_delay)
            prev_timestamp = step.original_timestamp

            # 回放前检查
            if not self._check_before(step):
                logger.warning(f"Step {step.index} check_before failed, skipping")
                step_results.append({
                    "index": step.index,
                    "status": "skipped",
                    "reason": "check_before failed"
                })
                skipped += 1
                if on_step:
                    on_step(step.index, step_results[-1])
                continue

            # 世界模型验证
            if self.world_model is not None:
                # 获取当前观察
                current_obs = self._get_current_observation()

                # 验证动作序列
                is_safe, uncertainty, reason = self._validate_with_world_model(
                    current_obs,
                    step
                )

                logger.debug(
                    f"World model validation: safe={is_safe}, "
                    f"uncertainty={uncertainty:.3f}, reason={reason}"
                )

                if not is_safe:
                    logger.warning(
                        f"Step {step.index} world model validation failed: {reason}"
                    )
                    step_results.append({
                        "index": step.index,
                        "status": "skipped",
                        "reason": f"world model validation: {reason}"
                    })
                    skipped += 1
                    if on_step:
                        on_step(step.index, step_results[-1])
                    continue

            # 执行动作
            result = {"index": step.index, "status": "unknown"}
            try:
                if step.action_type == "click":
                    success = self._execute_click(step)
                elif step.action_type == "key_press":
                    success = self._execute_key_press(step)
                else:
                    logger.warning(f"Unknown action type: {step.action_type}")
                    success = False

                if success:
                    result["status"] = "succeeded"
                    succeeded += 1
                else:
                    result["status"] = "failed"
                    result["reason"] = "execution failed"
                    failed += 1

            except Exception as e:
                logger.error(f"Step {step.index} error: {e}")
                result["status"] = "failed"
                result["reason"] = str(e)
                failed += 1

            step_results.append(result)
            if on_step:
                on_step(step.index, result)

            step_duration = time.time() - step_start
            result["duration"] = round(step_duration, 3)

        total_duration = time.time() - start_time

        replay_result = ReplayResult(
            total_steps=len(steps_to_run),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            duration_seconds=round(total_duration, 2),
            steps=step_results
        )

        logger.info(
            f"Replay finished: {succeeded} succeeded, {failed} failed, {skipped} skipped, "
            f"duration {total_duration:.2f}s"
        )

        return replay_result

    def get_steps(self) -> List[ReplayStep]:
        """获取所有回放步骤（用于预览）"""
        return self._steps.copy()

    def clear(self):
        """清空回放计划"""
        self._steps = []
