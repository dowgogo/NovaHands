import subprocess
import platform
import re
import shlex
from ..base_skill import BaseSkill

# 应用名合法性校验：只允许字母、数字、空格、连字符、下划线、点
_APP_NAME_RE = re.compile(r'^[\w\s\-\.]+$')


class OpenAppSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="open_app",
            description="打开指定的应用程序",
            parameters={"app_name": "str"}
        )

    def execute(self, controller, **kwargs):
        app_name = kwargs["app_name"]

        # 安全校验：防止命令注入
        if not _APP_NAME_RE.match(app_name):
            raise ValueError(
                f"Invalid app_name '{app_name}': only alphanumeric, spaces, hyphens, underscores and dots are allowed."
            )

        system = platform.system()
        try:
            if system == 'Windows':
                # 使用列表形式，不使用 shell=True，避免 shell 注入
                subprocess.Popen(['cmd', '/c', 'start', '', app_name])
            elif system == 'Darwin':
                subprocess.Popen(['open', '-a', app_name])
            elif system == 'Linux':
                # 跨平台修复：Linux 下应用名可能含空格（如 "Visual Studio Code"）
                # 使用 shlex.split 将字符串拆成参数列表，避免 Popen 把空格误认为路径分隔符
                # 注意：_APP_NAME_RE 已确保 app_name 无 shell 注入字符，shlex.split 是安全的
                args = shlex.split(app_name)
                subprocess.Popen(args)
            else:
                raise NotImplementedError(f"Unsupported OS: {system}")
        except Exception as e:
            raise RuntimeError(f"Failed to open {app_name}: {e}")
