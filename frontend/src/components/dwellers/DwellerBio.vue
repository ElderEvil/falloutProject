<script setup lang="ts">
interface Props {
  bio?: string | null
  firstName: string
}

defineProps<Props>()
</script>

<template>
  <div class="dweller-bio">
    <h3 class="bio-title">Biography</h3>
    <div class="bio-content">
      <template v-if="bio">
        <p class="bio-text">{{ bio }}</p>
      </template>
      <template v-else>
        <div class="bio-placeholder">
          <p class="placeholder-text">
            No biography available for {{ firstName }} yet.
          </p>
          <p class="placeholder-hint">
            Use the "Generate AI" button to create a unique backstory!
          </p>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dweller-bio {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.bio-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
}

.bio-content {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 3px solid var(--color-theme-primary);
  border-radius: 4px;
}

.bio-text {
  max-width: 70ch;
  line-height: 1.7;
  color: var(--color-theme-primary);
  font-size: 1rem;
  text-shadow: 0 0 3px var(--color-theme-glow);
  white-space: pre-wrap;
}

.bio-placeholder {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  text-align: center;
  padding: 2rem 1rem;
}

.placeholder-text {
  color: var(--color-theme-primary);
  font-size: 1rem;
  text-shadow: 0 0 2px var(--color-theme-glow);
  opacity: 0.7;
}

.placeholder-hint {
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-style: italic;
  text-shadow: 0 0 2px var(--color-theme-glow);
  opacity: 0.5;
}
</style>
