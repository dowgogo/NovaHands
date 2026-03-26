import subprocess
import platform
import re
import shlex
import logging
from ..base_skill import BaseSkill

logger = logging.getLogger(__name__)

# 应用名合法性校验：只允许字母、数字、空格、连字符、下划线、点
_APP_NAME_RE = re.compile(r'^[\w\s\-\.]+$')

# 常见应用名映射表（中英文别名 → Windows 可执行文件名）
_APP_ALIASES: dict[str, str] = {
    # 浏览器
    "chrome": "chrome",
    "谷歌": "chrome",
    "谷歌浏览器": "chrome",
    "edge": "msedge",
    "微软edge": "msedge",
    "firefox": "firefox",
    "火狐": "firefox",
    "火狐浏览器": "firefox",
    # 办公
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "ppt": "powerpnt",
    "outlook": "outlook",
    "邮件": "outlook",
    "onenote": "onenote",
    # 系统工具
    "记事本": "notepad",
    "notepad": "notepad",
    "计算器": "calc",
    "calculator": "calc",
    "画图": "mspaint",
    "paint": "mspaint",
    "文件管理器": "explorer",
    "资源管理器": "explorer",
    "explorer": "explorer",
    "cmd": "cmd",
    "命令提示符": "cmd",
    "powershell": "powershell",
    "任务管理器": "taskmgr",
    "task manager": "taskmgr",
    "控制面板": "control",
    "control panel": "control",
    # 媒体
    "vlc": "vlc",
    "spotify": "spotify",
    "网易云": "cloudmusic",
    "微信": "wechat",
    "wechat": "wechat",
    "qq": "qq",
    "钉钉": "dingtalk",
    "dingtalk": "dingtalk",
    "飞书": "feishu",
    "feishu": "feishu",
    # 开发工具
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "pycharm": "pycharm",
    "git": "git-gui",
}


def _resolve_app_name(app_name: str) -> str:
    """将用户输入的应用名解析为可执行文件名。"""
    key = app_name.lower().strip()
    resolved = _APP_ALIASES.get(key, app_name)
    if resolved != app_name:
        logger.info(f"App alias resolved: '{app_name}' → '{resolved}'")
    return resolved


class OpenAppSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="open_app",
            description="打开指定的应用程序，支持常见中英文应用名（如：记事本、Chrome、微信、Excel、计算器等）",
            parameters={"app_name": "str"}
        )

    def execute(self, controller, **kwargs):
        app_name = kwargs["app_name"]

        # 安全校验：防止命令注入
        if not _APP_NAME_RE.match(app_name):
            raise ValueError(
                f"Invalid app_name '{app_name}': only alphanumeric, spaces, hyphens, underscores and dots are allowed."
            )

        # 解析别名
        resolved = _resolve_app_name(app_name)

        system = platform.system()
        try:
            if system == 'Windows':
                # 使用列表形式，不使用 shell=True，避免 shell 注入
                subprocess.Popen(['cmd', '/c', 'start', '', resolved])
            elif system == 'Darwin':
                subprocess.Popen(['open', '-a', resolved])
            elif system == 'Linux':
                # 跨平台修复：Linux 下应用名可能含空格（如 "Visual Studio Code"）
                # 使用 shlex.split 将字符串拆成参数列表，避免 Popen 把空格误认为路径分隔符
                # 注意：_APP_NAME_RE 已确保 app_name 无 shell 注入字符，shlex.split 是安全的
                args = shlex.split(resolved)
                subprocess.Popen(args)
            else:
                raise NotImplementedError(f"Unsupported OS: {system}")
            logger.info(f"Launched app: '{resolved}' (input: '{app_name}')")
        except Exception as e:
            raise RuntimeError(f"Failed to open '{app_name}' (resolved: '{resolved}'): {e}")
