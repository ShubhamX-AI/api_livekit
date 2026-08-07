from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# Incoming Call Config
class InboundTwilioConfig(BaseModel):
    type: Literal["twilio"]
    phone_number: str = Field(..., min_length=1, max_length=30, description="Twilio inbound phone number")


class InboundExotelConfig(BaseModel):
    type: Literal["exotel"]
    phone_number: str = Field(..., min_length=1, max_length=30, description="Exotel inbound phone number")


InboundConfig = Annotated[
    Union[InboundTwilioConfig, InboundExotelConfig],
    Field(discriminator="type"),
]


class AssignInboundNumber(BaseModel):
    assistant_id: str = Field(..., min_length=1, max_length=100, description="Assistant ID")
    inbound_context_strategy_id: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional inbound context strategy ID")
    service: Literal["exotel", "twilio"] = Field(..., description="Inbound service")
    inbound_config: InboundConfig = Field(..., description="Configuration object based on service type")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "assistant_id": "Test Assistant ID",
                "inbound_context_strategy_id": "strategy-123",
                "service": "exotel",
                "inbound_config": {"type": "exotel", "phone_number": "+918044319240"},
            }
        }

    @model_validator(mode="before")
    @classmethod
    def inject_type_into_config(cls, data: Any) -> Any:
        if isinstance(data, dict):
            service = data.get("service")
            config = data.get("inbound_config")

            if service and isinstance(config, dict) and "type" not in config:
                # Mirror the top-level service to the config object's type
                config["type"] = service

        return data

    @model_validator(mode="after")
    def validate_service_matches_config(self):
        # We check again after parsing to ensure everything is consistent
        if self.service != self.inbound_config.type:
            raise ValueError(
                f"service '{self.service}' must match inbound_config.type '{self.inbound_config.type}'"
            )
        return self


class UpdateInboundMapping(BaseModel):
    assistant_id: Optional[str] = Field(None, min_length=1, max_length=100, description="Assistant ID")
    inbound_context_strategy_id: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional inbound context strategy ID; send null to detach")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "assistant_id": "Updated Assistant ID",
                "inbound_context_strategy_id": "strategy-123",
            }
        }

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self
