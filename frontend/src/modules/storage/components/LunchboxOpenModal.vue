<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, UModal } from '@/core/components/ui'
import RewardCard from '@/core/components/common/RewardCard.vue'
import type { components } from '@/core/types/api.generated'

type LunchboxOpened = components['schemas']['LunchboxOpened']

interface Props {
  show: boolean
  result: LunchboxOpened | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const revealed = ref(false)

watch(() => props.show, (open) => {
  if (open) revealed.value = false
})

const items = computed(() => props.result?.items ?? [])
const dwellerName = computed(() => props.result?.dweller.name ?? 'New Dweller')

const itemIcon = (type: string): string => type === 'weapon' ? 'mdi:sword-cross' : 'mdi:tshirt-crew'
const itemLabel = (type: string): string => type === 'weapon' ? 'Weapon' : 'Outfit'
</script>

<template>
  <UModal
    :model-value="show && !!result"
    title="Lunchbox Opened!"
    size="wide"
    @close="emit('close')"
  >
    <template #header="{ titleId }">
      <div class="flex items-center gap-3">
        <Icon icon="mdi:gift" class="h-8 w-8 text-theme-primary terminal-glow" />
        <h2 :id="titleId" class="text-2xl font-bold text-theme-primary terminal-glow">Lunchbox Opened!</h2>
      </div>
    </template>

    <div v-if="result && !revealed" class="flex flex-col items-center gap-6 p-8">
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div
          v-for="index in 4"
          :key="index"
          class="flex h-24 w-24 items-center justify-center rounded-md border-2 border-dashed border-theme-primary/40 bg-theme-primary/5"
        >
          <Icon icon="mdi:gift" class="h-10 w-10 text-theme-primary/50" />
        </div>
      </div>
      <p class="text-theme-primary/70">Something rattles inside…</p>
      <UButton variant="primary" @click="revealed = true">Reveal Contents</UButton>
    </div>

    <div v-if="result && revealed" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <RewardCard
        v-for="(item, index) in items"
        :key="index"
        :icon="itemIcon(item.type)"
        :label="itemLabel(item.type)"
        :value="`${item.name} · ${item.rarity}`"
      />
      <RewardCard
        icon="mdi:account-plus"
        label="New Dweller"
        :value="dwellerName"
      />
    </div>

    <template #footer>
      <div class="flex w-full justify-end">
        <UButton variant="primary" @click="emit('close')">Done</UButton>
      </div>
    </template>
  </UModal>
</template>
