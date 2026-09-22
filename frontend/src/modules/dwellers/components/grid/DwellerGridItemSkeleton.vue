<script setup lang="ts">
import { Skeleton } from '@/core/components/ui/skeleton'
</script>

<template>
  <div class="dweller-grid-item-skeleton">
    <!-- Thumbnail area -->
    <div class="thumbnail-skeleton">
      <Skeleton style="width: 100%; height: 100%;" />
    </div>

    <!-- Info section -->
    <div class="info-skeleton">
      <div class="header-skeleton">
        <Skeleton style="width: 120px; height: 1rem;" />
        <Skeleton class="rounded-full" style="width: 50px; height: 1.25rem;" />
      </div>

      <div class="stats-skeleton">
        <Skeleton style="width: 60px; height: 0.875rem;" />
        <Skeleton style="width: 70px; height: 0.875rem;" />
        <Skeleton style="width: 80px; height: 0.875rem;" />
      </div>

      <Skeleton class="rounded-full" style="width: 100%; height: 0.5rem;" />
      <Skeleton style="width: 100px; height: 0.875rem;" />
    </div>
  </div>
</template>

<style scoped>
.dweller-grid-item-skeleton {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.thumbnail-skeleton {
  width: 100%;
  height: 150px;
  background: rgba(0, 0, 0, 0.4);
}

.info-skeleton {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.header-skeleton {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-skeleton {
  display: flex;
  gap: 0.75rem;
}
</style>
