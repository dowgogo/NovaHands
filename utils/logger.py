import logging
import sys
from pathlib import Path


def setup_logger(log_level: str = "INFO", log_file: str = None):
    """配置 novahands logger。

    Parameters
    ----------
    log_level : str
        日志级别，来自 config.json logging.level，默认 INFO。
    log_file : str | None
        日志文件路径；None 时使用项目根目录下 logs/novahands.log。
    """
    logger = logging.getLogger('novahands')

    # 避免重复添加 handler（模块被多次 reload 时）
    if logger.handlers:
        return logger

    # 将配置文件中的字符串 level 转换为 logging 常量（无效值 fallback 到 INFO）
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(logging.DEBUG)  # logger 本身接收全部，由 handler 控制输出粒度
    # 修复：不传播到根 logger，避免日志被宿主程序（如 uvicorn）重复输出
    logger.propagate = False

    # Console handler：级别由配置决定
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(numeric_level)

    # File handler：始终保留 DEBUG 级别（方便排查）
    if log_file:
        log_path = Path(log_file)
    else:
        log_path = Path(__file__).parent.parent / "logs" / "novahands.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(log_path), encoding='utf-8')
    fh.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


# 默认实例（未传入 config 时使用 INFO 级别）
logger = setup_logger()

