        key = step.details.get("key", "")
        # 隐私保护：不允许回放字符键（防止密码泄露）
        if key == "<CHAR>" or key == "<LETTER>" or key == "<unknown>":
            logger.debug(f"Skipping sanitized key: {key}")
            return True
        try:
            if key.startswith("Key."):
                key_name = key.split(".")[-1]
                pyautogui.press(key_name)
            else:
                # 直接传入键名
                pyautogui.press(key)
            logger.debug(f"Pressed key: {key}")
            return True
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return False