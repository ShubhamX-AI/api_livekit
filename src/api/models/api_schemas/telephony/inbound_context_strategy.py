from ipaddress import ip_address
from typing import Annotated, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.providers.keys import reject_masked_config

# Inbound Context Strategy Schemas
_BLOCKED_WEBHOOK_HOSTS = {"localhost", "metadata.google.internal"}


def validate_inbound_context_url(url: Optional[str]) -> Optional[str]:
    """Refuse webhook URLs the agent worker must never fetch.

    The worker runs inside our network and POSTs to whatever URL the customer
    stored, so an unvalidated URL is an SSRF hole straight at the metadata
    service. The guard is the host/IP block below, not the scheme — plain http
    is allowed so customers already on it are not locked out of their own
    strategies. Checked at write time only; DNS is not re-resolved at call time.
    """
    if url is None:
        return url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("url must use http or https")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("url must include a host")
    if host in _BLOCKED_WEBHOOK_HOSTS:
        raise ValueError(f"url host '{host}' is not allowed")

    try:
        ip = ip_address(host)
    except ValueError:
        return url  # a name, not a literal IP — nothing more to check here

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise ValueError(f"url host '{host}' resolves to a non-public address")
    return url


class WebhookInboundContextStrategyConfigSchema(BaseModel):
    type: Literal["webhook"] = "webhook"
    url: str = Field(..., min_length=1, max_length=500, description="Webhook URL used to fetch inbound caller context (http/https, public hosts only)")
    headers: dict[str, str] = Field(default_factory=dict, description="Optional headers sent with the inbound context webhook")
    timeout_seconds: float = Field(2.0, ge=0.5, le=10.0, description="Webhook timeout in seconds")

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v):
        return validate_inbound_context_url(v)

    @field_validator("headers")
    @classmethod
    def _no_masked_secrets(cls, v):
        return reject_masked_config(v)


class UpdateWebhookInboundContextStrategyConfigSchema(BaseModel):
    type: Literal["webhook"] = "webhook"
    url: Optional[str] = Field(None, min_length=1, max_length=500, description="Webhook URL used to fetch inbound caller context (http/https, public hosts only)")
    headers: Optional[dict[str, Optional[str]]] = Field(None, description="Headers merged into the stored map. Send a header with value null to delete just that header.")
    timeout_seconds: Optional[float] = Field(None, ge=0.5, le=10.0, description="Webhook timeout in seconds")

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v):
        return validate_inbound_context_url(v)

    @field_validator("headers")
    @classmethod
    def _no_masked_secrets(cls, v):
        return reject_masked_config(v)


InboundContextStrategyConfig = Annotated[
    WebhookInboundContextStrategyConfigSchema,
    Field(discriminator="type"),
]


UpdateInboundContextStrategyConfig = Annotated[
    UpdateWebhookInboundContextStrategyConfigSchema,
    Field(discriminator="type"),
]


class CreateInboundContextStrategy(BaseModel):
    strategy_name: str = Field(..., min_length=1, max_length=100, description="Strategy name")
    strategy_type: Literal["webhook"] = Field(..., description="Strategy type")
    strategy_config: InboundContextStrategyConfig = Field(..., description="Typed strategy config")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "strategy_name": "CRM lookup",
                "strategy_type": "webhook",
                "strategy_config": {
                    "url": "https://example.com/caller-context",
                    "headers": {"Authorization": "Bearer demo-token"},
                    "timeout_seconds": 2.0,
                },
            }
        }

    @model_validator(mode="before")
    @classmethod
    def inject_strategy_type(cls, data: dict):
        if isinstance(data, dict):
            strategy_type = data.get("strategy_type")
            config = data.get("strategy_config")
            if strategy_type and isinstance(config, dict):
                config["type"] = strategy_type
        return data


class UpdateInboundContextStrategy(BaseModel):
    strategy_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Strategy name")
    strategy_type: Optional[Literal["webhook"]] = Field(None, description="Strategy type")
    strategy_config: Optional[UpdateInboundContextStrategyConfig] = Field(None, description="Typed strategy config")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "strategy_name": "CRM lookup v2",
                "strategy_type": "webhook",
                "strategy_config": {
                    "url": "https://example.com/caller-context-v2",
                    "timeout_seconds": 2.0,
                },
            }
        }

    @model_validator(mode="before")
    @classmethod
    def inject_strategy_type(cls, data: dict):
        if isinstance(data, dict):
            strategy_type = data.get("strategy_type")
            config = data.get("strategy_config")
            if strategy_type and isinstance(config, dict):
                config["type"] = strategy_type
        return data

    @model_validator(mode="after")
    def validate_strategy_update(self):
        if not self.model_fields_set:
            raise ValueError("No fields provided for update")

        # Membership, not truthiness: `{"strategy_type": null, "strategy_config": null}`
        # passed the old bool() check and the route's raw $set then nulled
        # strategy_type in Mongo, silently disabling the strategy for every call.
        has_type = "strategy_type" in self.model_fields_set
        has_config = "strategy_config" in self.model_fields_set
        if has_type != has_config:
            raise ValueError(
                "Provide both `strategy_type` and `strategy_config` together, or neither."
            )
        for field in ("strategy_name", "strategy_type", "strategy_config"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(
                    f"`{field}` cannot be null; omit it to leave it unchanged."
                )
        return self
