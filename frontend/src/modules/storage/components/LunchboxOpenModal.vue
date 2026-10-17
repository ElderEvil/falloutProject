<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useSound } from '@/core/composables/useSound'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent } from '@/core/components/ui/card'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import RewardItemCard from '@/core/components/common/RewardItemCard.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerRarityBadge from '@/modules/dwellers/components/DwellerRarityBadge.vue'
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
  if (
    items.value.some((item) => item.rarity === 'legendary') ||
    props.result?.dweller.rarity === 'legendary'
  ) {
    revealTimers.push(
      window.setTimeout(() => playSound('cardLegendary', 'sfx'), items.value.length * 250)
    )
  }
}

watch(
  () => props.show,
  (open) => {
    clearRevealTimers()
    if (open) {
      revealed.value = false
    }
  }
)

onUnmounted(clearRevealTimers)

const items = computed(() => props.result?.items ?? [])
const dwellerName = computed(() => props.result?.dweller.name ?? 'New Dweller')

const itemLabel = (type: string): string => (type === 'weapon' ? 'Weapon' : 'Outfit')
</script>

<template>
  <TerminalModal
    :open="show && !!result"
    title="Lunchbox Opened!"
    icon="mdi:gift"
    size="3xl"
    max-height="75"
    @close="emit('close')"
  >
    <div class="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
      <div v-if="result && !revealed" class="flex flex-col items-center gap-6 py-5">
        <p class="text-xs uppercase tracking-widest text-muted-foreground">Vault-Tec supply drop</p>
        <div class="grid w-full max-w-lg grid-cols-2 gap-3 sm:grid-cols-4" aria-hidden="true">
          <Card
            v-for="index in items.length + 1"
            :key="index"
            class="gap-0 rounded-lg border border-dashed border-theme-primary/30 bg-surface-sunken py-0 shadow-none"
          >
            <CardContent class="flex h-28 items-center justify-center p-4 sm:h-36">
              <Icon icon="mdi:help" class="size-9 text-theme-primary/40" />
            </CardContent>
          </Card>
        </div>
        <p class="text-sm text-muted-foreground">Something rattles inside…</p>
        <Button variant="default" @click="revealContents">
          <!-- @vue-ignore -->
          <Icon icon="mdi:gift-open" data-icon="inline-start" />
          Reveal Contents
        </Button>
      </div>

      <div
        v-if="result && revealed"
        class="flex flex-col gap-4 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2"
        aria-live="polite"
      >
        <RewardItemCard
          :name="dwellerName"
          :rarity="result.dweller.rarity"
          label="New Dweller"
          meta="Has joined your vault."
          kind="dweller"
          layout="row"
        >
          <template #media>
            <DwellerPortrait
              :image-url="result.dweller.image_url"
              :thumbnail-url="result.dweller.thumbnail_url"
              :alt="dwellerName"
              prefer-thumbnail
              image-class="h-32 w-full object-cover object-top sm:h-36"
              fallback-class="size-14 text-theme-primary/50"
            />
          </template>
          <template #badge>
            <DwellerRarityBadge :rarity="result.dweller.rarity" show-label size="sm" />
          </template>
        </RewardItemCard>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <RewardItemCard
            v-for="(item, index) in items"
            :key="index"
            :name="item.name"
            :rarity="item.rarity"
            :label="itemLabel(item.type)"
            :item-type="item.type"
            :image-url="item.image_url"
          />
        </div>
        <p class="text-center text-xs text-muted-foreground">
          {{ items.length }} items added to Storage · 1 dweller joined your vault
        </p>
      </div>
    </div>

    <template #footer>
      <Button variant="default" @click="emit('close')"> Done </Button>
    </template>
  </TerminalModal>
</template>
