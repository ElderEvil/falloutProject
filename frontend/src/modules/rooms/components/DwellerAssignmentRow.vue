<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import DwellerListRow from '@/modules/dwellers/components/DwellerListRow.vue'
import DwellerStatusBadge from '@/modules/dwellers/components/stats/DwellerStatusBadge.vue'
import {
  getAbilityConfig,
  type DwellerShort,
  type SpecialKey,
} from '@/modules/dwellers/models/dweller'

const props = defineProps<{
  dweller: DwellerShort
  ability: string | null
  currentRoomName: string
}>()

const emit = defineEmits<{
  activate: [dwellerId: string]
}>()

const abilityConfig = computed(() => getAbilityConfig(props.ability))
const statKey = computed<SpecialKey | null>(() => {
  const ability = abilityConfig.value
  return ability ? (props.ability!.toLowerCase() as SpecialKey) : null
})
const statValue = computed(() => (statKey.value ? props.dweller[statKey.value] : 0))
</script>

<template>
  <DwellerListRow :dweller="dweller" dense show-identity @activate="emit('activate', $event)">
    <template #middle>
      <div class="picker-current">
        <DwellerStatusBadge :status="dweller.status" show-label size="small" />
        <span class="picker-current__room">
          <Icon icon="mdi:door-open" class="size-3.5 shrink-0" :ariaHidden="true" />
          {{ currentRoomName }}
        </span>
      </div>
      <span class="picker-divider" aria-hidden="true"></span>
      <div v-if="abilityConfig" class="picker-room-stat">
        <Icon :icon="abilityConfig.icon" class="size-4 shrink-0" :ariaHidden="true" />
        <span class="picker-room-stat__label">{{ abilityConfig.label }}</span>
        <strong class="picker-room-stat__value">{{ statValue }}</strong>
      </div>
    </template>
    <template #actions>
      <Icon
        icon="mdi:plus-circle-outline"
        class="size-4 text-theme-primary/50"
        :ariaHidden="true"
      />
    </template>
  </DwellerListRow>
</template>

<style scoped>
.picker-current {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
  white-space: nowrap;
}

.picker-current__room {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  overflow: hidden;
  color: color-mix(in srgb, var(--color-theme-primary) 65%, transparent);
  font-size: 0.65rem;
  text-overflow: ellipsis;
}

.picker-divider {
  display: inline-block;
  width: 1px;
  align-self: stretch;
  background: color-mix(in srgb, var(--color-theme-glow) 35%, transparent);
}

.picker-room-stat {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.4rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 3px;
  background: color-mix(in srgb, var(--color-theme-primary) 12%, transparent);
  color: var(--color-theme-primary);
  font-size: 0.7rem;
  white-space: nowrap;
}

.picker-room-stat__label {
  opacity: 0.65;
}

.picker-room-stat__value {
  color: var(--color-terminal-green);
  font-size: 0.8rem;
}
</style>
