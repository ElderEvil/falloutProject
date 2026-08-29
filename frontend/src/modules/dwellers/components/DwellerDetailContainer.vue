<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDwellerStore } from '../stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { Icon } from '@iconify/vue'
import BackButton from '@/core/components/common/BackButton.vue'
import { UButton, UInput, UModal } from '@/core/components/ui'
import DwellerDetailPane from '../components/DwellerDetailPane.vue'
import DwellerAppearanceEditor from '../components/DwellerAppearanceEditor.vue'
import TrainingStartModal from '../components/modals/TrainingStartModal.vue'
import ExplorationDurationModal from '@/modules/exploration/components/ExplorationDurationModal.vue'
import { useSendToWasteland } from '@/modules/exploration/composables/useSendToWasteland'
import { useGaryMode } from '@/core/composables/useGaryMode'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { getVaultMap } from '@/modules/map/services/mapService'
import { useDwellerDetailActions } from '../composables/useDwellerDetail'
import type { MapPlaceLink } from '../components/DwellerBio.vue'
import type { RevivalCostResponse } from '../models/dweller'

const props = defineProps<{ embedded?: boolean }>()

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

// Standalone route uses :dwellerId; the desktop master-detail uses ?selected.
const dwellerId = computed<string>(() => {
  const fromParam = route.params.dwellerId
  if (typeof fromParam === 'string') return fromParam
  if (Array.isArray(fromParam) && typeof fromParam[0] === 'string') return fromParam[0]
  const fromQuery = route.query.selected
  if (typeof fromQuery === 'string') return fromQuery
  if (Array.isArray(fromQuery) && typeof fromQuery[0] === 'string') return fromQuery[0]
  return ''
})
const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

const loading = ref(false)
let loadSeq = 0
const generatingAI = ref(false)
const generatingBio = ref(false)
const generatingPortrait = ref(false)
const generatingAppearance = ref(false)
const showTrainingModal = ref(false)
const showAppearanceEditor = ref(false)

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

const { refetch, runAction } = useDwellerDetailActions(dwellerId, vaultId)

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
      .map((loc) => ({ name: loc.name, locationId: loc.id }))
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

const onBack = () => {
  if (props.embedded) {
    // Deselect in the master-detail list instead of leaving the page
    router.replace({ query: { ...route.query, selected: undefined } })
  } else {
    router.push(`/vault/${vaultId.value}/dwellers`)
  }
}

const navigateToChatPage = () => router.push(`/dweller/${dwellerId.value}/chat`)

const navigateToDweller = (id: string) => router.push(`/vault/${vaultId.value}/dwellers/${id}`)

const onHeaderNameClick = () => {
  if (dweller.value?.first_name?.toLowerCase() === 'gary') triggerGaryMode()
}

const assigning = ref(false)
const unassigning = ref(false)
const usingStimpack = ref(false)
const usingRadaway = ref(false)
const issuingMedicalSupply = ref(false)

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

const sendWasteland = useSendToWasteland(() => vaultId.value)

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

watch(dwellerId, () => {
  sendWasteland.cancel()
  void loadDweller()
})

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
    showAppearanceEditor.value = false
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

const handleUseStimpack = () =>
  runAction(() => dwellerMedicalStore.useStimpack(dwellerId.value, authStore.token as string), {
    flag: usingStimpack,
    errorMessage: 'Failed to use Stimpak',
  })

const handleUseRadaway = () =>
  runAction(() => dwellerMedicalStore.useRadaway(dwellerId.value, authStore.token as string), {
    flag: usingRadaway,
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

const showRenameDialog = ref(false)
const renameDialogName = ref('')

const openRenameDialog = () => {
  renameDialogName.value = dweller.value?.first_name ?? ''
  showRenameDialog.value = true
}

const confirmRename = () => {
  const name = renameDialogName.value.trim()
  if (!name) return
  showRenameDialog.value = false
  void handleRename(name)
}

const handleTrainingStarted = () => refetch()
</script>

<template>
  <div>
    <div v-if="loading" class="loading-container">
      <Icon icon="mdi:loading" class="loading-icon animate-spin" />
      <p class="loading-text">Loading dweller details...</p>
    </div>

    <div v-else-if="!dweller" class="error-container">
      <Icon icon="mdi:alert-circle" class="error-icon" />
      <p class="error-text">Dweller not found</p>
      <BackButton label="Back to Dwellers" @click="onBack" />
    </div>

    <DwellerDetailPane
      v-else
      :dweller="dweller"
      :vault-id="vaultId"
      :place-links="placeLinks"
      :initial-tab="queryTab"
      :highlight-stat="queryStat"
      :generating-bio="generatingBio"
      :generating-appearance="generatingAppearance"
      :generating-portrait="generatingPortrait"
      :generating-a-i="generatingAI"
      :using-stimpack="usingStimpack"
      :using-radaway="usingRadaway"
      :issuing-medical-supply="issuingMedicalSupply"
      :assigning="assigning"
      :unassigning="unassigning"
      :revival-loading="revivalLoading"
      :revival-cost="revivalCost"
      :available-stimpaks="currentVault?.stimpack"
      :available-radaways="currentVault?.radaway"
      @back="onBack"
      @rename="openRenameDialog"
      @chat="navigateToChatPage"
      @assign="handleAssign"
      @unassign="handleUnassign"
      @recall="handleRecall"
      @use-stimpack="handleUseStimpack"
      @use-radaway="handleUseRadaway"
      @train="showTrainingModal = true"
      @send-wasteland="handleSendWasteland"
      @generate-portrait="generateDwellerPortrait"
      @issue-medical-supply="handleIssueMedicalSupply"
      @refresh="handleRefresh"
      @generate-bio="generateDwellerBio"
      @generate-appearance="generateDwellerAppearance"
      @generate-all="generateDwellerInfo"
      @edit-appearance="showAppearanceEditor = true"
      @navigate-dweller="navigateToDweller"
      @revive="handleRevive"
      @header-name-click="onHeaderNameClick"
    />

    <DwellerAppearanceEditor
      v-if="dweller"
      v-model="showAppearanceEditor"
      :dweller="dweller"
      @saved="handleAppearanceSaved"
    />
    <TrainingStartModal
      v-if="dweller"
      v-model="showTrainingModal"
      :dweller="dweller"
      @started="handleTrainingStarted"
    />
    <ExplorationDurationModal
      v-if="dweller"
      :show="sendWasteland.showModal.value"
      :dweller-name="`${sendWasteland.pendingDweller.value?.firstName ?? ''} ${sendWasteland.pendingDweller.value?.lastName ?? ''}`"
      :max-stimpaks="currentVault?.stimpack ?? 0"
      :max-radaways="currentVault?.radaway ?? 0"
      @confirm="handleSendWastelandConfirm"
      @cancel="sendWasteland.cancel"
    />

    <UModal v-model="showRenameDialog" title="Rename Dweller" size="sm">
      <UInput
        v-model="renameDialogName"
        label="First name"
        placeholder="Dweller name"
      />
      <template #footer>
        <UButton variant="secondary" @click="showRenameDialog = false">Cancel</UButton>
        <UButton variant="primary" :disabled="!renameDialogName.trim()" @click="confirmRename">
          Save
        </UButton>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  min-height: 400px;
}

.loading-icon,
.error-icon {
  width: 4rem;
  height: 4rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 10px var(--color-theme-glow));
}

.loading-text,
.error-text {
  font-size: 1.25rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}
</style>
