import platform
import subprocess
import psutil
import logging

logger = logging.getLogger('novahands')


def get_foreground_app() -> str:
    """Return name of current foreground window's process."""
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
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            return result.stdout.strip()
        elif system == 'Linux':
            # Requires xdotool: sudo apt install xdotool
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowpid'],
                capture_output=True, text=True
            )
            pid = result.stdout.strip()
            if pid:
                process = psutil.Process(int(pid))
                return process.name()
            else:
                return "unknown"
        else:
            return "unknown"
    except Exception as e:
        logger.error(f"Failed to get foreground app: {e}")
        return "unknown"
