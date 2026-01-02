import axios from '@/plugins/axios'
import type { components } from '@/types/api.generated'

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
  const response = await axios.post(
    '/api/v1/training/start',
    null,
    {
      params: { dweller_id: dwellerId, room_id: roomId },
      headers: { Authorization: `Bearer ${token}` }
    }
  )
  return response.data
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
  const response = await axios.get(
    `/api/v1/training/dweller/${dwellerId}`,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  )
  return response.data
}

/**
 * Get all active training sessions in a vault
 * @param vaultId - UUID of the vault
 * @param token - Auth token
 * @returns List of active training sessions
 */
export async function getVaultTrainings(
  vaultId: string,
  token: string
): Promise<TrainingRead[]> {
  const response = await axios.get(
    `/api/v1/training/vault/${vaultId}`,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  )
  return response.data
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
  const response = await axios.get(
    `/api/v1/training/${trainingId}`,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  )
  return response.data
}

/**
 * Cancel an active training session
 * @param trainingId - UUID of the training session
 * @param token - Auth token
 * @returns Cancelled training session
 */
export async function cancelTraining(
  trainingId: string,
  token: string
): Promise<TrainingRead> {
  const response = await axios.post(
    `/api/v1/training/${trainingId}/cancel`,
    null,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  )
  return response.data
}

/**
 * Get all active training sessions in a room
 * @param roomId - UUID of the room
 * @param token - Auth token
 * @returns List of active training sessions in the room
 */
export async function getRoomTrainings(
  roomId: string,
  token: string
): Promise<TrainingRead[]> {
  const response = await axios.get(
    `/api/v1/training/room/${roomId}`,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  )
  return response.data
}
