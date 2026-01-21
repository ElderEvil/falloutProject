<template>
  <div class="component-loader" role="status" aria-live="polite" aria-label="Loading component">
    <div class="loader-content">
      <div class="spinner" aria-hidden="true"></div>
      <p class="loading-text">Loading...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
// Simple loading component for async component loading
</script>

<style scoped>
.component-loader {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 2rem;
}

.loader-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  border-top-color: var(--color-theme-primary, #00ff00);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  color: var(--color-theme-primary, #00ff00);
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0;
}
</style>
