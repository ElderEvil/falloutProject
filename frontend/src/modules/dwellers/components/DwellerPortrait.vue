<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { normalizeImageUrl } from '@/core/utils/image'

interface Props {
  imageUrl?: string | null
  thumbnailUrl?: string | null
  alt: string
  imageClass?: string
  fallbackClass?: string
}

const props = withDefaults(defineProps<Props>(), {
  imageUrl: null,
  thumbnailUrl: null,
  imageClass: '',
  fallbackClass: '',
})

const portraitUrl = computed(() => normalizeImageUrl(props.imageUrl || props.thumbnailUrl))
</script>

<template>
  <img v-if="portraitUrl" :src="portraitUrl" :alt="alt" :class="imageClass" />
  <span v-else role="img" :aria-label="alt">
    <Icon icon="mdi:account" :ariaHidden="true" :class="fallbackClass" />
  </span>
</template>
