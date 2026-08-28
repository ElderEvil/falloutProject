<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import BackButton from '@/core/components/common/BackButton.vue'
import UButton from '@/core/components/ui/UButton.vue'
import type { components } from '@/core/types/api.generated'
import type { MapPlaceLink } from './DwellerBio.vue'
import type { RevivalCostResponse } from '../models/dweller'
import DwellerCard from './cards/DwellerCard.vue'
import DwellerPanel from './DwellerPanel.vue'
import DwellerStatusBadge from './stats/DwellerStatusBadge.vue'
import { RevivalSection } from './death'

type DwellerDetailRead = components['schemas']['DwellerReadFull']

interface Props {
  dweller: DwellerDetailRead
  vaultId?: string
  placeLinks?: MapPlaceLink[]
  initialTab?: string
  highlightStat?: string
  generatingBio?: boolean
  generatingAppearance?: boolean
  generatingPortrait?: boolean
  generatingAI?: boolean
  usingStimpack?: boolean
  usingRadaway?: boolean
  issuingMedicalSupply?: boolean
  assigning?: boolean
  unassigning?: boolean
  revivalLoading?: boolean
  revivalCost: RevivalCostResponse | null
  availableStimpaks?: number
  availableRadaways?: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'rename'): void
  (e: 'chat'): void
  (e: 'assign'): void
  (e: 'unassign'): void
  (e: 'recall'): void
  (e: 'use-stimpack'): void
  (e: 'use-radaway'): void
  (e: 'train'): void
  (e: 'send-wasteland'): void
  (e: 'generate-portrait'): void
  (e: 'issue-medical-supply', supply: 'stimpack' | 'radaway'): void
  (e: 'refresh'): void
  (e: 'generate-bio'): void
  (e: 'generate-appearance'): void
  (e: 'generate-all'): void
  (e: 'edit-appearance'): void
  (e: 'navigate-dweller', id: string): void
  (e: 'revive'): void
  (e: 'header-name-click'): void
}>()

const isAnyGenerating = computed(
  () =>
    !!props.generatingBio ||
    !!props.generatingAppearance ||
    !!props.generatingAI ||
    !!props.generatingPortrait
)

const cardLoading = computed(
  () =>
    !!props.generatingAI ||
    !!props.usingStimpack ||
    !!props.usingRadaway ||
    !!props.issuingMedicalSupply ||
    !!props.assigning ||
    !!props.unassigning
)

const isDead = computed(() => props.dweller.is_dead === true)
const isPermanentlyDead = computed(() => !!props.dweller.is_permanently_dead)
</script>

<template>
  <div class="dweller-detail">
    <!-- Header -->
    <div class="detail-header">
      <BackButton label="Back to Dwellers" @click="emit('back')" />

      <div class="header-info">
        <div class="name-section">
          <h1 class="dweller-name cursor-pointer select-none" @click="emit('header-name-click')">
            {{ dweller.first_name }} {{ dweller.last_name }}
          </h1>
          <UButton
            v-if="!isDead"
            @click="emit('rename')"
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
          :loading="cardLoading"
          :generating-portrait="generatingPortrait"
          :available-stimpaks="availableStimpaks"
          :available-radaways="availableRadaways"
          :issuing-medical-supply="issuingMedicalSupply"
          @chat="emit('chat')"
          @assign="emit('assign')"
          @unassign="emit('unassign')"
          @recall="emit('recall')"
          @use-stimpack="emit('use-stimpack')"
          @use-radaway="emit('use-radaway')"
          @train="emit('train')"
          @send-wasteland="emit('send-wasteland')"
          @generate-portrait="emit('generate-portrait')"
          @issue-medical-supply="emit('issue-medical-supply', $event)"
        />

        <!-- Revival Section for Dead Dwellers -->
        <RevivalSection
          v-if="isDead && !isPermanentlyDead"
          :dweller-id="dweller.id"
          :revival-cost="revivalCost"
          :loading="revivalLoading"
          @revive="emit('revive')"
        />

        <!-- Permanently Dead Notice -->
        <div
          v-else-if="isPermanentlyDead"
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
        :dweller-id="dweller.id"
        :generating-bio="generatingBio"
        :generating-appearance="generatingAppearance"
        :is-any-generating="isAnyGenerating"
        :vault-id="vaultId"
        :place-links="placeLinks"
        :initial-tab="initialTab"
        :highlight-stat="highlightStat"
        @refresh="emit('refresh')"
        @generate-bio="emit('generate-bio')"
        @generate-appearance="emit('generate-appearance')"
        @generate-all="emit('generate-all')"
        @edit-appearance="emit('edit-appearance')"
        @navigate-dweller="(id) => emit('navigate-dweller', id)"
      />
    </div>
  </div>
</template>

<style scoped>
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
  letter-spacing: -0.5px;
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
  grid-template-columns: minmax(340px, 400px) minmax(0, 1fr);
  gap: 2rem;
  align-items: start;
}

@media (max-width: 1280px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
