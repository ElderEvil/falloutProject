<script setup lang="ts">
import { Icon } from '@iconify/vue'
</script>

<template>
  <div class="dweller-equipment">
    <h3 class="equipment-title">Equipment</h3>

    <div class="equipment-placeholder">
      <Icon icon="mdi:hammer-wrench" class="placeholder-icon" />
      <h4 class="placeholder-heading">Coming Soon</h4>
      <p class="placeholder-text">
        Equipment management is under development. Soon you'll be able to:
      </p>
      <ul class="feature-list">
        <li><Icon icon="mdi:pistol" class="feature-icon" /> Equip weapons</li>
        <li><Icon icon="mdi:tshirt-crew" class="feature-icon" /> Change outfits</li>
        <li><Icon icon="mdi:dog" class="feature-icon" /> Assign pets</li>
        <li><Icon icon="mdi:treasure-chest" class="feature-icon" /> Manage inventory</li>
      </ul>

      <div class="mockup-container">
        <div class="mockup-layout">
          <div class="mockup-section">
            <div class="mockup-label">Weapon</div>
            <div class="mockup-slot">
              <Icon icon="mdi:pistol" class="mockup-icon" />
            </div>
          </div>
          <div class="mockup-section">
            <div class="mockup-label">Outfit</div>
            <div class="mockup-slot">
              <Icon icon="mdi:tshirt-crew" class="mockup-icon" />
            </div>
          </div>
          <div class="mockup-section">
            <div class="mockup-label">Pet</div>
            <div class="mockup-slot">
              <Icon icon="mdi:dog" class="mockup-icon" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dweller-equipment {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.equipment-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
  border-bottom: 2px solid rgba(0, 255, 0, 0.3);
  padding-bottom: 0.5rem;
}

.equipment-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
  padding: 3rem 2rem;
  background: rgba(0, 255, 0, 0.03);
  border: 2px dashed rgba(0, 255, 0, 0.3);
  border-radius: 8px;
  text-align: center;
}

.placeholder-icon {
  width: 4rem;
  height: 4rem;
  color: rgba(0, 255, 0, 0.6);
  filter: drop-shadow(0 0 8px rgba(0, 255, 0, 0.4));
}

.placeholder-heading {
  font-size: 1.5rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
}

.placeholder-text {
  color: rgba(0, 255, 0, 0.8);
  font-size: 1rem;
  text-shadow: 0 0 3px rgba(0, 255, 0, 0.4);
  max-width: 50ch;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

.feature-list li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: rgba(0, 255, 0, 0.7);
  font-size: 0.95rem;
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.3);
}

.feature-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: #00ff00;
  filter: drop-shadow(0 0 4px rgba(0, 255, 0, 0.5));
}

.mockup-container {
  width: 100%;
  max-width: 500px;
  margin-top: 1rem;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 6px;
}

.mockup-layout {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.mockup-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: center;
}

.mockup-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgba(0, 255, 0, 0.7);
  text-shadow: 0 0 3px rgba(0, 255, 0, 0.4);
}

.mockup-slot {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  border: 2px dashed rgba(0, 255, 0, 0.3);
  border-radius: 6px;
}

.mockup-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: rgba(0, 255, 0, 0.4);
}
</style>
