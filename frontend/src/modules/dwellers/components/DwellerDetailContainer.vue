<script setup lang="ts">
import { computed, defineAsyncComponent, provide } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import BackButton from '@/core/components/common/BackButton.vue'
import { UButton, UInput, UModal } from '@/core/components/ui'
import DwellerDetailPane from './DwellerDetailPane.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import { useDwellerDetail } from '../composables/useDwellerDetail'
import { dwellerDetailKey } from './DwellerDetailContext'

const DwellerAppearanceEditor = defineAsyncComponent({
  loader: () => import('./DwellerAppearanceEditor.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})
const TrainingStartModal = defineAsyncComponent({
  loader: () => import('./modals/TrainingStartModal.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})
const ExplorationDurationModal = defineAsyncComponent({
  loader: () => import('@/modules/exploration/components/ExplorationDurationModal.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})

const route = useRoute()

// The full-page detail route carries the dweller id as :dwellerId.
const dwellerId = computed<string>(() => {
  const fromParam = route.params.dwellerId
  if (typeof fromParam === 'string') return fromParam
  if (Array.isArray(fromParam) && typeof fromParam[0] === 'string') return fromParam[0]
  return ''
})
const vaultId = computed(() => route.params.id as string)

const ctx = useDwellerDetail(dwellerId, vaultId)
provide(dwellerDetailKey, ctx)

const dweller = computed(() => ctx.dweller.value)
// Local refs aliasing the context flags so v-model binds to the same underlying state.
const appearanceEditorOpen = ctx.appearanceEditorOpen
const trainingModalOpen = ctx.trainingModalOpen
const renameDialogOpen = ctx.renameDialogOpen
const renameDialogName = ctx.renameDialogName
const softDeleteDialogOpen = ctx.softDeleteDialogOpen
const wastelandModalOpen = ctx.wastelandModalOpen
</script>

<template>
  <div>
    <div v-if="ctx.loading.value" class="loading-container">
      <Icon icon="mdi:loading" class="loading-icon animate-spin" />
      <p class="loading-text">Loading dweller details...</p>
    </div>

    <div v-else-if="!dweller" class="error-container">
      <Icon icon="mdi:alert-circle" class="error-icon" />
      <p class="error-text">Dweller not found</p>
      <BackButton label="Back to Dwellers" @click="ctx.actions.onBack()" />
    </div>

    <DwellerDetailPane v-else />

    <DwellerAppearanceEditor
      v-if="dweller"
      v-model="appearanceEditorOpen"
      :dweller="dweller"
      @saved="ctx.actions.saveAppearance"
    />
    <TrainingStartModal
      v-if="dweller"
      v-model="trainingModalOpen"
      :dweller="dweller"
      @started="ctx.actions.onTrainingStarted"
    />
    <ExplorationDurationModal
      v-if="dweller"
      :show="wastelandModalOpen"
      :dweller-name="`${ctx.wastelandPendingDweller.value?.firstName ?? ''} ${ctx.wastelandPendingDweller.value?.lastName ?? ''}`"
      :max-stimpaks="ctx.availableStimpaks.value ?? 0"
      :max-radaways="ctx.availableRadaways.value ?? 0"
      @confirm="ctx.actions.confirmSendToWasteland"
      @cancel="ctx.actions.cancelSendToWasteland"
    />

    <UModal v-model="renameDialogOpen" title="Rename Dweller" size="sm">
      <UInput
        v-model="renameDialogName"
        label="First name"
        placeholder="Dweller name"
      />
      <template #footer>
        <UButton variant="secondary" @click="renameDialogOpen = false">Cancel</UButton>
        <UButton variant="primary" :disabled="!renameDialogName.trim()" @click="ctx.actions.confirmRename()">
          Save
        </UButton>
      </template>
    </UModal>

    <UModal v-model="softDeleteDialogOpen" title="Soft-delete Dweller" size="sm">
      <p class="soft-delete-text">
        Soft-delete <strong>{{ dweller?.first_name }} {{ dweller?.last_name }}</strong>? They will leave the vault and
        become tradable at the Trading Post. You can restore them later while they remain listed.
      </p>
      <template #footer>
        <UButton variant="secondary" @click="softDeleteDialogOpen = false">Cancel</UButton>
        <UButton variant="danger" @click="ctx.actions.confirmSoftDelete()">Soft-delete</UButton>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.soft-delete-text {
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  line-height: 1.6;
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
</style>
