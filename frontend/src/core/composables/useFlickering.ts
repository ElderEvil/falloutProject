import { useToggle } from '@vueuse/core'

export function useFlickering() {
  const [isFlickering, toggleFlickering] = useToggle(true)

  return {
    isFlickering,
    toggleFlickering
  }
}
