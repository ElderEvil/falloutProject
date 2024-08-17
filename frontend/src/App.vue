<script setup lang="ts">
import { provide } from 'vue'
import DefaultLayout from '@/components/layout/DefaultLayout.vue'
import { useFlickering } from '@/composables/useFlickering'

const { isFlickering, toggleFlickering } = useFlickering()

provide('isFlickering', isFlickering)
provide('toggleFlickering', toggleFlickering)
</script>

<template>
  <DefaultLayout :isFlickering="isFlickering">
    <router-view></router-view>
  </DefaultLayout>
</template>
