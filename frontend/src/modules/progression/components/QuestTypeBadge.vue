<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/core/components/ui/badge'
import { QUEST_TYPE_COLORS, isSideQuestType, questTypeLabel } from '../models/quest'

const props = defineProps<{ questType: string }>()

const colors = computed(() => QUEST_TYPE_COLORS[props.questType] || QUEST_TYPE_COLORS.side)
const isSide = computed(() => isSideQuestType(props.questType))
const label = computed(() => questTypeLabel(props.questType))
</script>

<template>
  <Badge
    :variant="isSide ? 'outline' : 'default'"
    :style="isSide ? undefined : { backgroundColor: colors.bg, color: colors.text }"
    class="type-badge"
  >
    {{ label }}
  </Badge>
</template>

<style scoped>
.type-badge {
  font-size: 0.7rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
</style>
