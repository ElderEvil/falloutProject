<script setup lang="ts">
// @nuxt/ui USkeleton globally registered — no import needed
</script>

<template>
  <li class="dweller-card-skeleton">
    <div class="skeleton-content">
      <!-- Avatar -->
      <USkeleton class="h-12 w-12 rounded-full" />

      <!-- Info section -->
      <div class="skeleton-info">
        <div class="skeleton-header">
          <USkeleton class="h-5 w-[150px]" />
          <USkeleton class="h-6 w-[60px] rounded-full" />
        </div>

        <div class="skeleton-details">
          <USkeleton class="h-3.5 w-[80px]" />
          <USkeleton class="h-3.5 w-[100px]" />
          <USkeleton class="h-3.5 w-[90px]" />
        </div>

        <!-- Health bar -->
        <USkeleton class="h-2 w-full rounded-full" />

        <!-- Room info -->
        <USkeleton class="h-3.5 w-[120px]" />
      </div>
    </div>
  </li>
</template>

<style scoped>
.dweller-card-skeleton {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 8px;
  list-style: none;
}

.skeleton-content {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.skeleton-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.skeleton-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skeleton-details {
  display: flex;
  gap: 1rem;
}
</style>
