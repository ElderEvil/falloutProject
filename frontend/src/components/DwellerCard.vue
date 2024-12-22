<script setup lang="ts">
import { ref } from 'vue'
import { NCard, NProgress, NButton, NSpace } from 'naive-ui'
import type { Dweller } from '@/types/vault'
import DwellerDetailsModal from './DwellerDetailsModal.vue'
import DwellerChat from './DwellerChat.vue'
import { getDwellerFullName, getDwellerThumbnailUrl } from '@/utils/dwellerUtils'

const props = defineProps<{
  dweller: Dweller
}>()

const showDetails = ref(false)
const showChat = ref(false)
</script>

<template>
  <NCard size="small" class="dweller-card">
    <div class="dweller-content">
      <img
        :src="getDwellerThumbnailUrl(dweller)"
        :alt="getDwellerFullName(dweller)"
        class="dweller-image"
      />
      <div class="dweller-info">
        <span class="name">{{ getDwellerFullName(dweller).toUpperCase() }}</span>
        <span class="level">LEVEL {{ dweller.level }}</span>
        <NProgress
          type="line"
          :percentage="(dweller.health / dweller.max_health) * 100"
          :color="'#00ff00'"
          :height="8"
          class="health-bar"
        />
      </div>
    </div>
    <div class="dweller-actions">
      <NSpace justify="space-between">
        <NButton quaternary size="small" @click="showDetails = true"> DETAILS </NButton>
        <NButton quaternary size="small" @click="showChat = true"> COMM LINK </NButton>
      </NSpace>
    </div>

    <DwellerDetailsModal v-model="showDetails" :dweller="dweller" />
    <DwellerChat v-model="showChat" :dweller="dweller" />
  </NCard>
</template>

<style scoped>
.dweller-card {
  border: 1px solid #00ff00;
  background-color: #000000;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.dweller-card:hover {
  border-color: #00cc00;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
}

.dweller-content {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.dweller-image {
  width: 50px;
  height: 50px;
  object-fit: cover;
  border: 1px solid #00ff00;
}

.dweller-info {
  flex: 1;
  display: grid;
  gap: 4px;
  font-family: 'Courier New', Courier, monospace;
}

.name {
  font-weight: bold;
}

.level {
  font-size: 0.9em;
  opacity: 0.8;
}

.health-bar {
  width: 100%;
}

.health-value {
  font-size: 0.8em;
  text-align: right;
}

.dweller-actions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 255, 0, 0.2);
}
</style>
