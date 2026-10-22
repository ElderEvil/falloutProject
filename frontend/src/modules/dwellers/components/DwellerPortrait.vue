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
  preferThumbnail?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  imageUrl: null,
  thumbnailUrl: null,
  imageClass: '',
  fallbackClass: '',
  fallbackIcon: 'mdi:account',
  preferThumbnail: false,
})

const portraitSource = computed(() =>
  props.preferThumbnail ? props.thumbnailUrl || props.imageUrl : props.imageUrl || props.thumbnailUrl
)
// Backend static paths (/static/...) must resolve against the API origin;
// data:, blob:, absolute, and schemeless-host URLs pass through unchanged
// (issue #620). normalizeImageUrl repairs the schemeless-hostname legacy case.
const portraitUrl = computed(() => getStaticImageUrl(normalizeImageUrl(portraitSource.value)) ?? '')

const isThumbnailPreview = computed(() => portraitSource.value === props.thumbnailUrl && Boolean(props.thumbnailUrl))

const isCuratedDefault = computed(() => {
  const source = portraitSource.value
  return (
    Boolean(source) &&
    (source!.startsWith('/static/dweller_images/') || source!.startsWith('/static/dweller_thumbnails/'))
  )
})

const clipClass = computed(() => {
  if (/(^|\s)(avatar-image|thumbnail-image|header-avatar-image)(\s|$)/.test(props.imageClass) || props.imageClass.includes('h-full')) {
    return 'portrait-clip-all'
  }
  if (props.imageClass.includes('w-full')) {
    return 'portrait-clip-wide'
  }
  return 'portrait-clip'
})

const hasImageError = ref(false)

watch(portraitUrl, () => {
  hasImageError.value = false
})
</script>

<template>
  <span v-if="portraitUrl && !hasImageError" :class="clipClass">
    <img
      :src="portraitUrl"
      :alt="alt"
      :class="[
        'portrait-clip-image',
        imageClass,
        { 'default-portrait-zoom': isCuratedDefault },
      ]"
      :style="{ objectPosition: isThumbnailPreview ? 'center top' : undefined }"
      @error="hasImageError = true"
    />
  </span>
  <slot v-else-if="$slots.fallback" name="fallback" />
  <span v-else role="img" :aria-label="alt">
    <Icon :icon="fallbackIcon" :ariaHidden="true" :class="fallbackClass" />
  </span>
</template>

<style scoped>
.portrait-clip {
  display: inline-block;
  overflow: hidden;
  vertical-align: middle;
}

.portrait-clip-wide {
  display: block;
  width: 100%;
  overflow: hidden;
}

.portrait-clip-all {
  display: block;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.portrait-clip-image {
  display: block;
}

.portrait-clip-image.default-portrait-zoom {
  transform: scale(1.1);
  transform-origin: top center;
}
</style>
