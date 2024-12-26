<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NCard, NProgress, NSpace } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'
import DwellerAvatar from './DwellerAvatar.vue'
import DwellerDetailsModal from './DwellerDetailsModal.vue'
import DwellerChat from './DwellerChat.vue'
import { getDwellerFullName } from '@/utils/dwellerUtils'
import type { DwellerFull } from '@/types/dweller.types'

const props = defineProps<{
  dweller: DwellerFull
  showActions?: boolean
  onUnassign?: () => void
}>()

const themeStore = useThemeStore()
const showDetails = ref(false)
const showChat = ref(false)
</script>

<template>
  <NCard size="small" class="dweller-card">
    <div class="dweller-content">
      <DwellerAvatar :dweller="dweller" size="medium" show-default-icon />
      <div class="dweller-info">
        <span class="name">{{ getDwellerFullName(dweller).toUpperCase() }}</span>
        <span class="level">LEVEL {{ dweller.level }}</span>
        <div class="stats">
          <NProgress
            type="line"
            :percentage="(dweller.health / dweller.max_health) * 100"
            :color="themeStore.theme.colors.primary"
            :height="8"
            class="health-bar"
          />
          <span class="health-value">HP: {{ dweller.health }}/{{ dweller.max_health }}</span>
        </div>
      </div>
    </div>
    <div class="dweller-actions">
      <NSpace justify="space-between">
        <div class="action-buttons">
          <NButton quaternary size="small" @click="showDetails = true"> DETAILS</NButton>
          <NButton quaternary size="small" @click="showChat = true"> COMM LINK</NButton>
        </div>
        <NButton
          v-if="onUnassign"
          quaternary
          size="small"
          @click="onUnassign"
          class="unassign-button"
        >
          UNASSIGN
        </NButton>
      </NSpace>
    </div>

    <DwellerDetailsModal v-model="showDetails" :dweller="dweller" />
    <DwellerChat v-model="showChat" :dweller="dweller" />
  </NCard>
</template>

<style scoped>
/* ... existing styles ... */
</style>
