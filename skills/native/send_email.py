from ..base_skill import BaseSkill


class SendEmailSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="send_email",
            description="通过 Outlook 发送邮件",
            parameters={
                "recipient": "str",
                "subject": "str",
                "body": "str"
            }
        )

    def execute(self, controller, **kwargs):
        recipient = kwargs["recipient"]
        subject = kwargs["subject"]
        body = kwargs["body"]
        # Simulate keyboard shortcuts for Outlook (adjust as needed)
        controller.press_hotkey("ctrl", "n")
        controller.wait(1)
        controller.type_text(recipient)
        controller.press("tab")
        controller.type_text(subject)
        controller.press("tab")
        controller.type_text(body)
        controller.press_hotkey("ctrl", "enter")
