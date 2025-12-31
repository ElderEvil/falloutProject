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
  color: #00ff00;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
  border-bottom: 2px solid rgba(0, 255, 0, 0.3);
  padding-bottom: 0.5rem;
}

.bio-content {
  padding: 1rem;
  background: rgba(0, 255, 0, 0.05);
  border-left: 3px solid #00ff00;
  border-radius: 4px;
}

.bio-text {
  max-width: 70ch;
  line-height: 1.7;
  color: #00ff00;
  font-size: 1rem;
  text-shadow: 0 0 3px rgba(0, 255, 0, 0.4);
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
  color: rgba(0, 255, 0, 0.7);
  font-size: 1rem;
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.3);
}

.placeholder-hint {
  color: rgba(0, 255, 0, 0.5);
  font-size: 0.875rem;
  font-style: italic;
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.2);
}
</style>
