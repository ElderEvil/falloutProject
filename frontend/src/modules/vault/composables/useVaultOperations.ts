import { ref } from 'vue'
import { useVaultStore } from '../stores/vault'
import { useRoomStore } from '@/stores/room'
import { useRouter } from 'vue-router'

export function useVaultOperations() {
  const vaultStore = useVaultStore()
  const roomStore = useRoomStore()
  const router = useRouter()
  const selectedVaultId = ref<string | null>(null)

  const fetchVaults = async (token: string) => {
    await vaultStore.fetchVaults(token)
  }

  const createVault = async (number: number, token: string) => {
    await vaultStore.createVault(number, token)
    await fetchVaults(token)
  }

  const deleteVault = async (id: string, token: string) => {
    await vaultStore.deleteVault(id, token)
    if (selectedVaultId.value === id) {
      selectedVaultId.value = null
    }
    await fetchVaults(token)
  }

  const selectVault = (id: string) => {
    selectedVaultId.value = id
  }

  const loadVault = async (id: string, token: string) => {
    vaultStore.selectedVaultId = id
    await roomStore.fetchRooms(id, token)
    await router.push('/vault')
  }

  return {
    fetchVaults,
    createVault,
    deleteVault,
    selectVault,
    loadVault,
    selectedVaultId,
  }
}
