<script setup lang="ts">
import { onScopeDispose, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'
import { storeToRefs } from 'pinia'
import { useStorageStore } from '../stores/storage'

const props = defineProps<{ vaultId: string; workers: number; slots: number }>()
const storage = useStorageStore()
onScopeDispose(storage.retain())
const { maintenance, maintenanceLabel } = storeToRefs(storage)
const maintenanceIcons: Record<string, string> = {
  rusting: 'mdi:arrow-down-bold',
  stable: 'mdi:shield-check',
  improving: 'mdi:arrow-up-bold',
}
watch(
  () => [props.vaultId, props.workers],
  () => {
    void storage.refresh(props.vaultId)
  },
  { immediate: true }
)
</script>

<template>
  <section aria-label="Storage maintenance" class="space-y-2">
    <h3 class="flex items-center gap-2 font-semibold text-theme-primary">
      <Icon icon="mdi:tools" class="h-5 w-5 shrink-0" :ariaHidden="true" />
      Weapon maintenance
    </h3>
    <Card
      class="grid gap-0 divide-y divide-theme-primary/20 p-0 text-sm sm:divide-x sm:divide-y-0"
      :class="maintenance?.enabled ? 'sm:grid-cols-4' : 'sm:grid-cols-2'"
    >
      <p class="flex min-w-0 items-center justify-center gap-2 px-4 py-3 text-center">
        <Icon
          icon="mdi:account-group"
          class="h-4 w-4 shrink-0 text-theme-primary"
          :ariaHidden="true"
        />
        <span>{{ workers }} / {{ slots }} room workers</span>
      </p>
      <template v-if="maintenance?.enabled">
        <p class="flex min-w-0 items-center justify-center gap-2 px-4 py-3 text-center">
          <Icon
            :icon="maintenanceIcons[maintenance.mode] ?? 'mdi:shield-check'"
            class="h-4 w-4 shrink-0 text-theme-primary"
            :ariaHidden="true"
          />
          <span>{{ maintenanceLabel }}</span>
        </p>
        <p class="flex min-w-0 items-center justify-center gap-2 px-4 py-3 text-center">
          <Icon
            icon="mdi:heart"
            class="h-4 w-4 shrink-0 text-special-endurance"
            :ariaHidden="true"
          />
          <span>Vault-wide: {{ maintenance.total_endurance }} END</span>
        </p>
        <p class="flex min-w-0 items-center justify-center gap-2 px-4 py-3 text-center">
          <Icon
            icon="mdi:shield-outline"
            class="h-4 w-4 shrink-0 text-theme-primary"
            :ariaHidden="true"
          />
          <span>{{ maintenance.protection_pct.toFixed(0) }}% protection</span>
        </p>
      </template>
      <p
        v-else
        class="flex min-w-0 items-center justify-center gap-2 px-4 py-3 text-center text-muted-foreground"
      >
        <Icon icon="mdi:pause-circle-outline" class="h-4 w-4 shrink-0" :ariaHidden="true" />
        <span>Weapon maintenance is not active.</span>
      </p>
    </Card>
  </section>
</template>
