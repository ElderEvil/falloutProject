<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useEquipmentStore } from '@/stores/equipment'
import { useAuthStore } from '@/stores/auth'
import WeaponCard from '@/components/equipment/WeaponCard.vue'
import OutfitCard from '@/components/equipment/OutfitCard.vue'
import type { Dweller } from '@/models/dweller'

interface Props {
  dweller: Dweller
}

const props = defineProps<Props>()
const emit = defineEmits<{
  refresh: []
}>()

const equipmentStore = useEquipmentStore()
const authStore = useAuthStore()

const showInventoryModal = ref(false)
const inventoryTab = ref<'weapons' | 'outfits'>('weapons')

// Get equipped items from the dweller object
const equippedWeapon = computed(() => props.dweller?.weapon ?? null)
const equippedOutfit = computed(() => props.dweller?.outfit ?? null)

// Get available (unequipped) items
const availableWeapons = computed(() => equipmentStore.getAvailableWeapons())
const availableOutfits = computed(() => equipmentStore.getAvailableOutfits())

onMounted(async () => {
  if (authStore.token) {
    await equipmentStore.fetchWeapons(authStore.token)
    await equipmentStore.fetchOutfits(authStore.token)
  }
})

const handleUnequipWeapon = async () => {
  if (!equippedWeapon.value || !authStore.token || !props.dweller?.id) return
  await equipmentStore.unequipWeapon(props.dweller.id, equippedWeapon.value.id, authStore.token)
  emit('refresh')
}

const handleUnequipOutfit = async () => {
  if (!equippedOutfit.value || !authStore.token || !props.dweller?.id) return
  await equipmentStore.unequipOutfit(props.dweller.id, equippedOutfit.value.id, authStore.token)
  emit('refresh')
}

const handleEquipWeapon = async (weaponId: string) => {
  if (!authStore.token || !props.dweller?.id) return
  await equipmentStore.equipWeapon(props.dweller.id, weaponId, authStore.token)
  showInventoryModal.value = false
  emit('refresh')
}

const handleEquipOutfit = async (outfitId: string) => {
  if (!authStore.token || !props.dweller?.id) return
  await equipmentStore.equipOutfit(props.dweller.id, outfitId, authStore.token)
  showInventoryModal.value = false
  emit('refresh')
}

const openInventory = (tab: 'weapons' | 'outfits') => {
  inventoryTab.value = tab
  showInventoryModal.value = true
}
</script>

