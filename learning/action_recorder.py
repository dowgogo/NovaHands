import threading
import time
from dataclasses import dataclass
from typing import Optional
from pynput import mouse, keyboard
from utils.logger import logger

# 录制队列最大长度，防止长时间录制导致内存耗尽
_MAX_ACTIONS = 10_000


@dataclass
class Action:
    timestamp: float
    type: str
    details: dict
    app: Optional[str] = None


class ActionRecorder:
    def __init__(self, safe_guard):
        self.safe_guard = safe_guard
        self.actions = []
        self.recording = False
        self.lock = threading.Lock()
        self._start_stop_lock = threading.Lock()  # 防止 start/stop 并发调用的竞态
        self.mouse_listener = None
        self.keyboard_listener = None

    def start_recording(self):
        with self._start_stop_lock:
            if self.recording:
                return
            self.recording = True
            self.actions = []
            self.mouse_listener = mouse.Listener(on_click=self._on_click)
            self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
            self.mouse_listener.start()
            self.keyboard_listener.start()
            logger.info("Recording started")

    def stop_recording(self):
        with self._start_stop_lock:
            if not self.recording:
                return
            self.recording = False
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener.join()  # 等待线程完全停止
                self.mouse_listener = None
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener.join()  # 等待线程完全停止
                self.keyboard_listener = None
            logger.info(f"Recording stopped. Captured {len(self.actions)} actions.")

    def _on_click(self, x, y, button, pressed):
        if not self.recording or not pressed:
            return
        with self.lock:
            if len(self.actions) >= _MAX_ACTIONS:
                logger.warning(f"ActionRecorder: max actions ({_MAX_ACTIONS}) reached, discarding further events.")
                return
            action = Action(
                timestamp=time.time(),
                type="click",
                details={"x": x, "y": y, "button": str(button)},
                app=self.safe_guard.get_current_app()
            )
            self.actions.append(action)

    def _on_key_press(self, key):
        if not self.recording:
            return
        with self.lock:
            if len(self.actions) >= _MAX_ACTIONS:
                return
            key_str = str(key)
            # 隐私保护：将普通字符键（可能是密码等）替换为占位符，只保留功能键
            if hasattr(key, 'char') and key.char and key.char.isprintable():
                key_str = "<CHAR>"  # 不记录实际字符，防止 Keylogger 效果
            action = Action(
                timestamp=time.time(),
                type="key_press",
                details={"key": key_str},
                app=self.safe_guard.get_current_app()
            )
            self.actions.append(action)

    def get_actions(self):
        with self.lock:
            return self.actions.copy()

