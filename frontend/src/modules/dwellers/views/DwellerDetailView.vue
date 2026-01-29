<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDwellerStore } from '../stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExplorationStore } from '@/stores/exploration'
import { Icon } from '@iconify/vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import DwellerCard from '../components/cards/DwellerCard.vue'
import DwellerPanel from '../components/DwellerPanel.vue'
import TrainingStartModal from '../components/modals/TrainingStartModal.vue'
import DwellerStatusBadge from '../components/stats/DwellerStatusBadge.vue'
import UButton from '@/core/components/ui/UButton.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { RevivalSection } from '../components/death'
import type { RevivalCostResponse } from '../models/dweller'
import { useGaryMode } from '@/core/composables/useGaryMode'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const explorationStore = useExplorationStore()
const { isCollapsed } = useSidePanel()
const { triggerGaryMode } = useGaryMode()

const dwellerId = computed(() => route.params.dwellerId as string)
const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

const loading = ref(false)
const generatingAI = ref(false)
const generatingBio = ref(false)
const generatingPortrait = ref(false)
const generatingAppearance = ref(false)
const showTrainingModal = ref(false)

// Computed to check if any AI generation is in progress
const isAnyGenerating = computed(
  () =>
    generatingAI.value ||
    generatingBio.value ||
    generatingPortrait.value ||
    generatingAppearance.value
)

const dweller = computed(() => dwellerStore.detailedDwellers[dwellerId.value])
const revivalCost = ref<RevivalCostResponse | null>(null)
const revivalLoading = ref(false)
const isDead = computed(() => dweller.value?.is_dead === true)

onMounted(async () => {
  if (authStore.isAuthenticated && dwellerId.value) {
    loading.value = true
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string)
    loading.value = false

    // Fetch revival cost if dweller is dead
    if (dweller.value?.is_dead && !dweller.value?.is_permanently_dead) {
      revivalCost.value = await dwellerStore.getRevivalCost(
        dwellerId.value,
        authStore.token as string
      )
    }
  }
})

// Watch for changes in dweller's dead status to fetch/clear revival cost
watch(isDead, async (newIsDead) => {
  if (newIsDead && !dweller.value?.is_permanently_dead && authStore.isAuthenticated) {
    revivalCost.value = await dwellerStore.getRevivalCost(
      dwellerId.value,
      authStore.token as string
    )
  } else {
    revivalCost.value = null
  }
})

const goBack = () => {
  router.push(`/vault/${vaultId.value}/dwellers`)
}

const navigateToChatPage = () => {
  router.push(`/dweller/${dwellerId.value}/chat`)
}

const assigning = ref(false)

const handleAssign = async () => {
  if (!dweller.value || assigning.value) return

  assigning.value = true
  try {
    await dwellerStore.autoAssignToRoom(dwellerId.value, authStore.token as string)
    // Refresh dweller details to show updated room assignment
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
  } catch (error) {
    console.error('Error auto-assigning dweller:', error)
  } finally {
    assigning.value = false
  }
}

const handleRecall = async () => {
  if (!dweller.value || !authStore.token) return

  // Find the active exploration for this dweller
  const exploration = explorationStore.getExplorationByDwellerId(dwellerId.value)

  if (!exploration) {
    console.error('No active exploration found for dweller')
    return
  }

  try {
    await explorationStore.recallDweller(exploration.id, authStore.token)
    // Refresh dweller details to update status
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token, true)
  } catch (error) {
    console.error('Error recalling dweller:', error)
  }
}

const generateDwellerInfo = async () => {
  generatingAI.value = true
  try {
    const result = await dwellerStore.generateDwellerInfo(
      dwellerId.value,
      authStore.token as string
    )
    if (result) {
      // Force refresh the detailed dweller data
      await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
    }
  } catch (error) {
    console.error('Error generating info with AI:', error)
  } finally {
    generatingAI.value = false
  }
}

const generateDwellerBio = async () => {
  generatingBio.value = true
  try {
    const result = await dwellerStore.generateDwellerBio(dwellerId.value, authStore.token as string)
    if (result) {
      await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
    }
  } catch (error) {
    console.error('Error generating bio with AI:', error)
  } finally {
    generatingBio.value = false
  }
}

