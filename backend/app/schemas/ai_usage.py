from sqlmodel import SQLModel


class AIUsageStats(SQLModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AIUsageResponse(SQLModel):
    all_time: AIUsageStats
    current_month: AIUsageStats
    month: str
