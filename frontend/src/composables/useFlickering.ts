import { ref } from 'vue'

export function useFlickering() {
  const isFlickering = ref(true)

  const toggleFlickering = () => {
    isFlickering.value = !isFlickering.value
  }

  return {
    isFlickering,
    toggleFlickering
  }
}
