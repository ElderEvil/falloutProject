/** Consent state of a player-to-player connection. */
export type ConnectionStatus = 'pending' | 'accepted'

export interface ConnectionRead {
  id: string
  requester_id: string
  addressee_id: string
  status: ConnectionStatus
  counterpart_username: string
  created_at: string | null
  responded_at: string | null
}

export interface UserBlockRead {
  id: string
  blocked_id: string
  blocked_username: string
  created_at: string | null
}

export interface DirectMessageRead {
  id: string
  sender_user_id: string
  recipient_user_id: string
  body: string
  is_request: boolean
  created_at: string | null
}

export interface DirectMessageSummary {
  counterpart_user_id: string
  counterpart_username: string
  last_message: DirectMessageRead
  unread_count: number
  has_pending_request: boolean
}