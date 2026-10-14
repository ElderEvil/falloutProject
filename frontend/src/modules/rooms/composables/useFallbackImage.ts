import { computed, ref, watch } from 'vue'

/**
 * Resolves the first candidate image URL that has not failed to load, falling
 * back down the list; returns null once every candidate has failed. Failed
 * state resets whenever the candidate URLs change.
 *
 * Shared by the room preview, incident backdrop and grid cell so a broken
 * curated scene degrades to the configured room sprite and then to no image.
 * Pass a getter so each caller's reactive URLs are tracked.
 */
export function useFallbackImage(candidates: () => Array<string | null | undefined>) {
  const failed = ref<string[]>([])
  watch(candidates, () => {
    failed.value = []
  })
  const url = computed(
    () => candidates().find((candidate) => candidate && !failed.value.includes(candidate)) ?? null
  )
  const onError = () => {
    if (url.value) failed.value.push(url.value)
  }
  return { url, onError }
}
