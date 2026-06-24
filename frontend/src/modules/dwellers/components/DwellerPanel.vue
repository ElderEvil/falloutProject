<script setup lang="ts">
import { ref } from 'vue'
import DwellerBio from './DwellerBio.vue'
import DwellerStats from './stats/DwellerStats.vue'
import DwellerEquipment from './DwellerEquipment.vue'
import DwellerAppearance from './DwellerAppearance.vue'
import type { Dweller } from '../models/dweller'

interface Props {
  dweller: Dweller
  generatingBio?: boolean
  generatingAppearance?: boolean
  generatingPortrait?: boolean
  isAnyGenerating?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  refresh: []
  'generate-bio': []
  'generate-appearance': []
  'generate-portrait': []
  'generate-all': []
  'edit-appearance': []
}>()

const activeTab = ref('profile')

const tabItems = [
  { label: 'Profile', slot: 'profile' },
  { label: 'Appearance', slot: 'appearance' },
  { label: 'Stats', slot: 'stats' },
  { label: 'Equipment', slot: 'equipment' },
]
</script>

<template>
  <div class="dweller-panel">
    <UTabs v-model="activeTab" :items="tabItems" class="w-full">
      <template #profile>
        <div class="tab-content">
          <DwellerBio
            :bio="dweller.bio"
            :first-name="dweller.first_name"
            :generating-bio="generatingBio"
            :is-any-generating="props.isAnyGenerating"
            @generate-bio="emit('generate-bio')"
            @generate-all="emit('generate-all')"
          />
        </div>
      </template>
      <template #appearance>
        <div class="tab-content">
          <DwellerAppearance
            :visual-attributes="dweller.visual_attributes"
            :generating-appearance="generatingAppearance"
            :generating-portrait="generatingPortrait"
            :is-any-generating="props.isAnyGenerating"
            @generate-appearance="emit('generate-appearance')"
            @generate-portrait="emit('generate-portrait')"
            @edit="emit('edit-appearance')"
          />
        </div>
      </template>
      <template #stats>
        <div class="tab-content">
          <DwellerStats
            :S="dweller.S"
            :P="dweller.P"
            :E="dweller.E"
            :C="dweller.C"
            :I="dweller.I"
            :A="dweller.A"
            :L="dweller.L"
          />
        </div>
      </template>
      <template #equipment>
        <div class="tab-content">
          <DwellerEquipment
            :dweller="dweller"
            @refresh="emit('refresh')"
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
