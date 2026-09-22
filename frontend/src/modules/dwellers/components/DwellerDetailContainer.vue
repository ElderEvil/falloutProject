<script setup lang="ts">
import { computed, defineAsyncComponent, provide } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import BackButton from '@/core/components/common/BackButton.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { Button } from '@/core/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/core/components/ui/dialog'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'
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
const appearanceEditorOpen = ctx.appearanceEditorOpen
const trainingModalOpen = ctx.trainingModalOpen
const renameDialogOpen = ctx.renameDialogOpen
const renameDialogName = ctx.renameDialogName
const softDeleteDialogOpen = ctx.softDeleteDialogOpen
const wastelandModalOpen = ctx.wastelandModalOpen
</script>

<template>
  <div>
    <TerminalLoadingState v-if="ctx.loading.value" full-height message="Loading dweller details..." />

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

    <Dialog v-model:open="renameDialogOpen">
      <DialogContent
        class="flex max-h-[60vh] w-full max-w-sm flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-sm"
      >
        <DialogHeader
          class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
        >
          <DialogTitle class="text-2xl font-bold text-theme-primary terminal-glow">Rename Dweller</DialogTitle>
        </DialogHeader>
        <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
          <Label for="rename-dweller" class="mb-1 block text-sm font-medium text-theme-primary/70">
            First name
          </Label>
          <Input id="rename-dweller" v-model="renameDialogName" placeholder="Dweller name" />
        </div>
        <DialogFooter
          class="flex flex-shrink-0 justify-end gap-2 border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5"
        >
          <Button variant="secondary" @click="renameDialogOpen = false">Cancel</Button>
          <Button variant="default" :disabled="!renameDialogName.trim()" @click="ctx.actions.confirmRename()">
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="softDeleteDialogOpen">
      <DialogContent
        class="flex max-h-[60vh] w-full max-w-sm flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-sm"
      >
        <DialogHeader
          class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
        >
          <DialogTitle class="text-2xl font-bold text-theme-primary terminal-glow">Soft-delete Dweller</DialogTitle>
        </DialogHeader>
        <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
          <p class="soft-delete-text">
            Soft-delete <strong>{{ dweller?.first_name }} {{ dweller?.last_name }}</strong>? They will leave the vault and
            become tradable at the Trading Post. You can restore them later while they remain listed.
          </p>
        </div>
        <DialogFooter
          class="flex flex-shrink-0 justify-end gap-2 border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5"
        >
          <Button variant="secondary" @click="softDeleteDialogOpen = false">Cancel</Button>
          <Button variant="destructive" @click="ctx.actions.confirmSoftDelete()">Soft-delete</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.soft-delete-text {
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  line-height: 1.6;
}

.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  min-height: 400px;
}

.error-icon {
  width: 4rem;
  height: 4rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 10px var(--color-theme-glow));
}

.error-text {
  font-size: 1.25rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}
</style>
