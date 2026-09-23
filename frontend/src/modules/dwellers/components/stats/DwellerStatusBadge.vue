<script setup lang="ts">
import { computed } from 'vue'
import DwellerStateChip from '../DwellerStateChip.vue'
import { getStatusConfig } from '../../models/dweller'
import type { DwellerStatus } from '../../stores/dweller'

interface Props {
  status: DwellerStatus | null
  size?: 'small' | 'medium' | 'large'
  showLabel?: boolean
}

const { size = 'small', showLabel = false, status } = defineProps<Props>()

const statusConfig = computed(() => getStatusConfig(status))
</script>

<template>
  <DwellerStateChip
    :icon="statusConfig.icon"
    :label="showLabel ? statusConfig.label : ''"
    :size="size"
    class="status-badge badge-live"
    :class="[statusConfig.color, statusConfig.bgColor, statusConfig.borderColor]"
    :title="statusConfig.label"
    :style="{ '--glow-color': statusConfig.glowColor }"
  />
</template>
