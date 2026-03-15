export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface AIUsageStats {
  all_time: TokenUsage
  current_month: TokenUsage
  month: string
  quota_limit: number
  quota_used: number
  quota_remaining: number
  quota_percentage: number
  quota_warning: boolean
  quota_exceeded: boolean
  reset_date: string
}
