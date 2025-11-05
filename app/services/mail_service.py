from fastapi import BackgroundTasks, HTTPException
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import EmailStr

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

    async def SEND_MEDICINE_REQUEST_STATUS_MAIL(
        self,
        user_email: EmailStr,
        user_name: str,
        medicine_name: str,
        generic_name: str,
        status: str,
        response: str | None = None,
    ):
        subject = f"Your medicine request has been {status.capitalize()}"
        body_html = f"""
                <h3>Hello {user_name},</h3>
                <p>Your request for <b>{medicine_name} ({generic_name})</b> has been <b>{status.capitalize()}</b>.</p>
            """
        if response:
            body_html += f"<p><i>Admin response:</i> {response}</p>"

        body_html += "<p>Thank you for using Medico Store.</p>"
        message = MessageSchema(
            subject=subject,
            recipients=[user_email],
            body=body_html,
            subtype="html",
        )
        fast_mail_obj = FastMail(self.mail_conf)
        await fast_mail_obj.send_message(message)
