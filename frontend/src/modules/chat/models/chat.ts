import type { components } from '@/core/types/api.generated'

// Re-export generated API types
export type ChatMessage = components['schemas']['ChatMessage']
export type HappinessImpact = components['schemas']['HappinessImpact']
export type ActionSuggestion =
  | components['schemas']['AssignToRoomAction']
  | components['schemas']['StartTrainingAction']
  | components['schemas']['StartExplorationAction']
  | components['schemas']['RecallExplorationAction']
  | components['schemas']['NoAction']

// Individual action types for type guards
export type AssignToRoomAction = components['schemas']['AssignToRoomAction']
export type StartTrainingAction = components['schemas']['StartTrainingAction']
export type StartExplorationAction = components['schemas']['StartExplorationAction']
export type RecallExplorationAction = components['schemas']['RecallExplorationAction']
export type NoAction = components['schemas']['NoAction']

// Extended message type for frontend display
export interface ChatMessageDisplay {
  type: 'user' | 'dweller'
  content: string
  messageId?: string // Backend dweller_message_id for correlation with WebSocket events
  timestamp?: Date
  avatar?: string
  audioUrl?: string
  transcription?: string
  isPlaying?: boolean
  happinessImpact?: HappinessImpact | null
  actionSuggestion?: ActionSuggestion | null
}