const generateDwellerPortrait = async () => {
  generatingPortrait.value = true
  try {
    const result = await dwellerStore.generateDwellerPortrait(
      dwellerId.value,
      authStore.token as string
    )
    if (result) {
      await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
    }
  } catch (error) {
    console.error('Error generating portrait with AI:', error)
  } finally {
    generatingPortrait.value = false
  }
}

const generateDwellerAppearance = async () => {
  generatingAppearance.value = true
  try {
    const result = await dwellerStore.generateDwellerAppearance(
      dwellerId.value,
      authStore.token as string
    )
    if (result) {
      await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
    }
  } catch (error) {
    console.error('Error generating appearance with AI:', error)
  } finally {
    generatingAppearance.value = false
  }
}

const handleRefresh = async () => {
  await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
}

const handleRevive = async () => {
  if (revivalLoading.value || !authStore.token) return

  revivalLoading.value = true
  try {
    const result = await dwellerStore.reviveDweller(dwellerId.value, authStore.token)
    // Only clear revival cost and refresh on successful revival
    if (result) {
      revivalCost.value = null
      await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token, true)
    }
  } finally {
    revivalLoading.value = false
  }
}

const usingStimpack = ref(false)
const usingRadaway = ref(false)
const unassigning = ref(false)
const isEditingName = ref(false)
const editedName = ref('')
const renamingInProgress = ref(false)

const handleUseStimpack = async () => {
  if (!dweller.value || usingStimpack.value) return

  usingStimpack.value = true
  try {
    await dwellerStore.useStimpack(dwellerId.value, authStore.token as string)
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
  } catch (error) {
    console.error('Error using stimpack:', error)
  } finally {
    usingStimpack.value = false
  }
}

const handleUseRadaway = async () => {
  if (!dweller.value || usingRadaway.value) return

  usingRadaway.value = true
  try {
    await dwellerStore.useRadaway(dwellerId.value, authStore.token as string)
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
  } catch (error) {
    console.error('Error using radaway:', error)
  } finally {
    usingRadaway.value = false
  }
}

const handleUnassign = async () => {
  if (!dweller.value || unassigning.value) return

  unassigning.value = true
  try {
    await dwellerStore.unassignDwellerFromRoom(dwellerId.value, authStore.token as string)
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
  } catch (error) {
    console.error('Error unassigning dweller:', error)
  } finally {
    unassigning.value = false
  }
}

const handleTrainingStarted = async () => {
  await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
}

const startEditingName = () => {
  if (!dweller.value) return
  editedName.value = dweller.value.first_name
  isEditingName.value = true
}

const cancelEditingName = () => {
  isEditingName.value = false
  editedName.value = ''
}

