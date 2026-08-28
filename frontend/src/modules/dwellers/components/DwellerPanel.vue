<script setup lang="ts">
import { ref, watch } from 'vue'
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
  generatingPortrait?: boolean
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
  'generate-portrait': []
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
            @generate-all="emit('generate-all')"
          />
          <DwellerAppearance
            v-else-if="currentTab === 'appearance'"
            :visual-attributes="dweller.visual_attributes"
            :generating-appearance="generatingAppearance"
            :generating-portrait="generatingPortrait"
            :is-any-generating="props.isAnyGenerating"
            @generate-appearance="emit('generate-appearance')"
            @generate-portrait="emit('generate-portrait')"
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

.tab-content {
  min-height: 400px;
}
</style>
