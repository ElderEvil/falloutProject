import type { components } from '@/core/types/api.generated'

// Re-export generated API types
export type ChatMessage = components['schemas']['ChatMessage']
export type HappinessImpact = components['schemas']['HappinessImpact']
export type ActionSuggestion = components['schemas']['AssignToRoomAction'] | components['schemas']['StartTrainingAction'] | components['schemas']['NoAction']

// Extended message type for frontend display
export interface ChatMessageDisplay {
  type: 'user' | 'dweller'
  content: string
  timestamp?: Date
  avatar?: string
  audioUrl?: string
  transcription?: string
  isPlaying?: boolean
  happinessImpact?: HappinessImpact | null
  actionSuggestion?: ActionSuggestion | null
}
