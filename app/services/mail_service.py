from datetime import datetime, timedelta

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

    async def SEND_RESET_TOKEN(self, email: str, link: str):
        message = MessageSchema(
            subject="Welcome to Medico Store your modern AI Powered E-Pharmacy Team",
            recipients=[email],
            body=f"""
                <h3>Don't We Got You!</h3>
                <p>Click the link below to reset your password</p>
                <a href="{link}">{link}</a>
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

    async def SEND_PAYMENT_NOTIFICATION_MAIL(
        self,
        user_email: EmailStr,
        user_name: str,
        request_order_id: int,
        total_amount: float,
        prescription_id: int | None,
        payment_link: str,
    ):
        """
        Sends payment notification email to the customer when an order is approved
        and payment is awaited. Includes order details and a 24-hour deadline.
        """
        deadline = (datetime.utcnow() + timedelta(hours=24)).strftime(
            "%d %B %Y, %I:%M %p UTC"
        )
        subject = "Payment Request for Your Medico Store Order"
        body_html = f"""
            <h3>Hello {user_name},</h3>
            <p>Your request order <b>#{request_order_id}</b> is now <b>approved</b> and ready for payment.</p>
            <p><b>Prescription ID:</b> {prescription_id or 'N/A'}<br/>
            <b>Total Amount:</b> ₹{total_amount:.2f}<br/>
            <b>Payment Deadline:</b> {deadline}</p>

            <p>Please complete your payment within the next <b>24 hours</b> to avoid automatic cancellation.</p>

            <p>
                <a href="{payment_link}" 
                   style="background-color: #007BFF; color: white; padding: 10px 18px; 
                          text-decoration: none; border-radius: 5px;">
                    Pay Now
                </a>
            </p>

            <p>If you’ve already made the payment, please ignore this email.</p>
            <br/>
            <p>Thank you for choosing <b>Medico Store</b>!</p>
        """
        message = MessageSchema(
            subject=subject,
            recipients=[user_email],
            body=body_html,
            subtype="html",
        )
        fast_mail_obj = FastMail(self.mail_conf)
        await fast_mail_obj.send_message(message)
