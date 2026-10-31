from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    """Request models reject unknown fields so clients can't set id/user_id/timestamps."""

    model_config = ConfigDict(extra="forbid")


class CamelSchema(BaseModel):
    """camelCase on the wire (accessToken, refreshToken, ...), snake_case in Python."""

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
