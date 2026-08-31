from sqlmodel import Field, SQLModel


class AIUsageStats(SQLModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class AIOperationStats(SQLModel):
    """Token breakdown for one operation tag (LLMInteraction.usage).

    NULL usage is reported as "unknown"; legacy tags may also appear.
    """

    operation: str
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    count: int = Field(default=0, ge=0)
    is_operational: bool = Field(default=False)  # True for quota_tracking (bookkeeping, not an LLM request)


class QuotaInfo(SQLModel):
    quota_limit: int = Field(default=100000, ge=0)
    quota_used: int = Field(default=0, ge=0)
    quota_remaining: int = Field(default=0, ge=0)
    quota_percentage: float = Field(default=0.0, ge=0.0)
    quota_warning: bool = Field(default=False)
    quota_exceeded: bool = Field(default=False)
    reset_date: str = ""


class AIUsageResponse(SQLModel):
    """Per-user AI usage with quota status.

    by_operation covers the current month so operation shares align with
    quota_used ("bio generation: 40% of quota"). Cost estimation is
    intentionally deferred: honest pricing needs per-interaction provider/model
    rates (input/output prices differ; image/audio are not token-priced).
    LLMInteraction already snapshots provider/model to support that later.
    """

    all_time: AIUsageStats
    current_month: AIUsageStats
    quota: QuotaInfo
    month: str
    by_operation: list[AIOperationStats] = Field(default_factory=list)
    chat_heavy: bool = Field(default=False)  # chat_with_dweller > 80% of non-operational monthly tokens
