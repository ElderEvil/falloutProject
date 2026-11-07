<script setup lang="ts">
import { computed } from 'vue'
import { Button } from '@/core/components/ui/button'
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
    <Button
      v-for="theme in availableThemes"
      :key="theme.name"
      type="button"
      variant="ghost"
      class="flex h-auto w-full flex-col items-stretch justify-start whitespace-normal rounded border-solid bg-black/30 p-3 text-left font-normal transition-colors hover:bg-black/50"
      :class="{
        'border-[3px] bg-black/60': props.modelValue === theme.name,
        'border-2': props.modelValue !== theme.name,
      }"
      :style="{
        borderColor: theme.colors.primary,
        boxShadow: props.modelValue === theme.name ? `0 0 15px ${theme.colors.glow}` : 'none',
      }"
      :aria-label="`Select ${theme.displayName}`"
      :aria-pressed="props.modelValue === theme.name"
      @click="emit('update:modelValue', theme.name)"
    >
      <div
        class="mb-2 h-[30px] w-full rounded-sm"
        :style="{ backgroundColor: theme.colors.primary }"
      ></div>
      <div>
        <h4 class="mb-0.5 text-[0.95rem] font-bold" :style="{ color: theme.colors.primary }">
          {{ theme.displayName }}
        </h4>
        <p class="text-theme-primary/60 text-xs leading-tight">{{ theme.description }}</p>
      </div>
    </Button>
  </div>
</template>
