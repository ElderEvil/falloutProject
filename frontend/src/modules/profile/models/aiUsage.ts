export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface AIUsageStats {
  all_time: TokenUsage
  current_month: TokenUsage
  month: string
}
