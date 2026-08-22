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
  return props.urlMode === 'static' ? (getStaticImageUrl(source) ?? '') : normalizeImageUrl(source)
})

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
    @error="hasImageError = true"
  />
  <span v-else role="img" :aria-label="alt">
    <Icon :icon="fallbackIcon" :ariaHidden="true" :class="fallbackClass" />
  </span>
</template>
