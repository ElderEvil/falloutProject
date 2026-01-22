import type { components } from '@/core/types/api.generated'

// Re-export generated API types
export type ChatMessage = components['schemas']['ChatMessage']

// Extended message type for frontend display
export interface ChatMessageDisplay {
  type: 'user' | 'dweller'
  content: string
  timestamp?: Date
  avatar?: string
  audioUrl?: string
  transcription?: string
  isPlaying?: boolean
}
