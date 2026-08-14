<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { Weapon, Outfit } from '@/modules/combat/models/equipment'
import { getRarityColor, getDamageRange, getOutfitBonuses } from '@/modules/combat/models/equipment'
import { getStaticImageUrl } from '@/core/utils/image'

interface Props {
  item: Weapon | Outfit
  type: 'weapon' | 'outfit'
  showActions?: boolean
  equipped?: boolean
}

const { showActions = false, equipped = false, item, type } = defineProps<Props>()

const emit = defineEmits<{
  (e: 'equip'): void
  (e: 'unequip'): void
}>()

const rarityColor = computed(() => getRarityColor(item.rarity))

const itemIcon = computed(() => {
  if (type === 'weapon') {
    const w = item as Weapon
    switch (w.weapon_subtype) {
      case 'pistol':
        return 'mdi:pistol'
      case 'rifle':
        return 'mdi:rifle'
      case 'shotgun':
        return 'mdi:shotgun'
      case 'automatic':
        return 'mdi:rifle'
      case 'explosive':
        return 'mdi:bomb'
      case 'flamer':
        return 'mdi:fire'
      case 'edged':
        return 'mdi:sword'
      case 'blunt':
        return 'mdi:hammer'
      case 'pointed':
        return 'mdi:spear'
      default:
        return 'mdi:pistol'
    }
  }
  const o = item as Outfit
  switch (o.outfit_type) {
    case 'common_outfit':
      return 'mdi:tshirt-crew'
    case 'rare_outfit':
      return 'mdi:hard-hat'
    case 'legendary_outfit':
      return 'mdi:shield'
    case 'power_armor':
      return 'mdi:robot'
    case 'tiered_outfit':
      return 'mdi:star'
    default:
      return 'mdi:tshirt-crew'
  }
})

const damageRange = computed(() => (type === 'weapon' ? getDamageRange(item as Weapon) : ''))

const bonuses = computed(() => (type === 'outfit' ? getOutfitBonuses(item as Outfit) : []))

const itemTypeLabel = computed(() =>
  type === 'weapon' ? (item as Weapon).weapon_subtype : (item as Outfit).outfit_type
)

const imageError = ref(false)

watch(
  () => item.image_url,
  () => {
    imageError.value = false
  },
)

const itemImageUrl = computed(() => {
  if (imageError.value || !item.image_url) {
    return ''
  }
  return getStaticImageUrl(item.image_url)
})

function onImageError() {
  imageError.value = true
}
</script>

<template>
  <div
    class="equipment-card"
    :class="[
      'flex flex-col gap-3 rounded-lg border-2 p-4 transition-all duration-200',
      equipped
        ? 'border-[var(--color-theme-primary)] bg-black/50 shadow-[0_0_12px_var(--color-theme-glow)]'
        : 'border-[var(--color-theme-glow)] bg-black/30 hover:border-[var(--color-theme-primary)] hover:bg-black/50 hover:-translate-y-0.5 hover:shadow-[0_4px_12px_var(--color-theme-glow)]',
    ]"
  >
    <div class="flex items-center gap-3">
      <img
        v-if="itemImageUrl"
        :src="itemImageUrl"
        :alt="item.name"
        class="h-16 w-16 object-contain"
        @error="onImageError"
      />
      <Icon v-else :icon="itemIcon" class="h-16 w-16 text-[var(--color-theme-primary)]" />
      <div class="flex-1">
        <h4 class="text-lg font-bold text-shadow-[0_0_4px_currentColor]" :style="{ color: rarityColor }">
          {{ item.name }}
        </h4>
        <p class="text-xs capitalize text-[var(--color-theme-primary)] opacity-70">
          {{ itemTypeLabel }} • {{ item.rarity }}
        </p>
      </div>
    </div>

    <p class="text-sm leading-snug text-[var(--color-theme-primary)] opacity-80">{{ item.description }}</p>

    <div v-if="type === 'weapon'" class="flex flex-col gap-2 rounded bg-black/30 p-3">
      <div class="flex items-center gap-2 text-sm">
        <Icon icon="mdi:sword-cross" class="h-4 w-4 text-[var(--color-theme-primary)]" />
        <span class="text-[var(--color-theme-primary)] opacity-70">Damage:</span>
        <span class="ml-auto font-bold text-[var(--color-theme-primary)]">{{ damageRange }}</span>
      </div>
      <div class="flex items-center gap-2 text-sm">
        <Icon icon="mdi:alphabet-latin" class="h-4 w-4 text-[var(--color-theme-primary)]" />
        <span class="text-[var(--color-theme-primary)] opacity-70">Uses:</span>
        <span class="ml-auto font-bold text-[var(--color-theme-primary)]">{{ (item as Weapon).stat }}</span>
      </div>
      <div
        v-if="(item as Weapon).accuracy !== null && (item as Weapon).accuracy !== undefined"
        class="flex items-center gap-2 text-sm"
      >
        <Icon icon="mdi:target" class="h-4 w-4 text-[var(--color-theme-primary)]" />
        <span class="text-[var(--color-theme-primary)] opacity-70">Accuracy:</span>
        <span class="ml-auto font-bold text-[var(--color-theme-primary)]">{{ (item as Weapon).accuracy }}%</span>
      </div>
    </div>

    <div v-else-if="bonuses.length > 0" class="rounded bg-black/30 p-3">
      <div class="mb-2 flex items-center gap-2">
        <Icon icon="mdi:chevron-up" class="h-4 w-4 text-[var(--color-theme-primary)]" />
        <span class="text-sm font-semibold text-[var(--color-theme-primary)] opacity-70">SPECIAL Bonuses:</span>
      </div>
      <div class="flex flex-wrap gap-2">
        <div v-for="bonus in bonuses" :key="bonus.stat" class="flex items-center gap-1 rounded border border-[var(--color-theme-glow)] bg-black/20 px-2 py-1 text-sm">
          <span class="font-semibold text-[var(--color-theme-primary)] opacity-70">{{ bonus.stat }}</span>
          <span class="font-bold text-[var(--color-theme-primary)]">+{{ bonus.bonus }}</span>
        </div>
      </div>
    </div>

    <div v-if="showActions" class="flex gap-2">
      <button
        v-if="!equipped"
        class="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded border-2 border-[var(--color-theme-primary)] bg-black/30 px-4 py-2 text-sm font-semibold text-[var(--color-theme-primary)] transition-all duration-200 hover:bg-black/50 hover:shadow-[0_0_12px_var(--color-theme-glow)]"
        @click="emit('equip')"
      >
        <Icon icon="mdi:check" />
        Equip
      </button>
      <button
        v-else
        class="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded border-2 border-[var(--color-danger)] bg-red-900/30 px-4 py-2 text-sm font-semibold text-[var(--color-danger)] transition-all duration-200 hover:bg-red-900/50 hover:shadow-[0_0_12px_color-mix(in_srgb,var(--color-danger)_40%,transparent)]"
        @click="emit('unequip')"
      >
        <Icon icon="mdi:close" />
        Unequip
      </button>
    </div>
  </div>
</template>
