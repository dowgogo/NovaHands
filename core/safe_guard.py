import logging
from typing import List
from utils.config_loader import ConfigLoader
from utils.platform_utils import get_foreground_app
from gui.confirm_dialog import confirm_operation

logger = logging.getLogger('novahands')

# confirm_timeout 最小值（秒），防止配置为 0 或负数导致对话框立即关闭
_MIN_CONFIRM_TIMEOUT = 5


class SafeGuard:
    def __init__(self):
        self.config = ConfigLoader()
        security = self.config.get_security()
        self.allowed_apps: List[str] = security.get('allowed_apps', [])
        self.sensitive_ops: List[str] = security.get('sensitive_operations', [])

        # 安全修复：timeout 做最小值校验，防止配置为 0/负数
        raw_timeout = security.get('confirm_timeout', 30)
        self.confirm_timeout = max(_MIN_CONFIRM_TIMEOUT, int(raw_timeout))

        # 安全修复：若白名单为空，发出警告（运行时将对所有应用返回 False）
        if not self.allowed_apps:
            logger.warning(
                "Security: allowed_apps is empty. "
                "check_app_allowed() will deny all applications. "
                "Update config.json to add allowed apps."
            )

    def check_app_allowed(self, process_name: str = None) -> bool:
        if process_name is None:
            process_name = get_foreground_app()
        base_name = process_name.lower()
        # 安全修复：白名单为空时采用 deny-all 策略
        if not self.allowed_apps:
            return False
        for allowed in self.allowed_apps:
            if base_name == allowed.lower():
                return True
        logger.warning(f"App '{base_name}' not in whitelist")
        return False

    def is_operation_sensitive(self, op_type: str) -> bool:
        return op_type in self.sensitive_ops

    def request_confirmation(self, op_type: str, details: str = "") -> bool:
        # 安全修复：details 截断，防止敏感信息写入 INFO 日志
        safe_details = details[:100] if details else ""
        logger.info(f"Request confirmation: op_type={op_type!r} (details omitted from log)")
        logger.debug(f"Confirmation details: {safe_details!r}")
        return confirm_operation(f"操作: {op_type}\n{safe_details}", timeout=self.confirm_timeout)

    def get_current_app(self) -> str:
        return get_foreground_app()

