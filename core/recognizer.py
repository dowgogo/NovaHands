import cv2
import numpy as np
import pyautogui
import os
from utils.logger import logger


class Recognizer:
    def __init__(self, template_dir: str = None):
        raw_path = template_dir or os.path.join(os.path.dirname(__file__), "..", "templates")
        # 安全：路径规范化，防止路径遍历
        self.template_dir = os.path.realpath(raw_path)
        # 限制必须在项目目录内
        project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
        if not self.template_dir.startswith(project_root):
            raise ValueError(
                f"Template directory must be within project root: {self.template_dir}\n"
                f"Project root: {project_root}"
            )
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir)

    def find_button(self, template_name: str, confidence: float = 0.8) -> tuple:
        template_path = os.path.join(self.template_dir, template_name)
        if not os.path.exists(template_path):
            logger.error(f"Template not found: {template_path}")
            return None

        try:
            screenshot = pyautogui.screenshot()
            screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                logger.error(f"Failed to read template: {template_path}")
                return None

            gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= confidence:
                h, w = template.shape
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                logger.debug(f"Found {template_name} at ({center_x},{center_y}) conf={max_val:.2f}")
                return (center_x, center_y)
            else:
                logger.debug(f"Not found {template_name} conf={max_val:.2f}")
                return None
        except Exception as e:
            logger.error(f"Template matching failed: {e}")
            return None
