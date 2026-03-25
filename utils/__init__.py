from .logger import logger
from .config_loader import ConfigLoader
# platform_utils 依赖 psutil/win32 等平台库，采用懒导入，避免在单元测试中提前触发依赖
def get_foreground_app():
    from .platform_utils import get_foreground_app as _get
    return _get()
