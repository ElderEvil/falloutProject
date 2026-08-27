export type AIProvider = 'openai' | 'anthropic' | 'ollama' | 'lmstudio'

export type AIMode = 'gateway' | 'direct' | 'ollama' | 'lmstudio' | 'disabled'

export interface AIProfile {
  id: string
  provider: AIProvider | null
  model: string | null
  base_url: string | null
  gateway_route: string | null
  updated_at: string | null
}

export interface AIEffective {
  provider: string
  model: string
  base_url: string | null
  gateway_route: string | null
  mode: AIMode
}

export interface AISettingsRead {
  profile: AIProfile | null
  effective: AIEffective
}

export interface AISettingsUpdate {
  provider?: AIProvider | null
  model?: string | null
  base_url?: string | null
  gateway_route?: string | null
}

export const AI_PROVIDER_OPTIONS: { value: AIProvider | ''; label: string }[] = [
  { value: '', label: 'Default (from env)' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'lmstudio', label: 'LM Studio' },
]

export type AISettingsTestResult =
  | { status: 'ok'; latency_ms: number; model: string }
  | { status: 'error'; latency_ms: number | null; model: string | null; message: string }