const saveNewName = async () => {
  if (!editedName.value.trim() || renamingInProgress.value) return

  renamingInProgress.value = true
  try {
    const result = await dwellerStore.renameDweller(
      dwellerId.value,
      editedName.value.trim(),
      authStore.token as string
    )
    if (result) {
      isEditingName.value = false
      editedName.value = ''
    }
  } finally {
    renamingInProgress.value = false
  }
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-8">
          <!-- Loading State -->
          <div v-if="loading" class="loading-container">
            <Icon icon="mdi:loading" class="loading-icon animate-spin" />
            <p class="loading-text">Loading dweller details...</p>
          </div>

          <!-- Error State -->
          <div v-else-if="!dweller" class="error-container">
            <Icon icon="mdi:alert-circle" class="error-icon" />
            <p class="error-text">Dweller not found</p>
            <UButton @click="goBack" variant="secondary">
              <Icon icon="mdi:arrow-left" class="mr-2" />
              Back to Dwellers
            </UButton>
          </div>

          <!-- Dweller Detail -->
          <div v-else class="dweller-detail">
            <!-- Header -->
            <div class="detail-header">
              <UButton @click="goBack" variant="ghost" size="sm">
                <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-2" />
                Back to Dwellers
              </UButton>

              <div class="header-info">
                <div class="name-section">
                  <h1
                    v-if="!isEditingName"
                    class="dweller-name cursor-pointer select-none"
                    @click="dweller.first_name?.toLowerCase() === 'gary' && triggerGaryMode()"
                  >
                    {{ dweller.first_name }} {{ dweller.last_name }}
                  </h1>
                  <div v-else class="name-edit-section">
                    <input
                      v-model="editedName"
                      type="text"
                      class="name-input"
                      placeholder="First name"
                      maxlength="20"
                      @keyup.enter="saveNewName"
                      @keyup.esc="cancelEditingName"
                      autofocus
                    />
                    <UButton
                      @click="saveNewName"
                      :disabled="!editedName.trim() || renamingInProgress"
                      variant="primary"
                      size="sm"
                    >
                      <Icon icon="mdi:check" class="h-4 w-4" />
                    </UButton>
                    <UButton @click="cancelEditingName" variant="ghost" size="sm">
                      <Icon icon="mdi:close" class="h-4 w-4" />
                    </UButton>
                  </div>
                  <UButton
                    v-if="!isEditingName && !isDead"
                    @click="startEditingName"
                    variant="ghost"
                    size="sm"
                    class="rename-btn"
                  >
                    <Icon icon="mdi:pencil" class="h-4 w-4" />
                  </UButton>
                </div>
                <DwellerStatusBadge :status="dweller.status" :show-label="true" size="large" />
              </div>
            </div>

            <!-- Two-Column Layout -->
            <div class="detail-layout">
              <!-- Left Column: Dweller Card -->
              <div class="space-y-6">
                <DwellerCard
                  :dweller="dweller"
                  :image-url="dweller.image_url"
                  :loading="generatingAI || usingStimpack || usingRadaway || assigning || unassigning"
                  @chat="navigateToChatPage"
                  @assign="handleAssign"
                  @unassign="handleUnassign"
                  @recall="handleRecall"
                  @use-stimpack="handleUseStimpack"
                  @use-radaway="handleUseRadaway"
                  @train="showTrainingModal = true"
                />

                <!-- Revival Section for Dead Dwellers -->
                <RevivalSection
                  v-if="isDead && !dweller.is_permanently_dead"
                  :dweller-id="dwellerId"
                  :revival-cost="revivalCost"
                  :loading="revivalLoading"
                  @revive="handleRevive"
                />

                <!-- Permanently Dead Notice -->
                <div
                  v-else-if="dweller.is_permanently_dead"
                  class="bg-gray-900 border border-red-500/30 rounded-lg p-4 text-center"
                >
                  <Icon icon="mdi:grave-stone" class="h-12 w-12 text-gray-500 mx-auto mb-3" />
                  <h3 class="text-lg font-bold text-red-500 mb-1">Permanently Deceased</h3>
                  <p class="text-gray-400 text-sm">
                    This dweller has passed beyond the revival window.
                  </p>
                  <p v-if="dweller.epitaph" class="text-theme-primary/60 italic mt-3 text-sm">
                    "{{ dweller.epitaph }}"
                  </p>
                </div>
              </div>

              <!-- Right Column: Dweller Panel -->
              <DwellerPanel
                :dweller="dweller"
                :generating-bio="generatingBio"
                :generating-appearance="generatingAppearance"
                :generating-portrait="generatingPortrait"
                :is-any-generating="isAnyGenerating"
                @refresh="handleRefresh"
                @generate-bio="generateDwellerBio"
                @generate-appearance="generateDwellerAppearance"
                @generate-portrait="generateDwellerPortrait"
                @generate-all="generateDwellerInfo"
              />
            </div>
          </div>

          <!-- Modals -->
          <TrainingStartModal
            v-if="dweller"
            v-model="showTrainingModal"
            :dweller="dweller"
            @started="handleTrainingStarted"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}

.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 50%, transparent 50%);
  background-size: 100% 2px;
  pointer-events: none;
}

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

.dweller-detail {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.detail-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.name-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.dweller-name {
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
  margin-bottom: 1rem;
  letter-spacing: -0.5px;
}

.name-edit-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.name-input {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.25rem;
  padding: 0.5rem 1rem;
  font-family: 'Courier New', monospace;
  outline: none;
  transition: all 0.2s;
}

.name-input:focus {
  box-shadow: 0 0 15px var(--color-theme-glow);
  border-color: var(--color-theme-accent);
}

.rename-btn {
  opacity: 0.6;
  transition: opacity 0.2s;
}

.rename-btn:hover {
  opacity: 1;
}

.detail-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 2rem;
  align-items: start;
}

@media (max-width: 1024px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
