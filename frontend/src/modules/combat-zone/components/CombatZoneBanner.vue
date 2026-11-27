<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import type { CombatZoneMarkerRead } from '@/modules/map/models/map'
import CombatZonePanel from './CombatZonePanel.vue'

const props = defineProps<{ vaultId: string }>()
const flags = useFeatureFlagsStore()
const open = ref(false)

void flags.fetchFlags()

const marker = computed<CombatZoneMarkerRead | null>(() =>
  flags.combatZone
    ? {
        id: 'combat-zone',
        name: 'The Combat Zone',
        coord_x: 0,
        coord_y: 0,
        enabled: true,
      }
    : null
)
</script>

<template>
  <div
    v-if="flags.combatZone"
    class="flex flex-wrap items-center gap-3 rounded border border-terminal-green/40 bg-surface-raised px-4 py-2 text-sm"
  >
    <Icon icon="mdi:sword-cross" class="h-5 w-5 shrink-0" ariaHidden="true" />
    <span class="font-bold">INTERCHANGE 77 · THE COMBAT ZONE</span>
    <span class="text-xs text-theme-primary/60">
      Send a contender, command the bout, take the purse.
    </span>
    <Button size="sm" class="ml-auto" @click="open = true">Enter the Zone</Button>
  </div>

  <CombatZonePanel v-model:open="open" :vault-id="vaultId" :marker="marker" />
</template>
