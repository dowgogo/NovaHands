import platform
import subprocess
import psutil
import logging

logger = logging.getLogger('novahands')


def get_foreground_app() -> str:
    """Return name of current foreground window's process.

    跨平台兼容说明：
    - Windows：依赖 win32gui / win32process（已在 virtual_test 中 mock）
    - macOS：依赖 osascript；headless（CI）环境下 osascript 无法获取窗口信息，返回 "unknown"
    - Linux：依赖 xdotool（需额外安装）；未安装或 DISPLAY 不存在时返回 "unknown"
    所有分支均捕获异常，保证调用方不会因平台差异崩溃。
    """
    system = platform.system()
    try:
        if system == 'Windows':
            import win32gui
            import win32process
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name()

        elif system == 'Darwin':
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True,
                timeout=5  # 防止 headless 环境长时间阻塞
            )
            name = result.stdout.strip()
            # headless/CI 环境下 osascript 返回空字符串或错误
            if result.returncode != 0 or not name:
                logger.debug(f"osascript failed (returncode={result.returncode}), returning 'unknown'")
                return "unknown"
            return name

        elif system == 'Linux':
            # 跨平台修复：先检查 DISPLAY 环境变量，避免 headless 环境报错
            import os
            if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                logger.debug("No DISPLAY/WAYLAND_DISPLAY found (headless?), returning 'unknown'")
                return "unknown"

            # 检查 xdotool 是否可用（避免 FileNotFoundError 崩溃）
            which_result = subprocess.run(
                ['which', 'xdotool'],
                capture_output=True, text=True
            )
            if which_result.returncode != 0:
                logger.debug("xdotool not found, returning 'unknown'. Install with: sudo apt install xdotool")
                return "unknown"

            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowpid'],
                capture_output=True, text=True,
                timeout=5
            )
            if result.returncode != 0 or not result.stdout.strip():
                logger.debug(f"xdotool failed (returncode={result.returncode}), returning 'unknown'")
                return "unknown"

            pid = result.stdout.strip()
            if pid.isdigit():
                process = psutil.Process(int(pid))
                return process.name()
            return "unknown"

        else:
            return "unknown"

    except FileNotFoundError as e:
        # 工具（win32gui / osascript / xdotool）未安装
        logger.debug(f"get_foreground_app: dependency not found: {e}")
        return "unknown"
    except subprocess.TimeoutExpired:
        logger.warning("get_foreground_app: subprocess timed out, returning 'unknown'")
        return "unknown"
    except Exception as e:
        logger.error(f"Failed to get foreground app: {e}")
        return "unknown"
