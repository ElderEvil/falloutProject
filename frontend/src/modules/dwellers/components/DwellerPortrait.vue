<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
  preferThumbnail?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  imageUrl: null,
  thumbnailUrl: null,
  imageClass: '',
  fallbackClass: '',
  fallbackIcon: 'mdi:account',
  urlMode: 'normalized',
  preferThumbnail: false,
})

const portraitSource = computed(() =>
  props.preferThumbnail ? props.thumbnailUrl || props.imageUrl : props.imageUrl || props.thumbnailUrl
)
const portraitUrl = computed(() => {
  return props.urlMode === 'static'
    ? (getStaticImageUrl(portraitSource.value) ?? '')
    : normalizeImageUrl(portraitSource.value)
})
const isThumbnailPreview = computed(() => portraitSource.value === props.thumbnailUrl && Boolean(props.thumbnailUrl))

const hasImageError = ref(false)

watch(portraitUrl, () => {
  hasImageError.value = false
})
</script>

<template>
  <img
    v-if="portraitUrl && !hasImageError"
    :src="portraitUrl"
    :alt="alt"
    :class="imageClass"
    :style="{ objectPosition: isThumbnailPreview ? 'center top' : undefined }"
    @error="hasImageError = true"
  />
  <span v-else role="img" :aria-label="alt">
    <Icon :icon="fallbackIcon" :ariaHidden="true" :class="fallbackClass" />
  </span>
</template>
