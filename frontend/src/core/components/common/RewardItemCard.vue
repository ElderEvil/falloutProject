<script setup lang="ts">
/**
 * RewardItemCard — rarity-styled reward card shared by reveal modals.
 *
 * Renders an item (art via ItemIcon, glyph fallback), a dweller (portrait via
 * the `media` slot, silhouette supplied by the consumer) or a numeric/currency
 * reward (icon glyph in the same media panel, label above value). Rarity drives
 * both the card border and the text colour through the shared item tokens.
 *
 * `core/` may not import `@/modules/` (scripts/check-boundaries.mjs hard-fails
 * that direction), so the dweller portrait and rarity badge are injected by the
 * owning module through the `media` / `badge` slots — the card itself owns only
 * the shell, label, name and rarity styling.
 */
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import ItemIcon from '@/core/components/common/ItemIcon.vue'
import { getRarityBorderClass, getRarityTextClass } from '@/core/models/items'

interface Props {
  name: string
  rarity?: string
  label?: string
  meta?: string
  quantity?: number
  kind?: 'item' | 'dweller' | 'currency'
  itemType?: string
  imageUrl?: string | null
  icon?: string
  layout?: 'tile' | 'row'
}

const {
  name,
  rarity,
  label,
  meta,
  quantity,
  kind = 'item',
  itemType = 'item',
  imageUrl = null,
  icon,
  layout = 'tile',
} = defineProps<Props>()

const cardClass = computed(() => [
  'flex-row gap-0 rounded-lg border bg-surface py-0 shadow-none',
  layout === 'tile' ? 'sm:flex-col' : '',
  getRarityBorderClass(rarity),
])

// Media panel widths differ per kind: the dweller portrait fills a fixed rail,
// the item art stretches full-width once the tile stacks at `sm:`.
const mediaClass = computed(() =>
  kind === 'dweller'
    ? 'grid w-28 shrink-0 place-items-center bg-surface-sunken p-0 sm:w-36'
    : 'grid w-24 shrink-0 place-items-center bg-surface-sunken p-3 sm:h-32 sm:w-full sm:p-4'
)

const headerClass = computed(() =>
  kind === 'dweller'
    ? 'min-w-0 flex-1 content-center gap-2 p-4 sm:p-5'
    : 'min-w-0 flex-1 content-center gap-2 p-3 sm:p-4'
)

const titleClass = computed(() =>
  kind === 'dweller' ? 'break-words text-xl sm:text-2xl' : 'break-words text-sm leading-snug'
)
</script>

<template>
  <Card :class="cardClass">
    <CardContent :class="mediaClass">
      <slot v-if="kind === 'dweller'" name="media" />
      <Icon
        v-else-if="kind === 'currency'"
        :icon="icon ?? 'mdi:gift'"
        class="size-14 text-theme-primary/60 sm:size-16"
      />
      <ItemIcon
        v-else
        :item="{ image_url: imageUrl, name }"
        :item-type="itemType"
        img-class="size-20 object-contain sm:size-24"
        icon-class="size-12 text-theme-primary/60"
      />
    </CardContent>

    <CardHeader :class="headerClass">
      <template v-if="kind === 'dweller'">
        <CardDescription class="flex items-center gap-1.5 text-xs uppercase tracking-wider">
          <Icon icon="mdi:account-plus" class="size-4" />
          {{ label }}
        </CardDescription>
        <CardTitle :class="[titleClass, getRarityTextClass(rarity)]">
          {{ name }}
        </CardTitle>
        <div class="flex">
          <slot name="badge" />
        </div>
        <p v-if="meta" class="text-xs text-muted-foreground">{{ meta }}</p>
      </template>

      <template v-else-if="kind === 'currency'">
        <CardDescription class="text-xs">{{ label }}</CardDescription>
        <CardTitle :class="[titleClass, 'text-theme-primary']">
          {{ name }}
        </CardTitle>
      </template>

      <template v-else>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <CardDescription class="text-xs">{{ label }}</CardDescription>
          <Badge
            v-if="rarity"
            variant="outline"
            class="text-[0.65rem] capitalize"
            :class="[getRarityTextClass(rarity), getRarityBorderClass(rarity)]"
          >
            {{ rarity }}
          </Badge>
          <span v-if="quantity && quantity > 1" class="text-xs text-muted-foreground">
            ×{{ quantity }}
          </span>
        </div>
        <CardTitle :class="[titleClass, getRarityTextClass(rarity)]">
          {{ name }}
        </CardTitle>
      </template>
    </CardHeader>
  </Card>
</template>
