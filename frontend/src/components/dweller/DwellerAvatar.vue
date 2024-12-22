<script setup lang="ts">
import { computed } from 'vue'
import { PersonCircleOutline } from '@vicons/ionicons5'
import type { Dweller } from '@/types/vault'
import { getDwellerFullName } from '@/utils/dwellerUtils'

const props = defineProps<{
  dweller: Dweller
  size?: 'small' | 'medium' | 'large'
  showDefaultIcon?: boolean
}>()

const sizeClass = computed(() => props.size || 'medium')

const hasValidImage = computed(() => {
  return props.dweller.image_url || props.dweller.thumbnail_url
})

const imageUrl = computed(() => {
  if (!hasValidImage.value) return null
  const url = props.size === 'large' ? props.dweller.image_url : props.dweller.thumbnail_url
  return `http://${url}`
})
</script>

<template>
  <div class="dweller-avatar" :class="[sizeClass, { 'has-icon': !hasValidImage }]">
    <img
      v-if="hasValidImage"
      :src="imageUrl"
      :alt="getDwellerFullName(dweller)"
      class="avatar-image"
    />
    <PersonCircleOutline v-else-if="showDefaultIcon" class="default-icon" />
    <div v-else class="initials">
      {{
        getDwellerFullName(dweller)
          .split(' ')
          .map((n) => n[0])
          .join('')
      }}
    </div>
  </div>
</template>

<style scoped>
.dweller-avatar {
  border: 1px solid var(--theme-border);
  overflow: hidden;
  transition: border-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 255, 0, 0.05);
}

.dweller-avatar:hover {
  border-color: var(--theme-hover);
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.default-icon {
  width: 70%;
  height: 70%;
  color: var(--theme-text);
  opacity: 0.7;
}

.initials {
  font-family: 'Courier New', monospace;
  font-weight: bold;
  color: var(--theme-text);
  font-size: 1.2em;
  text-shadow: 0 0 8px var(--theme-shadow);
}

.small {
  width: 40px;
  height: 40px;
}

.medium {
  width: 50px;
  height: 50px;
}

.large {
  width: 150px;
  height: 150px;
}

.has-icon {
  background: var(--theme-background);
}
</style>
