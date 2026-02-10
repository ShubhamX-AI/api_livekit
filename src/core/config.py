import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings"""
    def __init__(self):
        self.PORT = int(os.getenv("PORT", "8000"))
        self.DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
        self.SMTP_HOST = os.getenv("SMTP_HOST", "smtp.sendgrid.net")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USER = os.getenv("SMTP_USER", "apikey")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@yourdomain.com")
        self.FROM_NAME = os.getenv("FROM_NAME", "Your App Name")

settings = Settings()
