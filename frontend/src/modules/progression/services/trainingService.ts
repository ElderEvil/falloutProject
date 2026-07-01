import * as http from '@/core/plugins/httpClient'
import type { components } from '@/core/types/api.generated'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

/**
 * Start training a dweller in a training room
 * @param dwellerId - UUID of the dweller to train
 * @param roomId - UUID of the training room
 * @param token - Auth token
 * @returns Created training session
 */
export async function startTraining(
  dwellerId: string,
  roomId: string,
  token: string
): Promise<TrainingRead> {
  return await http.apiPost<TrainingRead>(
    `/api/v1/training/start?dweller_id=${dwellerId}&room_id=${roomId}`,
    undefined,
    { headers: { Authorization: `Bearer ${token}` } }
  )
}

/**
 * Get active training for a dweller
 * @param dwellerId - UUID of the dweller
 * @param token - Auth token
 * @returns Active training session or null
 */
export async function getDwellerTraining(
  dwellerId: string,
  token: string
): Promise<TrainingRead | null> {
  return await http.apiGet<TrainingRead | null>(`/api/v1/training/dweller/${dwellerId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

/**
 * Get all active training sessions in a vault
 * @param vaultId - UUID of the vault
 * @param token - Auth token
 * @returns List of active training sessions
 */
export async function getVaultTrainings(vaultId: string, token: string): Promise<TrainingRead[]> {
  return await http.apiGet<TrainingRead[]>(`/api/v1/training/vault/${vaultId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

/**
 * Get training progress details
 * @param trainingId - UUID of the training session
 * @param token - Auth token
 * @returns Training session with progress information
 */
export async function getTrainingProgress(
  trainingId: string,
  token: string
): Promise<TrainingProgress> {
  return await http.apiGet<TrainingProgress>(`/api/v1/training/${trainingId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

/**
 * Cancel an active training session
 * @param trainingId - UUID of the training session
 * @param token - Auth token
 * @returns Cancelled training session
 */
export async function cancelTraining(trainingId: string, token: string): Promise<TrainingRead> {
  return await http.apiPost<TrainingRead>(
    `/api/v1/training/${trainingId}/cancel`,
    undefined,
    { headers: { Authorization: `Bearer ${token}` } }
  )
}

/**
 * Complete a training session, granting the stat increase to the dweller
 * @param trainingId - UUID of the training session to complete
 * @param token - Auth token
 * @returns Completed training session
 */
export async function completeTraining(trainingId: string, token: string): Promise<TrainingRead> {
  return await http.apiPost<TrainingRead>(
    `/api/v1/training/${trainingId}/complete`,
    undefined,
    { headers: { Authorization: `Bearer ${token}` } }
  )
}

/**
 * Get all active training sessions in a room
 * @param roomId - UUID of the room
 * @param token - Auth token
 * @returns List of active training sessions in the room
 */
export async function getRoomTrainings(roomId: string, token: string): Promise<TrainingRead[]> {
  return await http.apiGet<TrainingRead[]>(`/api/v1/training/room/${roomId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}
