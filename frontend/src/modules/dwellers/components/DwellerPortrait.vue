<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { getStaticImageUrl, normalizeImageUrl } from '@/core/utils/image'

interface Props {
  imageUrl?: string | null
  thumbnailUrl?: string | null
  alt: string
  imageClass?: string
  fallbackClass?: string
  fallbackIcon?: string
  urlMode?: 'normalized' | 'static'
}

const props = withDefaults(defineProps<Props>(), {
  imageUrl: null,
  thumbnailUrl: null,
  imageClass: '',
  fallbackClass: '',
  fallbackIcon: 'mdi:account',
  urlMode: 'normalized',
})

const portraitUrl = computed(() => {
  const source = props.imageUrl || props.thumbnailUrl
  return props.urlMode === 'static'
    ? (getStaticImageUrl(source) ?? '')
    : normalizeImageUrl(source)
})
</script>

<template>
  <img v-if="portraitUrl" :src="portraitUrl" :alt="alt" :class="imageClass" />
  <span v-else role="img" :aria-label="alt">
    <Icon :icon="fallbackIcon" :ariaHidden="true" :class="fallbackClass" />
  </span>
</template>
