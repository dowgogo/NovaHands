import logging
from ..base_skill import BaseSkill

logger = logging.getLogger(__name__)

# 参数长度限制，防止超长内容误操作或注入
_MAX_RECIPIENT_LEN = 256
_MAX_SUBJECT_LEN = 200
_MAX_BODY_LEN = 10000


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

        # 安全校验：参数不能为空
        if not recipient or not recipient.strip():
            raise ValueError("send_email: recipient cannot be empty")
        if not subject or not subject.strip():
            raise ValueError("send_email: subject cannot be empty")
        # body 允许为空（可以发无内容邮件），但不允许为 None
        if body is None:
            raise ValueError("send_email: body cannot be None")

        # 安全校验：限制长度，防止超长内容通过键盘模拟写入
        if len(recipient) > _MAX_RECIPIENT_LEN:
            raise ValueError(
                f"send_email: recipient too long ({len(recipient)} chars, max {_MAX_RECIPIENT_LEN})"
            )
        if len(subject) > _MAX_SUBJECT_LEN:
            raise ValueError(
                f"send_email: subject too long ({len(subject)} chars, max {_MAX_SUBJECT_LEN})"
            )
        if len(body) > _MAX_BODY_LEN:
            raise ValueError(
                f"send_email: body too long ({len(body)} chars, max {_MAX_BODY_LEN})"
            )

        logger.info(
            f"Sending email via Outlook: to={recipient[:50]!r}, "
            f"subject={subject[:50]!r}, body_len={len(body)}"
        )

        # 通过 Outlook 快捷键模拟发送邮件
        controller.press_hotkey("ctrl", "n")
        controller.wait(1)
        controller.type_text(recipient)
        controller.press("tab")
        controller.type_text(subject)
        controller.press("tab")
        controller.type_text(body)
        controller.press_hotkey("ctrl", "enter")
