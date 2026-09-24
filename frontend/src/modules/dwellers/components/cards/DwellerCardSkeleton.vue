<script setup lang="ts">
import { Skeleton } from '@/core/components/ui/skeleton'
</script>

<template>
  <li class="dweller-card-skeleton">
    <div class="skeleton-content">
      <!-- Avatar -->
      <Skeleton class="rounded-full" style="width: 3rem; height: 3rem;" />

      <!-- Info section -->
      <div class="skeleton-info">
        <div class="skeleton-header">
          <Skeleton style="width: 150px; height: 1.25rem;" />
          <Skeleton class="rounded-full" style="width: 60px; height: 1.5rem;" />
        </div>

        <div class="skeleton-details">
          <Skeleton style="width: 80px; height: 0.875rem;" />
          <Skeleton style="width: 100px; height: 0.875rem;" />
          <Skeleton style="width: 90px; height: 0.875rem;" />
        </div>

        <!-- Health bar -->
        <Skeleton class="rounded-full" style="width: 100%; height: 0.5rem;" />

        <!-- Room info -->
        <Skeleton style="width: 120px; height: 0.875rem;" />
      </div>
    </div>
  </li>
</template>

<style scoped>
.dweller-card-skeleton {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgb(from var(--color-theme-primary) r g b / 0.2);
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
