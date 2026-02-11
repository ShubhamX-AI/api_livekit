from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field, EmailStr


# API key storage
class APIKey(Document):
    """API key model for Beanie ODM"""
    api_key: Indexed(str, unique=True)
    user_name: str
    org_name: Optional[str] = None
    user_email: Indexed(EmailStr, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    class Settings:
        name = "api_keys"  # Collection name in MongoDB