import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """SMTP Email Service using SendGrid"""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.sendgrid.net")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "apikey")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@yourdomain.com")
        self.from_name = os.getenv("FROM_NAME", "Your App Name")
    
    def send_email(
        self,
        to_email: str | List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> bool:
        """
        Send an email via SMTP
        
        Args:
            to_email: Recipient email address(es)
            subject: Email subject
            body: Plain text email body
            html_body: Optional HTML email body
            from_email: Optional custom from email (defaults to env FROM_EMAIL)
            from_name: Optional custom from name (defaults to env FROM_NAME)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            
            # Set from address
            sender_email = from_email or self.from_email
            sender_name = from_name or self.from_name
            msg["From"] = f"{sender_name} <{sender_email}>"
            
            # Set to address(es)
            if isinstance(to_email, list):
                msg["To"] = ", ".join(to_email)
                recipients = to_email
            else:
                msg["To"] = to_email
                recipients = [to_email]
            
            msg["Subject"] = subject
            
            # Attach plain text body
            msg.attach(MIMEText(body, "plain"))
            
            # Attach HTML body if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            
            # Send email via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
