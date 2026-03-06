from sqlmodel import Field, SQLModel


class AIUsageStats(SQLModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class AIUsageResponse(SQLModel):
    all_time: AIUsageStats
    current_month: AIUsageStats
    month: str
