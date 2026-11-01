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
  zoom?: boolean
  dead?: boolean
  objectPosition?: string
  scale?: number
}

const props = withDefaults(defineProps<Props>(), {
  imageUrl: null,
  thumbnailUrl: null,
  imageClass: '',
  fallbackClass: '',
  fallbackIcon: 'mdi:account',
  preferThumbnail: false,
  zoom: true,
  dead: false,
  objectPosition: undefined,
  scale: 1,
})

const portraitSource = computed(() =>
  props.preferThumbnail
    ? props.thumbnailUrl || props.imageUrl
    : props.imageUrl || props.thumbnailUrl
)
// Backend static paths (/static/...) must resolve against the API origin;
// data:, blob:, absolute, and schemeless-host URLs pass through unchanged
// (issue #620). normalizeImageUrl repairs the schemeless-hostname legacy case.
const portraitUrl = computed(() => getStaticImageUrl(normalizeImageUrl(portraitSource.value)) ?? '')

const isThumbnailPreview = computed(
  () => portraitSource.value === props.thumbnailUrl && Boolean(props.thumbnailUrl)
)

const isCuratedDefault = computed(() => {
  const source = portraitSource.value
  return (
    Boolean(source) &&
    (source!.startsWith('/static/dweller_images/') ||
      source!.startsWith('/static/dweller_thumbnails/'))
  )
})

const clipClass = computed(() => {
  if (
    /(^|\s)(avatar-image|thumbnail-image|header-avatar-image|size-full)(\s|$)/.test(
      props.imageClass
    ) ||
    props.imageClass.includes('h-full')
  ) {
    return 'portrait-clip-all'
  }
  if (props.imageClass.includes('w-full')) {
    return 'portrait-clip-wide'
  }
  return 'portrait-clip'
})

const imageStyle = computed(() => ({
  objectPosition: props.objectPosition ?? (isThumbnailPreview.value ? 'center top' : undefined),
  '--portrait-scale': String(props.scale),
  transformOrigin: props.scale > 1 ? 'center top' : undefined,
}))

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
      :width="isCuratedDefault ? 150 : undefined"
      :height="isCuratedDefault ? 300 : undefined"
      :class="[
        'portrait-clip-image',
        imageClass,
        {
          'default-portrait-zoom': isCuratedDefault && zoom,
          'dead-portrait-image': dead,
        },
      ]"
      :style="imageStyle"
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
  transform: scale(var(--portrait-scale, 1));
  transform-origin: center bottom;
}

.portrait-clip-image.default-portrait-zoom {
  transform: scale(calc(var(--portrait-scale, 1) * 1.1));
  transform-origin: top center;
}

.dead-portrait-image {
  filter: grayscale(1) brightness(0.4) contrast(1.25);
  opacity: 0.6;
}
</style>
