import { computed, ref, watch } from 'vue'
import { getStaticImageUrl } from '@/core/utils/image'

/**
 * Resolves an item image URL with error fallback: returns null when the image
 * is missing or failed to load (so callers can render an icon instead), and
 * resets the error state whenever the source URL changes.
 */
export function useItemImage(imageUrl: () => string | null | undefined) {
  const imageError = ref(false)

  watch(imageUrl, () => {
    imageError.value = false
  })

  const resolvedUrl = computed(() => (imageError.value ? null : getStaticImageUrl(imageUrl())))

  const onImageError = () => {
    imageError.value = true
  }

  return { imageUrl: resolvedUrl, onImageError }
}
