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