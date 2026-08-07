from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# ── SIP Trunk Config sub-models ────────────────────────
class TwilioTrunkConfig(BaseModel):
    address: str = Field(..., min_length=1, max_length=100, description="SIP trunk address")
    numbers: List[str] = Field(..., description="SIP trunk numbers")
    username: str = Field(..., min_length=1, max_length=100, description="SIP auth username")
    password: str = Field(..., min_length=1, max_length=100, description="SIP auth password")


class ExotelTrunkConfig(BaseModel):
    exotel_number: str = Field(..., min_length=1, max_length=20, description="Exotel virtual number (caller ID)")
    # Optional overrides for advanced setup
    sip_host: Optional[str] = Field(None, description="Exotel SIP proxy host")
    sip_port: Optional[int] = Field(None, description="Exotel SIP proxy port")
    sip_domain: Optional[str] = Field(None, description="Exotel SIP domain")


# Discriminated union type for Trunks
TrunkConfig = Annotated[
    Union[TwilioTrunkConfig, ExotelTrunkConfig],
    Field(discriminator=None),  # discriminated by trunk_type in parent
]


# For Outbound Trunk creation
class CreateOutboundTrunk(BaseModel):
    trunk_name: str = Field(..., min_length=1, max_length=100, description="Trunk name (cannot be empty)")
    trunk_type: Literal["twilio", "exotel"] = Field(..., description="Trunk type")
    trunk_config: TrunkConfig = Field(..., description="Trunk configuration object (varies by type)")
    passthrough_mode: bool = Field(False, description="When true, bridges web user directly to SIP with no AI agent")
    passthrough_webhook_url: Optional[str] = Field(None, description="Webhook URL for end-of-call notification in passthrough mode")

    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "trunk_name": "My Exotel Trunk",
                "trunk_type": "exotel",
                "trunk_config": {"exotel_number": "08044319240"},
            }
        }

    @model_validator(mode="after")
    def validate_trunk_config_matches_type(self):
        expected = {
            "twilio": TwilioTrunkConfig,
            "exotel": ExotelTrunkConfig,
        }
        if not isinstance(self.trunk_config, expected[self.trunk_type]):
            raise ValueError(f"trunk_config must match trunk_type '{self.trunk_type}'")
        return self
