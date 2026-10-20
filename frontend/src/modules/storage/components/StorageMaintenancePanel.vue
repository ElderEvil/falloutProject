<script setup lang="ts">
import { watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'
import { storeToRefs } from 'pinia'
import { useStorageStore } from '../stores/storage'

const props = defineProps<{ vaultId: string; workers: number; slots: number }>()
const storage = useStorageStore()
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
  <section aria-label="Storage maintenance">
    <Card
      class="items-start gap-x-6 gap-y-3 p-4 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
    >
      <h3 class="flex items-center gap-2 font-semibold text-theme-primary">
        <Icon icon="mdi:tools" class="h-5 w-5 shrink-0" :ariaHidden="true" />
        Weapon maintenance
      </h3>
      <p class="flex items-center gap-2">
        <Icon
          icon="mdi:account-group"
          class="h-4 w-4 shrink-0 text-theme-primary"
          :ariaHidden="true"
        />
        <span>{{ workers }} / {{ slots }} room workers</span>
      </p>
      <template v-if="maintenance?.enabled">
        <p class="flex items-center gap-2">
          <Icon
            :icon="maintenanceIcons[maintenance.mode] ?? 'mdi:shield-check'"
            class="h-4 w-4 shrink-0 text-theme-primary"
            :ariaHidden="true"
          />
          <span>{{ maintenanceLabel }}</span>
        </p>
        <p class="flex items-center gap-2">
          <Icon
            icon="mdi:shield-outline"
            class="h-4 w-4 shrink-0 text-theme-primary"
            :ariaHidden="true"
          />
          <span>
            Vault-wide: {{ maintenance.total_endurance }} END ·
            {{ maintenance.protection_pct.toFixed(0) }}% protection
          </span>
        </p>
      </template>
      <p v-else class="flex items-center gap-2 text-muted-foreground">
        <Icon icon="mdi:pause-circle-outline" class="h-4 w-4 shrink-0" :ariaHidden="true" />
        <span>Weapon maintenance is not active.</span>
      </p>
    </Card>
  </section>
</template>
