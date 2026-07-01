import { ref, type Ref } from 'vue'
import type {
  ActionSuggestion,
  ChatMessageDisplay,
  StartExplorationAction,
  RecallExplorationAction,
} from '../models/chat'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { startTraining } from '@/modules/progression/services/trainingService'
import { useToast } from '@/core/composables/useToast'
import { useAuthStore } from '@/modules/auth/stores/auth'

export interface UseChatActionsOptions {
  dwellerId: string
  dwellerName: string
  messages: Ref<ChatMessageDisplay[]>
}

export function useChatActions(options: UseChatActionsOptions) {
  const authStore = useAuthStore()
  const dwellerStore = useDwellerStore()
  const vaultStore = useVaultStore()
  const roomStore = useRoomStore()
  const explorationStore = useExplorationStore()
  const toast = useToast()

  const isPerformingAction = ref(false)
  const showStatSelector = ref(false)
  const pendingTrainingAction = ref<{ stat: string; reason: string } | null>(null)

  const handleAssignToRoom = async (roomId: string, roomName: string): Promise<boolean> => {
    if (!authStore.token) return false

    isPerformingAction.value = true
    try {
      await dwellerStore.assignDwellerToRoom(options.dwellerId, roomId, authStore.token)
      toast.success(`${options.dwellerName} assigned to ${roomName}`)
      return true
    } catch (error) {
      console.error('Failed to assign dweller to room:', error)
      toast.error('Failed to assign dweller to room')
      return false
    } finally {
      isPerformingAction.value = false
    }
  }

  const handleStartTraining = async (stat: string): Promise<boolean> => {
    if (!authStore.token) return false

    isPerformingAction.value = true
    try {
      const dweller = dwellerStore.dwellers.find((d) => d.id === options.dwellerId)
      if (!dweller) {
        toast.error('Dweller not found')
        return false
      }

      const vaultId = vaultStore.activeVaultId
      if (!vaultId) {
        toast.error('Unable to access vault data')
        return false
      }

      if (roomStore.rooms.length === 0) {
        await roomStore.fetchRooms(vaultId, authStore.token)
      }

      let trainingRoomId = dweller.room_id
      const currentRoom = roomStore.rooms.find((r) => r.id === dweller.room_id)

      if (!currentRoom || currentRoom.category !== 'training') {
        const trainingRooms = roomStore.rooms.filter((r) => r.category === 'training')

        if (trainingRooms.length === 0) {
          toast.error('No training rooms available')
          return false
        }

        const matchingStatRooms = trainingRooms.filter(
          (r) => r.ability?.toLowerCase() === stat.toLowerCase()
        )
        let availableTrainingRoom = matchingStatRooms.find((r) => {
          const occupancy = dwellerStore.dwellers.filter((d) => d.room_id === r.id).length
          return !r.max_capacity || occupancy < r.max_capacity
        })
        if (!availableTrainingRoom) {
          availableTrainingRoom = trainingRooms.find((r) => {
            const occupancy = dwellerStore.dwellers.filter((d) => d.room_id === r.id).length
            return !r.max_capacity || occupancy < r.max_capacity
          })
        }

        if (!availableTrainingRoom) {
          toast.error('No available training rooms (all at capacity)')
          return false
        }

        toast.info(`Moving ${options.dwellerName} to training room...`)
        await dwellerStore.assignDwellerToRoom(
          options.dwellerId,
          availableTrainingRoom.id,
          authStore.token
        )
        trainingRoomId = availableTrainingRoom.id
      }

      await startTraining(options.dwellerId, trainingRoomId, authStore.token)
      toast.success(`${options.dwellerName} started ${stat} training`)
      return true
    } catch (error) {
      console.error('Failed to start training:', error)
      toast.error('Failed to start training')
      return false
    } finally {
      isPerformingAction.value = false
      showStatSelector.value = false
      pendingTrainingAction.value = null
    }
  }

  const handleStartExploration = async (action: StartExplorationAction): Promise<boolean> => {
    if (!authStore.token) return false

    const vaultId = vaultStore.activeVaultId
    if (!vaultId) {
      toast.error('No vault selected')
      return false
    }

    isPerformingAction.value = true
    try {
      const dweller = dwellerStore.dwellers.find((d) => d.id === options.dwellerId)
      if (!dweller) {
        toast.error('Dweller not found')
        return false
      }

      if (dweller.room_id) {
        await dwellerStore.unassignDwellerFromRoom(options.dwellerId, authStore.token)
      }

      toast.info(`Sending ${options.dwellerName} to wasteland...`)
      await explorationStore.sendDwellerToWasteland(
        vaultId,
        options.dwellerId,
        action.duration_hours,
        authStore.token,
        action.stimpaks,
        action.radaways
      )
      toast.success(`${options.dwellerName} sent to the wasteland!`)

      await dwellerStore.fetchDwellerDetails(options.dwellerId, authStore.token, true)
      return true
    } catch (error) {
      console.error('Failed to start exploration:', error)
      toast.error('Failed to send dweller to wasteland')
      return false
    } finally {
      isPerformingAction.value = false
    }
  }

  const handleRecallExploration = async (action: RecallExplorationAction): Promise<boolean> => {
    if (!authStore.token) return false

    isPerformingAction.value = true
    try {
      const progress = await explorationStore.fetchExplorationProgress(
        action.exploration_id,
        authStore.token
      )

      if (
        progress &&
        typeof progress.progress_percentage === 'number' &&
        progress.progress_percentage >= 100
      ) {
        toast.info(`Completing ${options.dwellerName}'s exploration...`)
        await explorationStore.completeExploration(action.exploration_id, authStore.token)
        toast.success(`${options.dwellerName}'s exploration completed!`)
      } else {
        toast.info(`Recalling ${options.dwellerName} from wasteland...`)
        await explorationStore.recallDweller(action.exploration_id, authStore.token)
        toast.success(`${options.dwellerName} recalled from wasteland!`)
      }

      await dwellerStore.fetchDwellerDetails(options.dwellerId, authStore.token, true)
      return true
    } catch (error) {
      console.error('Failed to recall exploration:', error)
      toast.error('Failed to recall dweller from wasteland')
      return false
    } finally {
      isPerformingAction.value = false
    }
  }

  const handleActionConfirm = async (action: ActionSuggestion, messageIndex: number) => {
    if (!action) return

    let success = false

    if (action.action_type === 'assign_to_room') {
      success = await handleAssignToRoom(action.room_id, action.room_name)
    } else if (action.action_type === 'start_training') {
      pendingTrainingAction.value = { stat: action.stat, reason: action.reason }
      success = await handleStartTraining(action.stat)
    } else if (action.action_type === 'start_exploration') {
      success = await handleStartExploration(action)
    } else if (action.action_type === 'recall_exploration') {
      success = await handleRecallExploration(action)
    }

    if (success && options.messages.value[messageIndex]) {
      options.messages.value[messageIndex].actionSuggestion = null
    }
  }

  return {
    isPerformingAction,
    showStatSelector,
    pendingTrainingAction,
    handleActionConfirm,
  }
}
