<script setup lang="ts">
import USkeleton from '@/components/ui/USkeleton.vue'
</script>

<template>
  <div class="dweller-grid-item-skeleton">
    <!-- Thumbnail area -->
    <div class="thumbnail-skeleton">
      <USkeleton width="100%" height="100%" />
    </div>

    <!-- Info section -->
    <div class="info-skeleton">
      <div class="header-skeleton">
        <USkeleton width="120px" height="1rem" />
        <USkeleton width="50px" height="1.25rem" rounded="full" />
      </div>

      <div class="stats-skeleton">
        <USkeleton width="60px" height="0.875rem" />
        <USkeleton width="70px" height="0.875rem" />
        <USkeleton width="80px" height="0.875rem" />
      </div>

      <USkeleton width="100%" height="0.5rem" rounded="full" />
      <USkeleton width="100px" height="0.875rem" />
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
