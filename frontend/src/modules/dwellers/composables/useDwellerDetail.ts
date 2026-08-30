import { computed, onMounted, readonly, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '../stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useToast } from '@/core/composables/useToast'
import { useSendToWasteland } from '@/modules/exploration/composables/useSendToWasteland'
import { useGaryMode } from '@/core/composables/useGaryMode'
import { handleStoreError } from '@/core/utils/errorHandler'
import { getVaultMap } from '@/modules/map/services/mapService'
import type { Dweller, MapPlaceLink, RevivalCostResponse } from '../models/dweller'

export interface DwellerDetailActions {
  assign(): void
  unassign(): void
  recall(): void
  openSendToWasteland(): void
  confirmSendToWasteland(payload: { duration: number; stimpaks: number; radaways: number }): Promise<boolean>
  cancelSendToWasteland(): void
  useStimpak(): void
  useRadAway(): void
  issueMedicalSupply(supply: 'stimpack' | 'radaway'): void
  rename(name: string): void
  confirmRename(): void
  openRenameDialog(): void
  openSoftDeleteDialog(): void
  confirmSoftDelete(): void
  revive(): void
  generateBio(): void
  generatePortrait(): void
  generateAppearance(): void
  generateAll(): void
  editAppearance(): void
  saveAppearance(attributes: Record<string, unknown>): Promise<void>
  onTrainingStarted(): void
  refresh(): void
  onBack(): void
  navigateToChat(): void
  navigateToDweller(id: string): void
  onHeaderNameClick(): void
}

export interface UseDwellerDetailReturn {
  // state (exposed readonly to consumers)
  dweller: Readonly<Ref<Dweller | null | undefined>>
  loading: Readonly<Ref<boolean>>
  placeLinks: Readonly<Ref<MapPlaceLink[]>>
  revivalCost: Readonly<Ref<RevivalCostResponse | null>>
  revivalLoading: Readonly<Ref<boolean>>
  generatingBio: Readonly<Ref<boolean>>
  generatingAppearance: Readonly<Ref<boolean>>
  generatingPortrait: Readonly<Ref<boolean>>
  generatingAI: Readonly<Ref<boolean>>
  usingStimpak: Readonly<Ref<boolean>>
  usingRadAway: Readonly<Ref<boolean>>
  issuingMedicalSupply: Readonly<Ref<boolean>>
  assigning: Readonly<Ref<boolean>>
  unassigning: Readonly<Ref<boolean>>
  isAnyGenerating: Readonly<Ref<boolean>>
  cardLoading: Readonly<Ref<boolean>>
  availableStimpaks: Readonly<Ref<number | undefined>>
  availableRadaways: Readonly<Ref<number | undefined>>
  vaultId: Ref<string>
  dwellerId: Ref<string>
  initialTab: Readonly<Ref<string | undefined>>
  highlightStat: Readonly<Ref<string | undefined>>
  // async-modal flags (writable so the thin container template binds v-model)
  appearanceEditorOpen: Ref<boolean>
  trainingModalOpen: Ref<boolean>
  renameDialogOpen: Ref<boolean>
  renameDialogName: Ref<string>
  softDeleteDialogOpen: Ref<boolean>
  wastelandModalOpen: Ref<boolean>
  wastelandPendingDweller: Readonly<Ref<{ firstName: string; lastName?: string } | null>>
  actions: DwellerDetailActions
}

interface RunOptions {
  flag?: Ref<boolean>
  errorMessage?: string
  refreshVault?: boolean
  onSuccess?: () => void
}

/**
 * Single orchestration composable for the dweller detail page. Owns data loading,
 * modal orchestration, and action wiring that previously lived in the god-container,
 * exposing a provideable context so descendants inject instead of prop-drill.
 */
export function useDwellerDetail(dwellerId: Ref<string>, vaultId: Ref<string>): UseDwellerDetailReturn {
  const route = useRoute()
  const router = useRouter()
  const authStore = useAuthStore()
  const {
    filter: dwellerStore,
    generation: dwellerGenerationStore,
    management: dwellerManagementStore,
    medical: dwellerMedicalStore,
    death: dwellerDeathStore,
  } = useDwellerStore()
  const vaultStore = useVaultStore()
  const explorationStore = useExplorationStore()
  const toast = useToast()
  const { triggerGaryMode } = useGaryMode()

  const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

  const loading = ref(false)
  let loadSeq = 0
  const generatingAI = ref(false)
  const generatingBio = ref(false)
  const generatingPortrait = ref(false)
  const generatingAppearance = ref(false)
  const appearanceEditorOpen = ref(false)
  const trainingModalOpen = ref(false)
  const renameDialogOpen = ref(false)
  const renameDialogName = ref('')
  const softDeleteDialogOpen = ref(false)
  const softDeleting = ref(false)

  const dweller = computed(() => dwellerStore.detailedDwellers[dwellerId.value])
  const revivalCost = ref<RevivalCostResponse | null>(null)
  const revivalLoading = ref(false)
  const isDead = computed(() => dweller.value?.is_dead === true)
  const placeLinks = ref<MapPlaceLink[]>([])

  const queryTab = computed(() => {
    const tab = route.query.tab
    return typeof tab === 'string' ? tab : undefined
  })
  const queryStat = computed(() => {
    const stat = route.query.stat
    return typeof stat === 'string' ? stat.toLowerCase() : undefined
  })

  const assigning = ref(false)
  const unassigning = ref(false)
  const usingStimpak = ref(false)
  const usingRadAway = ref(false)
  const issuingMedicalSupply = ref(false)

  const sendWasteland = useSendToWasteland(() => vaultId.value)

  const isAnyGenerating = computed(
    () => generatingBio.value || generatingAppearance.value || generatingAI.value || generatingPortrait.value
  )
  const cardLoading = computed(
    () =>
      generatingAI.value ||
      usingStimpak.value ||
      usingRadAway.value ||
      issuingMedicalSupply.value ||
      assigning.value ||
      unassigning.value
  )
  const availableStimpaks = computed(() => currentVault.value?.stimpack)
  const availableRadaways = computed(() => currentVault.value?.radaway)

  const refetch = () => dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)

  const runAction = async (action: () => Promise<unknown>, opts: RunOptions = {}) => {
    if (!dwellerStore.detailedDwellers[dwellerId.value] || opts.flag?.value) return
    if (opts.flag) opts.flag.value = true
    try {
      await action()
      await refetch()
      if (opts.refreshVault) await vaultStore.refreshVault(vaultId.value, authStore.token as string)
      opts.onSuccess?.()
    } catch {
      toast.error(opts.errorMessage ?? 'Action failed')
    } finally {
      if (opts.flag) opts.flag.value = false
    }
  }

  async function loadDweller() {
    if (!authStore.isAuthenticated || !dwellerId.value) return
    const requestedId = dwellerId.value
    const seq = ++loadSeq
    loading.value = true
    const fetched = await dwellerStore.fetchDwellerDetails(requestedId, authStore.token as string)
    if (seq !== loadSeq) return
    loading.value = false

    if (fetched?.is_dead && !fetched.is_permanently_dead) {
      revivalCost.value = await dwellerDeathStore.getRevivalCost(requestedId, authStore.token as string)
    }

    try {
      const mapData = await getVaultMap(authStore.token as string, vaultId.value)
      if (seq !== loadSeq) return
      placeLinks.value = mapData.locations
        .filter((loc) => loc.dwellers?.some((d) => d.dweller_id === requestedId))
        .map((loc): MapPlaceLink => ({ name: loc.name, locationId: loc.id }))
    } catch (error) {
      if (seq !== loadSeq) return
      handleStoreError(error, 'Failed to load vault map for bio place links')
    }
  }

  onMounted(loadDweller)

  watch(isDead, async (newIsDead) => {
    if (newIsDead && !dweller.value?.is_permanently_dead && authStore.isAuthenticated) {
      revivalCost.value = await dwellerDeathStore.getRevivalCost(dwellerId.value, authStore.token as string)
    } else {
      revivalCost.value = null
    }
  })

  watch(dwellerId, () => {
    sendWasteland.cancel()
    void loadDweller()
  })

  const onBack = () => router.push(`/vault/${vaultId.value}/dwellers`)
  const navigateToChat = () => router.push(`/dweller/${dwellerId.value}/chat`)
  const navigateToDweller = (id: string) => router.push(`/vault/${vaultId.value}/dwellers/${id}`)
  const onHeaderNameClick = () => {
    if (dweller.value?.first_name?.toLowerCase() === 'gary') triggerGaryMode()
  }

  const handleAssign = () =>
    runAction(() => dwellerManagementStore.autoAssignToRoom(dwellerId.value, authStore.token as string), {
      flag: assigning,
      errorMessage: 'Failed to assign dweller automatically',
    })
  const handleUnassign = () =>
    runAction(() => dwellerManagementStore.unassignDwellerFromRoom(dwellerId.value, authStore.token as string), {
      flag: unassigning,
      errorMessage: 'Failed to unassign dweller from room',
    })
  const handleRecall = async () => {
    if (!dweller.value || !authStore.token) return
    const exploration = explorationStore.getExplorationByDwellerId(dwellerId.value)
    if (!exploration) {
      toast.error('No active exploration found for this dweller')
      return
    }
    await runAction(() => explorationStore.recallDweller(exploration.id, authStore.token as string), {
      errorMessage: 'Failed to recall dweller',
    })
  }
  const handleSendWasteland = () => {
    if (!dweller.value) return
    sendWasteland.open({
      dwellerId: dwellerId.value,
      firstName: dweller.value.first_name,
      lastName: dweller.value.last_name ?? undefined,
    })
  }
  const handleSendWastelandConfirm = (payload: { duration: number; stimpaks: number; radaways: number }) => {
    const pendingDwellerId = sendWasteland.pendingDweller.value?.dwellerId
    if (!pendingDwellerId) return Promise.resolve(false)
    return sendWasteland.confirm(payload, async () => {
      await Promise.all([
        dwellerStore.fetchDwellerDetails(pendingDwellerId, authStore.token as string, true),
        vaultStore.refreshVault(vaultId.value, authStore.token as string),
      ])
    })
  }

  const generateDwellerInfo = () =>
    runAction(() => dwellerGenerationStore.generateDwellerInfo(dwellerId.value, authStore.token as string), {
      flag: generatingAI,
      errorMessage: 'Failed to generate dweller information',
    })
  const generateDwellerBio = () =>
    runAction(() => dwellerGenerationStore.generateDwellerBio(dwellerId.value, authStore.token as string), {
      flag: generatingBio,
      errorMessage: 'Failed to generate dweller biography',
    })
  const generateDwellerPortrait = () =>
    runAction(() => dwellerGenerationStore.generateDwellerPortrait(dwellerId.value, authStore.token as string), {
      flag: generatingPortrait,
      errorMessage: 'Failed to generate dweller portrait',
    })
  const generateDwellerAppearance = () =>
    runAction(() => dwellerGenerationStore.generateDwellerAppearance(dwellerId.value, authStore.token as string), {
      flag: generatingAppearance,
      errorMessage: 'Failed to generate dweller appearance',
    })
  const handleRefresh = () => refetch()

  const handleAppearanceSaved = async (attributes: Record<string, unknown>) => {
    if (!dweller.value) return
    const result = await dwellerManagementStore.updateVisualAttributes(
      dwellerId.value,
      attributes,
      authStore.token as string
    )
    if (result) {
      appearanceEditorOpen.value = false
      await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
    }
  }

  const handleRevive = () =>
    runAction(() => dwellerDeathStore.reviveDweller(dwellerId.value, authStore.token as string), {
      flag: revivalLoading,
      errorMessage: 'Failed to revive dweller',
      onSuccess: () => {
        revivalCost.value = null
      },
    })

  const handleUseStimpak = () =>
    runAction(() => dwellerMedicalStore.useStimpack(dwellerId.value, authStore.token as string), {
      flag: usingStimpak,
      errorMessage: 'Failed to use Stimpak',
    })
  const handleUseRadAway = () =>
    runAction(() => dwellerMedicalStore.useRadaway(dwellerId.value, authStore.token as string), {
      flag: usingRadAway,
      errorMessage: 'Failed to use RadAway',
    })
  const handleIssueMedicalSupply = (supply: 'stimpack' | 'radaway') =>
    runAction(
      () => dwellerMedicalStore.issueMedicalSupply(vaultId.value, dwellerId.value, supply, authStore.token as string),
      { flag: issuingMedicalSupply, errorMessage: 'Failed to issue medical supply', refreshVault: true }
    )

  const handleRename = (name: string) =>
    runAction(() => dwellerManagementStore.renameDweller(dwellerId.value, name, authStore.token as string), {
      errorMessage: 'Failed to rename dweller',
    })

  const openRenameDialog = () => {
    renameDialogName.value = dweller.value?.first_name ?? ''
    renameDialogOpen.value = true
  }
  const confirmRename = () => {
    const name = renameDialogName.value.trim()
    if (!name) return
    renameDialogOpen.value = false
    void handleRename(name)
  }

  const openSoftDeleteDialog = () => {
    softDeleteDialogOpen.value = true
  }
  const confirmSoftDelete = async () => {
    softDeleteDialogOpen.value = false
    await runAction(() => dwellerManagementStore.softDeleteDweller(dwellerId.value, authStore.token as string), {
      flag: softDeleting,
      errorMessage: 'Failed to soft-delete dweller',
      onSuccess: onBack,
    })
  }

  const actions: DwellerDetailActions = {
    assign: handleAssign,
    unassign: handleUnassign,
    recall: handleRecall,
    openSendToWasteland: handleSendWasteland,
    confirmSendToWasteland: handleSendWastelandConfirm,
    cancelSendToWasteland: () => sendWasteland.cancel(),
    useStimpak: handleUseStimpak,
    useRadAway: handleUseRadAway,
    issueMedicalSupply: handleIssueMedicalSupply,
    rename: handleRename,
    confirmRename,
    openRenameDialog,
    openSoftDeleteDialog,
    confirmSoftDelete,
    revive: handleRevive,
    generateBio: generateDwellerBio,
    generatePortrait: generateDwellerPortrait,
    generateAppearance: generateDwellerAppearance,
    generateAll: generateDwellerInfo,
    editAppearance: () => (appearanceEditorOpen.value = true),
    saveAppearance: handleAppearanceSaved,
    onTrainingStarted: handleRefresh,
    refresh: handleRefresh,
    onBack,
    navigateToChat,
    navigateToDweller,
    onHeaderNameClick,
  }

  return {
    dweller: dweller,
    loading: readonly(loading),
    placeLinks: placeLinks,
    revivalCost: readonly(revivalCost),
    revivalLoading: readonly(revivalLoading),
    generatingBio: readonly(generatingBio),
    generatingAppearance: readonly(generatingAppearance),
    generatingPortrait: readonly(generatingPortrait),
    generatingAI: readonly(generatingAI),
    usingStimpak: readonly(usingStimpak),
    usingRadAway: readonly(usingRadAway),
    issuingMedicalSupply: readonly(issuingMedicalSupply),
    assigning: readonly(assigning),
    unassigning: readonly(unassigning),
    isAnyGenerating: readonly(isAnyGenerating),
    cardLoading: readonly(cardLoading),
    availableStimpaks: readonly(availableStimpaks),
    availableRadaways: readonly(availableRadaways),
    vaultId,
    dwellerId,
    initialTab: readonly(queryTab),
    highlightStat: readonly(queryStat),
    appearanceEditorOpen,
    trainingModalOpen,
    renameDialogOpen,
    renameDialogName,
    softDeleteDialogOpen,
    wastelandModalOpen: sendWasteland.showModal,
    wastelandPendingDweller: readonly(sendWasteland.pendingDweller),
    actions,
  }
}
