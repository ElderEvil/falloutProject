from pydantic import BaseModel


class OAuthProvidersResponse(BaseModel):
    google: bool
    github: bool


class OAuthHandoffRequest(BaseModel):
    code: str


class OAuthLinkedAccountsResponse(BaseModel):
    providers: list[str]
    has_password: bool


class OAuthLinkAuthorizeResponse(BaseModel):
    authorize_url: str