<template>
  <div class="dweller-equipment">
    <h3 class="equipment-title">Equipment</h3>

    <div class="equipment-grid">
      <!-- Weapon Slot -->
      <div class="equipment-slot">
        <div class="slot-header">
          <Icon icon="mdi:pistol" class="slot-icon" />
          <h4 class="slot-title">Weapon</h4>
        </div>

        <WeaponCard
          v-if="equippedWeapon"
          :weapon="equippedWeapon"
          :equipped="true"
          :show-actions="true"
          @unequip="handleUnequipWeapon"
        />

        <div v-else class="empty-slot" @click="openInventory('weapons')">
          <Icon icon="mdi:plus-circle" class="empty-icon" />
          <p class="empty-text">Click to equip weapon</p>
        </div>
      </div>

      <!-- Outfit Slot -->
      <div class="equipment-slot">
        <div class="slot-header">
          <Icon icon="mdi:tshirt-crew" class="slot-icon" />
          <h4 class="slot-title">Outfit</h4>
        </div>

        <OutfitCard
          v-if="equippedOutfit"
          :outfit="equippedOutfit"
          :equipped="true"
          :show-actions="true"
          @unequip="handleUnequipOutfit"
        />

        <div v-else class="empty-slot" @click="openInventory('outfits')">
          <Icon icon="mdi:plus-circle" class="empty-icon" />
          <p class="empty-text">Click to equip outfit</p>
        </div>
      </div>
    </div>

    <!-- Inventory Modal -->
    <Teleport to="body">
      <div v-if="showInventoryModal" class="modal-overlay" @click="showInventoryModal = false">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              <Icon :icon="inventoryTab === 'weapons' ? 'mdi:pistol' : 'mdi:tshirt-crew'" />
              {{ inventoryTab === 'weapons' ? 'Select Weapon' : 'Select Outfit' }}
            </h3>
            <button @click="showInventoryModal = false" class="close-btn">
              <Icon icon="mdi:close" />
            </button>
          </div>

          <div class="modal-tabs">
            <button
              :class="['tab-btn', { active: inventoryTab === 'weapons' }]"
              @click="inventoryTab = 'weapons'"
            >
              <Icon icon="mdi:pistol" />
              Weapons ({{ availableWeapons.length }})
            </button>
            <button
              :class="['tab-btn', { active: inventoryTab === 'outfits' }]"
              @click="inventoryTab = 'outfits'"
            >
              <Icon icon="mdi:tshirt-crew" />
              Outfits ({{ availableOutfits.length }})
            </button>
          </div>

          <div class="modal-body">
            <!-- Weapons List -->
            <div v-if="inventoryTab === 'weapons'" class="items-grid">
              <WeaponCard
                v-for="weapon in availableWeapons"
                :key="weapon.id"
                :weapon="weapon"
                :show-actions="true"
                @equip="handleEquipWeapon(weapon.id)"
              />
              <div v-if="availableWeapons.length === 0" class="empty-state">
                <Icon icon="mdi:package-variant" class="empty-state-icon" />
                <p>No weapons available</p>
              </div>
            </div>

            <!-- Outfits List -->
            <div v-if="inventoryTab === 'outfits'" class="items-grid">
              <OutfitCard
                v-for="outfit in availableOutfits"
                :key="outfit.id"
                :outfit="outfit"
                :show-actions="true"
                @equip="handleEquipOutfit(outfit.id)"
              />
              <div v-if="availableOutfits.length === 0" class="empty-state">
                <Icon icon="mdi:package-variant" class="empty-state-icon" />
                <p>No outfits available</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
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
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
}

.equipment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}

.equipment-slot {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slot-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.slot-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-theme-primary);
}

.slot-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.empty-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.empty-slot:hover {
  border-color: var(--color-theme-primary);
  opacity: 0.6;
  background: rgba(0, 50, 0, 0.3);
  transform: translateY(-2px);
}

.empty-icon {
  width: 3rem;
  height: 3rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.empty-text {
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-size: 0.875rem;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: #0a0a0a;
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  width: 90%;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 40px var(--color-theme-glow);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 2px solid var(--color-theme-glow);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.close-btn {
  background: transparent;
  border: 2px solid var(--color-theme-glow);
  color: var(--color-theme-primary);
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
}

.close-btn:hover {
  background: rgba(0, 128, 0, 0.3);
  border-color: var(--color-theme-primary);
}

.modal-tabs {
  display: flex;
  gap: 0.5rem;
  padding: 1rem 1.5rem 0;
  border-bottom: 2px solid var(--color-theme-glow);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: transparent;
  border: 2px solid transparent;
  border-bottom: none;
  color: var(--color-theme-primary);
  opacity: 0.6;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 4px 4px 0 0;
}

.tab-btn:hover {
  color: var(--color-theme-primary);
  background: var(--color-theme-hover-bg);
}

.tab-btn.active {
  color: var(--color-theme-primary);
  background: var(--color-theme-active-bg);
  border-color: var(--color-theme-glow);
  border-bottom: 2px solid #0a0a0a;
  margin-bottom: -2px;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 4rem 2rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.empty-state-icon {
  width: 4rem;
  height: 4rem;
}

/* Scrollbar styling */
.modal-body::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb {
  background: var(--color-theme-primary);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: var(--color-theme-accent);
}
</style>
