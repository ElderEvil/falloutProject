<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { getItemIcon, type ItemIconSource } from '@/core/models/items'
import { useItemImage } from '@/core/composables/useItemImage'

interface Props {
  item: ItemIconSource
  itemType: string
  imgClass?: string
  iconClass?: string
  alt?: string
}

const {
  item,
  itemType,
  imgClass = 'h-16 w-16 object-contain',
  iconClass = 'h-16 w-16 text-theme-primary',
  alt,
} = defineProps<Props>()

const itemIcon = computed(() => getItemIcon(itemType, item))

const { imageUrl, onImageError } = useItemImage(() => item.image_url)
</script>

<template>
  <img
    v-if="imageUrl"
    :src="imageUrl"
    :alt="alt ?? item.name ?? 'Unknown Item'"
    :class="imgClass"
    @error="onImageError"
  />
  <Icon v-else :icon="itemIcon" :class="iconClass" />
</template>
