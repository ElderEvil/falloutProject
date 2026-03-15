from sqlmodel import Field, SQLModel


class AIUsageStats(SQLModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class QuotaInfo(SQLModel):
    quota_limit: int = Field(default=100000, ge=0)
    quota_used: int = Field(default=0, ge=0)
    quota_remaining: int = Field(default=0, ge=0)
    quota_percentage: float = Field(default=0.0, ge=0.0)
    quota_warning: bool = Field(default=False)
    quota_exceeded: bool = Field(default=False)
    reset_date: str = ""


class AIUsageResponse(SQLModel):
    all_time: AIUsageStats
    current_month: AIUsageStats
    quota: QuotaInfo
    month: str
