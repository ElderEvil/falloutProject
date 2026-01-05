<script setup lang="ts">
import { provide } from 'vue'
import DefaultLayout from '@/components/layout/DefaultLayout.vue'
import UNotificationContainer from '@/components/ui/UNotificationContainer.vue'
import UToastContainer from '@/components/ui/UToastContainer.vue'
import { useVisualEffects } from '@/composables/useVisualEffects'
import { useTheme } from '@/composables/useTheme'

// Visual effects (replaces old useFlickering)
const visualEffects = useVisualEffects()
const { flickering, scanlines, glowClass } = visualEffects

// Theme system
const { currentTheme, setTheme, availableThemes } = useTheme()

// Provide visual effects for components that need them
provide('visualEffects', visualEffects)
provide('scanlines', scanlines)
provide('glowClass', glowClass)

// Legacy support for old useFlickering consumers
provide('isFlickering', flickering)
provide('toggleFlickering', visualEffects.toggleFlickering)

// Theme providers
provide('currentTheme', currentTheme)
provide('setTheme', setTheme)
provide('availableThemes', availableThemes)
</script>

<template>
  <DefaultLayout :isFlickering="flickering">
    <router-view></router-view>
  </DefaultLayout>
  <UNotificationContainer />
  <UToastContainer />
</template>
