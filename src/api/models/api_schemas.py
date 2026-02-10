from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# Model for creating API key
class CreateApiKeyRequest(BaseModel):
    user_name: str = Field(..., min_length=1, max_length=20, description="User's name (cannot be empty)")
    org_name: Optional[str] = Field(None, max_length=50, description="Organization name (optional)")
    user_email: EmailStr = Field(..., description="User's email address (cannot be empty)")
    
    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "user_name": "Shubhan Halder",
                "org_name": "Indus Net Technologies",
                "user_email": "[EMAIL_ADDRESS]"
            }
        }
