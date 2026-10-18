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
  opening?: boolean
  error?: string | null
}

const props = withDefaults(defineProps<Props>(), { opening: false, error: null })

const emit = defineEmits<{
  close: []
  reveal: []
}>()

const revealing = ref(false)
const revealedCount = ref(0)
const { playSound } = useSound()

const revealTimers: number[] = []

const clearRevealTimers = () => {
  revealTimers.forEach((id) => window.clearTimeout(id))
  revealTimers.length = 0
}

const revealContents = () => {
  if (revealing.value) return
  if (!props.result) {
    if (!props.opening) emit('reveal')
    return
  }
  revealing.value = true
  rewards.value.forEach((reward, index) => {
    revealTimers.push(
      window.setTimeout(() => {
        revealedCount.value = index + 1
        if (reward.type === 'dweller') {
          playSound(
            reward.rarity === 'legendary'
              ? 'cardLegendary'
              : reward.rarity === 'rare'
                ? 'cardRare'
                : 'cardCommon',
            'sfx'
          )
        } else {
          playSound(reward.type === 'weapon' ? 'cardWeapon' : 'cardOutfit', 'ui')
          if (reward.rarity === 'legendary') playSound('cardLegendary', 'sfx')
        }
      }, index * 900)
    )
  })
}

watch([() => props.show, () => props.result], () => {
  clearRevealTimers()
  revealing.value = false
  revealedCount.value = 0
  if (props.show && props.result) revealContents()
})

onUnmounted(clearRevealTimers)

const items = computed(() => props.result?.items ?? [])
const rewards = computed(() =>
  props.result
    ? [
        ...items.value.map((item) => ({
          ...item,
          label: item.type === 'weapon' ? 'Weapon' : 'Outfit',
        })),
        { ...props.result.dweller, type: 'dweller' as const, label: 'New Dweller' },
      ]
    : []
)
const rewardSlots = computed(() =>
  rewards.value.length ? rewards.value : [null, null, null, null]
)
const finished = computed(() => revealing.value && revealedCount.value === rewards.value.length)
</script>

<template>
  <TerminalModal
    :open="show"
    title="Vault-Tec supply drop"
    icon="mdi:gift"
    size="3xl"
    max-height="90"
    :show-close="!opening"
    @close="!opening && emit('close')"
  >
    <div class="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
      <div class="flex flex-col items-center gap-4 py-3">
        <div class="grid w-full grid-cols-2 gap-3 sm:grid-cols-4">
          <div
            v-for="(reward, index) in rewardSlots"
            :key="index"
            class="h-60 min-w-0 sm:h-64"
            v-bind="{ 'data-reward-slot': index }"
          >
            <RewardItemCard
              v-if="reward && index < revealedCount"
              :name="reward.name"
              :rarity="reward.rarity"
              :label="reward.label"
              :kind="reward.type === 'dweller' ? 'dweller' : 'item'"
              :item-type="reward.type"
              :image-url="reward.image_url"
              layout="column"
              class="h-full motion-safe:animate-reward-reveal motion-reduce:animate-in motion-reduce:fade-in motion-reduce:duration-150"
            >
              <template v-if="reward.type === 'dweller'" #media>
                <DwellerPortrait
                  :image-url="reward.image_url"
                  :thumbnail-url="result?.dweller.thumbnail_url"
                  :alt="reward.name"
                  prefer-thumbnail
                  image-class="h-full w-full object-cover object-top"
                  fallback-class="size-14 text-theme-primary/50"
                />
              </template>
              <template v-if="reward.type === 'dweller'" #badge>
                <DwellerRarityBadge :rarity="reward.rarity" show-label size="sm" />
              </template>
            </RewardItemCard>
            <Card
              v-else
              class="h-full gap-0 rounded-lg border border-dashed border-theme-primary/30 bg-surface-sunken py-0 shadow-none"
              v-bind="{ 'aria-hidden': true }"
            >
              <CardContent class="flex h-full items-center justify-center p-4">
                <Icon icon="mdi:help" class="size-9 text-theme-primary/40" />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <div class="flex w-full flex-col items-center gap-3">
        <p
          class="flex min-h-10 items-center justify-center text-center text-sm text-muted-foreground"
          role="status"
        >
          <template v-if="error">{{ error }}</template>
          <template v-else-if="opening">Opening your lunchbox…</template>
          <template v-else-if="finished">
            {{ items.length }} items added to Storage · 1 dweller joined your vault
          </template>
          <template v-else-if="revealing"
            >Revealing contents… {{ revealedCount }}/{{ rewards.length }}</template
          >
          <template v-else>Something rattles inside…</template>
        </p>
        <Button
          variant="default"
          :disabled="opening || (revealing && !finished)"
          @click="finished ? emit('close') : revealContents()"
        >
          {{
            finished ? 'Done' : opening ? 'Opening…' : revealing ? 'Revealing…' : 'Reveal Contents'
          }}
        </Button>
      </div>
    </template>
  </TerminalModal>
</template>
