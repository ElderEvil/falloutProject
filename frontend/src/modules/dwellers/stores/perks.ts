import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { handleStoreError } from '@/core/utils/errorHandler'
import {
  getDwellerPerks,
  selectDwellerPerk,
  type DwellerPerks,
  type DwellerPerk,
} from '../services/dwellerService'

export const useDwellerPerksStore = defineStore('dwellerPerks', () => {
  const auth = useAuthStore()
  const toast = useToast()
  const data = ref<DwellerPerks | null>(null)
  const loading = ref(false)
  const selecting = ref(false)
  const error = ref<string | null>(null)
  let sequence = 0
  let dwellerId = ''

  function clear() {
    sequence++
    dwellerId = ''
    data.value = null
    loading.value = selecting.value = false
    error.value = null
  }

  watch(() => auth.token, clear, { flush: 'sync' })

  async function load(vaultId: string, id: string) {
    clear()
    if (!auth.token || !vaultId || !id) return
    const token = auth.token
    const version = sequence
    dwellerId = id
    loading.value = true
    try {
      const result = await getDwellerPerks(id, token)
      if (version === sequence) data.value = result
    } catch (caught) {
      if (version === sequence) {
        error.value = 'Could not load explorer perks.'
        handleStoreError(caught, error.value)
      }
    } finally {
      if (version === sequence) loading.value = false
    }
  }

  async function choose(perk: DwellerPerk) {
    if (!auth.token || !dwellerId || selecting.value || loading.value) return
    const version = sequence
    selecting.value = true
    error.value = null
    try {
      const result = await selectDwellerPerk(dwellerId, perk, auth.token)
      if (version !== sequence) return
      data.value = result
      const selected = result.options.find((option) => option.id === result.selected_perk)
      toast.success(`Explorer perk learned: ${selected?.name ?? perk}`)
    } catch (caught) {
      if (version === sequence) {
        error.value = 'Could not choose this perk. Refresh to check current eligibility.'
        handleStoreError(caught, error.value)
      }
    } finally {
      if (version === sequence) selecting.value = false
    }
  }

  return { data, loading, selecting, error, load, choose, clear }
})
