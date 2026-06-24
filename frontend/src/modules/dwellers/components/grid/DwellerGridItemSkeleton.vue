<script setup lang="ts">
// @nuxt/ui USkeleton globally registered — no import needed
</script>

<template>
  <div class="dweller-grid-item-skeleton">
    <!-- Thumbnail area -->
    <div class="thumbnail-skeleton">
      <USkeleton class="w-full h-full" />
    </div>

    <!-- Info section -->
    <div class="info-skeleton">
      <div class="header-skeleton">
        <USkeleton class="h-4 w-[120px]" />
        <USkeleton class="h-5 w-[50px] rounded-full" />
      </div>

      <div class="stats-skeleton">
        <USkeleton class="h-3.5 w-[60px]" />
        <USkeleton class="h-3.5 w-[70px]" />
        <USkeleton class="h-3.5 w-[80px]" />
      </div>

      <USkeleton class="h-2 w-full rounded-full" />
      <USkeleton class="h-3.5 w-[100px]" />
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
