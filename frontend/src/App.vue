<script setup lang="ts">
import { provide } from 'vue'
import DefaultLayout from '@/components/layout/DefaultLayout.vue'
import UNotificationContainer from '@/components/ui/UNotificationContainer.vue'
import UToastContainer from '@/components/ui/UToastContainer.vue'
import { useFlickering } from '@/composables/useFlickering'
import { useTheme } from '@/composables/useTheme'

const { isFlickering, toggleFlickering } = useFlickering()
const { currentTheme, setTheme, availableThemes } = useTheme()

provide('isFlickering', isFlickering)
provide('toggleFlickering', toggleFlickering)
provide('currentTheme', currentTheme)
provide('setTheme', setTheme)
provide('availableThemes', availableThemes)
</script>

<template>
  <DefaultLayout :isFlickering="isFlickering">
    <router-view></router-view>
  </DefaultLayout>
  <UNotificationContainer />
  <UToastContainer />
</template>
