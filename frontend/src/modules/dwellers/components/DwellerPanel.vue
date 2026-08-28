<script setup lang="ts">
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import UTabs from '@/core/components/ui/UTabs.vue'
import DwellerBio from './DwellerBio.vue'
import type { MapPlaceLink } from './DwellerBio.vue'
import DwellerStats from './stats/DwellerStats.vue'
import DwellerEquipment from './DwellerEquipment.vue'
import DwellerAppearance from './DwellerAppearance.vue'
import FamilyTreePanel from './FamilyTreePanel.vue'
import type { Dweller } from '../models/dweller'

interface Props {
  dweller: Dweller
  dwellerId?: string
  generatingBio?: boolean
  generatingAppearance?: boolean
  isAnyGenerating?: boolean
  vaultId?: string
  placeLinks?: MapPlaceLink[]
  initialTab?: string
  highlightStat?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  refresh: []
  'generate-bio': []
  'generate-appearance': []
  'generate-all': []
  'edit-appearance': []
  'navigate-dweller': [dwellerId: string]
}>()

const activeTab = ref(props.initialTab ?? 'profile')
watch(() => props.initialTab, (tab) => (activeTab.value = tab ?? 'profile'))

const tabs = [
  { key: 'profile', label: 'Profile' },
  { key: 'appearance', label: 'Appearance' },
  { key: 'stats', label: 'Stats' },
  { key: 'equipment', label: 'Equipment' },
  { key: 'family', label: 'Family' },
]
</script>

<template>
  <div class="dweller-panel">
    <div class="dossier-action">
      <div>
        <p class="dossier-title">Dweller dossier</p>
        <p class="dossier-description">Generate appearance, portrait, and biography together.</p>
      </div>
      <UTooltip text="Creates or replaces appearance, portrait, and biography" position="top">
        <UButton variant="secondary" size="sm" :disabled="props.isAnyGenerating" @click="emit('generate-all')">
          <Icon :icon="props.isAnyGenerating ? 'mdi:loading' : 'mdi:sparkles'" class="h-4 w-4" :class="{ 'animate-spin': props.isAnyGenerating }" />
          Complete dossier
        </UButton>
      </UTooltip>
    </div>
    <UTabs v-model="activeTab" :tabs="tabs">
      <template #default="{ activeTab: currentTab }">
        <div class="tab-content">
          <DwellerBio
            v-if="currentTab === 'profile'"
            :bio="dweller.bio"
            :first-name="dweller.first_name"
            :generating-bio="generatingBio"
            :is-any-generating="props.isAnyGenerating"
            :vault-id="props.vaultId"
            :place-links="props.placeLinks"
            @generate-bio="emit('generate-bio')"
          />
          <DwellerAppearance
            v-else-if="currentTab === 'appearance'"
            :visual-attributes="dweller.visual_attributes"
            :generating-appearance="generatingAppearance"
            :is-any-generating="props.isAnyGenerating"
            @generate-appearance="emit('generate-appearance')"
            @edit="emit('edit-appearance')"
          />
          <DwellerStats
            v-else-if="currentTab === 'stats'"
            :S="dweller.S"
            :P="dweller.P"
            :E="dweller.E"
            :C="dweller.C"
            :I="dweller.I"
            :A="dweller.A"
            :L="dweller.L"
            :highlight-stat="props.highlightStat"
          />
          <DwellerEquipment
            v-else-if="currentTab === 'equipment'"
            :dweller="dweller"
            @refresh="emit('refresh')"
          />
          <FamilyTreePanel
            v-else-if="currentTab === 'family'"
            :dweller-id="props.dwellerId"
            :dweller-name="dweller ? `${dweller.first_name} ${dweller.last_name}` : ''"
            :vault-id="props.vaultId"
            @select="emit('navigate-dweller', $event)"
          />
        </div>
      </template>
    </UTabs>
  </div>
</template>

<style scoped>
.dweller-panel {
  width: 100%;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.dossier-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid color-mix(in srgb, var(--color-theme-primary) 22%, transparent);
}

.dossier-title {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dossier-description {
  margin-top: 0.25rem;
  color: color-mix(in srgb, var(--color-theme-primary) 65%, transparent);
  font-size: 0.75rem;
}

@media (max-width: 36rem) {
  .dossier-action {
    align-items: stretch;
    flex-direction: column;
  }
}

.tab-content {
  min-height: 400px;
}
</style>
