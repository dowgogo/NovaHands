import pyautogui
import time
from core.safe_guard import SafeGuard
from utils.logger import logger
from utils.config_loader import ConfigLoader

# 单次 wait 最长允许秒数，防止外部传入极大值阻塞
_MAX_WAIT_SECONDS = 60.0


class Controller:
    def __init__(self):
        self.safe_guard = SafeGuard()
        config = ConfigLoader()
        # 安全修复：FAILSAFE 默认改为 True（移动鼠标至屏幕角可中断操作）
        pyautogui.FAILSAFE = config.get('security.enable_failsafe', True)
        pyautogui.PAUSE = 0.1
        # 获取屏幕尺寸，用于坐标边界校验
        self._screen_w, self._screen_h = pyautogui.size()

    def _clamp_coords(self, x: int, y: int):
        """将坐标限制在屏幕范围内"""
        x = max(0, min(int(x), self._screen_w - 1))
        y = max(0, min(int(y), self._screen_h - 1))
        return x, y

    def _check_sensitive(self, op_type: str, details: str = "") -> bool:
        if self.safe_guard.is_operation_sensitive(op_type):
            return self.safe_guard.request_confirmation(op_type, details)
        return True

    def click(self, x: int, y: int, button: str = 'left', check_sensitive: bool = False):
        x, y = self._clamp_coords(x, y)
        if check_sensitive and not self._check_sensitive('click', f"({x},{y})"):
            return
        pyautogui.click(x, y, button=button)
        logger.debug(f"Click ({x},{y}) button={button}")

    def type_text(self, text: str, interval: float = 0.05, check_sensitive: bool = True):
        # 安全修复：check_sensitive 默认改为 True；不记录文本内容防止敏感信息泄露
        if check_sensitive and not self._check_sensitive('send_keys', f"text_length={len(text)}"):
            return
        pyautogui.write(text, interval=interval)
        logger.debug(f"Typed text of length {len(text)}")  # 不记录实际内容

    def press(self, key: str, check_sensitive: bool = False):
        if check_sensitive and not self._check_sensitive('press_key', key):
            return
        pyautogui.press(key)

    def press_hotkey(self, *keys, check_sensitive: bool = True):
        # 安全修复：hotkey 默认开启敏感检查
        if check_sensitive and not self._check_sensitive('hotkey', '+'.join(keys)):
            return
        pyautogui.hotkey(*keys)

    def wait(self, seconds: float):
        # 安全修复：限制最大等待时间，防止外部传入极大值阻塞
        seconds = max(0.0, min(float(seconds), _MAX_WAIT_SECONDS))
        time.sleep(seconds)

    def move_to(self, x: int, y: int, duration: float = 0.5):
        x, y = self._clamp_coords(x, y)
        pyautogui.moveTo(x, y, duration=duration)

    def scroll(self, clicks: int, x: int = None, y: int = None):
        if x is not None and y is not None:
            x, y = self._clamp_coords(x, y)
        pyautogui.scroll(clicks, x=x, y=y)

