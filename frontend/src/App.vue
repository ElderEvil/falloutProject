<script setup lang="ts">
import { provide } from 'vue'
import DefaultLayout from '@/core/components/layout/DefaultLayout.vue'
import UToastContainer from '@/core/components/ui/UToastContainer.vue'
import { useVisualEffects } from '@/core/composables/useVisualEffects'
import { useTheme } from '@/core/composables/useTheme'
import { useTokenRefresh } from '@/core/composables/useTokenRefresh'
import { useResourceWarnings } from '@/modules/vault/composables/useResourceWarnings'

// Visual effects (replaces old useFlickering)
const visualEffects = useVisualEffects()
const { flickering, scanlines, glowClass } = visualEffects

// Theme system
const { currentTheme, setTheme, availableThemes } = useTheme()

// Token refresh system (auto-refreshes tokens before expiry)
useTokenRefresh()

// Resource warnings system
useResourceWarnings()

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
  <UToastContainer />
</template>
