<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { getRarityBorderClass } from '@/core/models/items'
import ItemCard from '@/core/components/common/ItemCard.vue'
interface Props {
  item: any
  itemType: string
  count?: number
}

const { count = 1, item, itemType } = defineProps<Props>()

const emit = defineEmits<{
  sell: []
  sellAll: []
  scrap: []
  open: []
}>()

const rarityBorderClass = computed(() => getRarityBorderClass((item as any).rarity))

const showSellAll = computed(() => count > 1 && itemType === 'junk')

const isActionable = computed(() => itemType === 'weapon' || itemType === 'outfit' || itemType === 'junk')

const isOpenable = computed(() => itemType === 'lunchbox')
</script>

<template>
  <Card
    :class="[
      'h-full w-full overflow-hidden rounded-lg border-2 gap-0 p-4 font-mono transition-all duration-200 hover:-translate-y-0.5 hover:bg-surface-raised hover:shadow-glow-md',
      rarityBorderClass,
    ]"
  >
    <ItemCard
      :item="item"
      :item-type="itemType"
      :count="count"
      variant="grid"
      class="h-full"
    >
      <template #actions>
        <!-- Footer: value + inventory actions (generic supplies have no sell/scrap endpoints) -->
        <div
          v-if="isActionable || isOpenable"
          class="mt-auto flex items-center justify-between gap-3 border-t border-(--color-theme-primary)/20 pt-2"
        >
          <div class="flex items-center gap-1.5 text-sm font-bold text-(--color-theme-primary)">
            <Icon icon="mdi:currency-usd" class="h-4 w-4 text-(--color-caps)" />
            <span>{{ item.value || 0 }}</span>
          </div>
          <div class="flex flex-wrap justify-end gap-2">
            <!--
              TooltipProvider delayDuration (200ms) preserves the previous tooltip
              hover delay; reka-ui opens instantly on keyboard focus, which is the
              stronger a11y contract for icon-only buttons.
            -->
            <TooltipProvider :delay-duration="200">
              <Tooltip v-if="isOpenable">
                <TooltipTrigger as-child>
                  <Button
                    variant="default"
                    size="sm"
                    @click="emit('open')"
                    class="border-2 border-theme-primary font-mono"
                  >
                    <Icon icon="mdi:gift-open" class="h-4 w-4" />
                    Open
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Open lunchbox</TooltipContent>
              </Tooltip>
              <Tooltip v-if="isActionable">
                <TooltipTrigger as-child>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="emit('sell')"
                    class="border-2 border-(--color-caps) font-mono text-(--color-caps) hover:bg-(--color-caps)/20 hover:text-(--color-caps)"
                  >
                    <Icon icon="mdi:cash" class="h-4 w-4" />
                    Sell
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{{ count > 1 ? 'Sell one' : 'Sell' }}</TooltipContent>
              </Tooltip>
              <Tooltip v-if="itemType !== 'junk' && isActionable">
                <TooltipTrigger as-child>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="emit('scrap')"
                    class="border-2 border-danger/60 font-mono text-danger hover:bg-danger/15 hover:text-danger"
                  >
                    <Icon icon="mdi:hammer-wrench" class="h-4 w-4" />
                    Scrap
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Scrap</TooltipContent>
              </Tooltip>
              <Tooltip v-if="showSellAll">
                <TooltipTrigger as-child>
                  <Button
                    variant="default"
                    size="sm"
                    @click="emit('sellAll')"
                    class="border-2 border-(--color-caps) bg-(--color-caps)/20 font-mono text-(--color-caps) hover:bg-(--color-caps)/30"
                  >
                    <Icon icon="mdi:cash-multiple" class="h-4 w-4" />
                    Sell all
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Sell all ({{ count }})</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </template>
    </ItemCard>
  </Card>
</template>
