<script setup lang="ts">
import { ref } from 'vue'
import UTabs from '@/components/ui/UTabs.vue'
import DwellerBio from './DwellerBio.vue'
import DwellerStats from './DwellerStats.vue'
import DwellerEquipment from './DwellerEquipment.vue'
import type { DwellerDetailRead } from '@/types/dweller'

interface Props {
  dweller: DwellerDetailRead
}

defineProps<Props>()
const emit = defineEmits<{
  refresh: []
}>()

const activeTab = ref('profile')

const tabs = [
  { key: 'profile', label: 'Profile' },
  { key: 'stats', label: 'Stats' },
  { key: 'equipment', label: 'Equipment' }
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
          />
          <DwellerEquipment v-else-if="currentTab === 'equipment'" :dweller="dweller" @refresh="emit('refresh')" />
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
