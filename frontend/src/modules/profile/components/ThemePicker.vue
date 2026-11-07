<script setup lang="ts">
import { computed } from 'vue'
import { themes, type ThemeName } from '@/core/composables/useTheme'

interface Props {
  modelValue: ThemeName
}

const props = defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [theme: ThemeName] }>()

const availableThemes = computed(() => Object.values(themes))
</script>

<template>
  <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
    <button
      v-for="theme in availableThemes"
      :key="theme.name"
      type="button"
      class="theme-card"
      :class="{ active: props.modelValue === theme.name }"
      :style="{
        borderColor: theme.colors.primary,
        boxShadow: props.modelValue === theme.name ? `0 0 15px ${theme.colors.glow}` : 'none',
      }"
      :aria-label="`Select ${theme.displayName}`"
      :aria-pressed="props.modelValue === theme.name"
      @click="emit('update:modelValue', theme.name)"
    >
      <div class="theme-preview" :style="{ backgroundColor: theme.colors.primary }"></div>
      <div class="theme-info">
        <h4 class="theme-name" :style="{ color: theme.colors.primary }">
          {{ theme.displayName }}
        </h4>
        <p class="theme-description">{{ theme.description }}</p>
      </div>
    </button>
  </div>
</template>

<style scoped>
.theme-card {
  position: relative;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 4px;
  transition: all 0.3s ease;
  text-align: left;
  cursor: pointer;
}

.theme-card:hover {
  background: rgba(0, 0, 0, 0.5);
}

.theme-card.active {
  background: rgba(0, 0, 0, 0.6);
  border-width: 3px;
}

.theme-preview {
  width: 100%;
  height: 30px;
  border-radius: 2px;
  margin-bottom: 0.5rem;
}

.theme-name {
  font-size: 0.95rem;
  font-weight: bold;
  margin-bottom: 0.125rem;
}

.theme-description {
  font-size: 0.75rem;
  color: color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  line-height: 1.2;
}
</style>
