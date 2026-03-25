import logging
import sys
from pathlib import Path


def setup_logger():
    logger = logging.getLogger('novahands')

    # 避免重复添加 handler（模块被多次 reload 时）
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    # 修复：不传播到根 logger，避免日志被宿主程序（如 uvicorn）重复输出
    logger.propagate = False

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    # File handler：修复为绝对路径，日志固定在项目根目录的 logs/ 下
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "novahands.log"
    fh = logging.FileHandler(str(log_file), encoding='utf-8')
    fh.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


logger = setup_logger()
