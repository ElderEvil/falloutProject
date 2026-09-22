<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/core/components/ui/dialog'
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
  <Dialog :open="show && !!result" @update:open="(open) => { if (!open) emit('close') }">
    <DialogContent
      class="flex max-h-[75vh] w-full max-w-xl flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-xl"
    >
      <DialogHeader
        class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
      >
        <Icon icon="mdi:gift" class="h-8 w-8 text-theme-primary terminal-glow" />
        <DialogTitle class="text-2xl font-bold text-theme-primary terminal-glow">Lunchbox Opened!</DialogTitle>
      </DialogHeader>

      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
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
          <Button variant="default" class="border-2 border-theme-primary hover:shadow-glow-md" @click="revealed = true">
            Reveal Contents
          </Button>
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
      </div>

      <DialogFooter
        class="flex-shrink-0 justify-end border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5"
      >
        <Button variant="default" class="border-2 border-theme-primary hover:shadow-glow-md" @click="emit('close')">
          Done
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
