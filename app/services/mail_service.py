from fastapi import BackgroundTasks, HTTPException
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema

from app.core.config import settings


class MailService:
    def __init__(self) -> None:
        self.mail_conf = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
        )

    async def SEND_ONBOARDING_MAIL(self, email: str, magic_link: str):
        message = MessageSchema(
            subject="Welcome to Medico Store your modern AI Powered E-Pharmacy Team",
            recipients=[email],
            body=f"""
                <h3>Welcome!</h3>
                <p>Click the link below to set your password and activate your account:</p>
                <a href="{magic_link}">{magic_link}</a>
                """,
            subtype="html",
        )

        fast_mail_obj = FastMail(self.mail_conf)
        await fast_mail_obj.send_message(message=message)
