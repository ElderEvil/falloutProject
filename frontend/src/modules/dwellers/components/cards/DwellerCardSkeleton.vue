<script setup lang="ts">
import USkeleton from '@/core/components/ui/USkeleton.vue'
</script>

<template>
  <li class="dweller-card-skeleton">
    <div class="skeleton-content">
      <!-- Avatar -->
      <USkeleton width="3rem" height="3rem" rounded="full" />

      <!-- Info section -->
      <div class="skeleton-info">
        <div class="skeleton-header">
          <USkeleton width="150px" height="1.25rem" />
          <USkeleton width="60px" height="1.5rem" rounded="full" />
        </div>

        <div class="skeleton-details">
          <USkeleton width="80px" height="0.875rem" />
          <USkeleton width="100px" height="0.875rem" />
          <USkeleton width="90px" height="0.875rem" />
        </div>

        <!-- Health bar -->
        <USkeleton width="100%" height="0.5rem" rounded="full" />

        <!-- Room info -->
        <USkeleton width="120px" height="0.875rem" />
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
