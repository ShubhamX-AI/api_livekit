from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.core.providers.keys import reject_masked_config


# ---- Tool Schemas ----
class ToolParameterSchema(BaseModel):
    """Parameter definition for a tool."""

    name: str = Field(..., min_length=1, max_length=50, description="Parameter name")
    type: Literal["string", "number", "boolean", "object", "array"] = Field("string", description="Parameter data type")
    description: Optional[str] = Field(None, max_length=300, description="Parameter description for the LLM")
    required: bool = Field(True, description="Whether the parameter is required")
    enum: Optional[List[str]] = Field(None, description="Allowed values (only for string type)")


class CreateTool(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z_][a-z0-9_]*$", description="Tool name in snake_case (e.g. lookup_weather)")
    tool_description: str = Field(..., min_length=1, max_length=500, description="What the tool does (shown to LLM)")
    tool_parameters: List[ToolParameterSchema] = Field(default=[], description="Tool parameter definitions")
    tool_execution_type: Literal["webhook", "static_return"] = Field(..., description="How the tool executes: 'webhook' (HTTP POST) or 'static_return' (fixed value)")
    tool_execution_config: dict = Field(..., description="Execution config: {'url': '...'} for webhook, {'value': ...} for static_return")

    @field_validator("tool_execution_config")
    @classmethod
    def _no_masked_secrets(cls, v):
        return reject_masked_config(v)

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "tool_name": "lookup_weather",
                "tool_description": "Look up weather information for a given location",
                "tool_parameters": [
                    {
                        "name": "location",
                        "type": "string",
                        "description": "City name to look up",
                        "required": True,
                    }
                ],
                "tool_execution_type": "webhook",
                "tool_execution_config": {"url": "https://api.example.com/weather"},
            }
        }


class UpdateTool(BaseModel):
    tool_name: Optional[str] = Field(None, min_length=1, max_length=100, pattern=r"^[a-z_][a-z0-9_]*$", description="Tool name in snake_case")
    tool_description: Optional[str] = Field(None, min_length=1, max_length=500, description="What the tool does")
    tool_parameters: Optional[List[ToolParameterSchema]] = Field(None, description="Tool parameter definitions")
    tool_execution_type: Optional[Literal["webhook", "static_return"]] = Field(None, description="Execution type")
    tool_execution_config: Optional[dict] = Field(None, description="Execution config")

    @field_validator("tool_execution_config")
    @classmethod
    def _no_masked_secrets(cls, v):
        return reject_masked_config(v)

    class Config:
        str_strip_whitespace = True


class AttachToolsRequest(BaseModel):
    tool_ids: List[str] = Field(..., min_length=1, description="List of tool IDs to attach/detach")
