import logging
import sys


def setup_logger():
    logger = logging.getLogger('novahands')
    logger.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    # File handler (will be configured after config loaded)
    fh = logging.FileHandler('novahands.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


logger = setup_logger()
