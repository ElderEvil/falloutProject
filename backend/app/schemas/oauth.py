from pydantic import BaseModel


class OAuthProvidersResponse(BaseModel):
    google: bool
    github: bool


class OAuthHandoffRequest(BaseModel):
    code: str
