<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useSound } from '@/core/composables/useSound'
import { Button } from '@/core/components/ui/button'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import RewardCard from '@/core/components/common/RewardCard.vue'
import { getItemIcon } from '@/core/models/items'
import type { components } from '@/core/types/api.generated'

type LunchboxOpened = components['schemas']['LunchboxOpened']
type LunchboxOpenedItem = components['schemas']['LunchboxOpenedItem']

interface Props {
  show: boolean
  result: LunchboxOpened | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const revealed = ref(false)
const { playSound } = useSound()

const revealTimers: number[] = []

const clearRevealTimers = () => {
  revealTimers.forEach((id) => window.clearTimeout(id))
  revealTimers.length = 0
}

const revealContents = () => {
  revealed.value = true
  clearRevealTimers()
  items.value.forEach((item, index) => {
    const key = item.type === 'weapon' ? 'cardWeapon' : 'cardOutfit'
    revealTimers.push(window.setTimeout(() => playSound(key, 'ui'), index * 250))
  })
  if (items.value.some((item) => item.rarity === 'legendary')) {
    revealTimers.push(
      window.setTimeout(() => playSound('cardLegendary', 'sfx'), items.value.length * 250)
    )
  }
}

watch(() => props.show, (open) => {
  clearRevealTimers()
  if (open) {
    revealed.value = false
  }
})

onUnmounted(clearRevealTimers)

const items = computed(() => props.result?.items ?? [])
const dwellerName = computed(() => props.result?.dweller.name ?? 'New Dweller')

const itemIcon = (item: LunchboxOpenedItem): string => getItemIcon(item.type, item)
const itemLabel = (type: string): string => type === 'weapon' ? 'Weapon' : 'Outfit'
</script>

<template>
  <TerminalModal
    :open="show && !!result"
    title="Lunchbox Opened!"
    icon="mdi:gift"
    size="xl"
    max-height="75"
    @close="emit('close')"
  >
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
          <Button variant="default" class="border-2 border-theme-primary hover:shadow-glow-md" @click="revealContents">
            Reveal Contents
          </Button>
        </div>

        <div v-if="result && revealed" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <RewardCard
            v-for="(item, index) in items"
            :key="index"
            :icon="itemIcon(item)"
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

    <template #footer>
      <Button variant="default" class="border-2 border-theme-primary hover:shadow-glow-md" @click="emit('close')">
        Done
      </Button>
    </template>
  </TerminalModal>
</template>
