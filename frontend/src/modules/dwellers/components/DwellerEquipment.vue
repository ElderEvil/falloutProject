<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useEquipmentStore } from '@/modules/combat/stores/equipment'
import { useAuthStore } from '@/modules/auth/stores/auth'
import EquipmentCard from '@/modules/combat/components/equipment/EquipmentCard.vue'
import UModal from '@/core/components/ui/UModal.vue'
import { useDwellerDetailContext } from './DwellerDetailContext'

const ctx = useDwellerDetailContext()

const equipmentStore = useEquipmentStore()
const authStore = useAuthStore()

const dweller = computed(() => ctx.dweller.value)
const vaultId = computed(() => ctx.vaultId.value)

const showInventoryModal = ref(false)
const inventoryMode = ref<'weapon' | 'outfit'>('weapon')

// Get equipped items from the dweller object
const equippedWeapon = computed(() => dweller.value?.weapon ?? null)
const equippedOutfit = computed(() => dweller.value?.outfit ?? null)

// Get available (unequipped) items
const availableWeapons = computed(() => equipmentStore.getAvailableWeapons())
const availableOutfits = computed(() => equipmentStore.getAvailableOutfits())

onMounted(async () => {
  if (authStore.token && vaultId.value) {
    await equipmentStore.fetchWeapons(authStore.token, vaultId.value)
    await equipmentStore.fetchOutfits(authStore.token, vaultId.value)
  } else {
    if (authStore.token) {
      await equipmentStore.fetchWeapons(authStore.token)
      await equipmentStore.fetchOutfits(authStore.token)
    }
  }
})

const handleUnequipWeapon = async () => {
  if (!equippedWeapon.value || !authStore.token || !dweller.value?.id) return
  await equipmentStore.unequipWeapon(dweller.value.id, equippedWeapon.value.id, authStore.token)
  ctx.actions.refresh()
}

const handleUnequipOutfit = async () => {
  if (!equippedOutfit.value || !authStore.token || !dweller.value?.id) return
  await equipmentStore.unequipOutfit(dweller.value.id, equippedOutfit.value.id, authStore.token)
  ctx.actions.refresh()
}

const handleEquipWeapon = async (weaponId: string) => {
  if (!authStore.token || !dweller.value?.id) return
  await equipmentStore.equipWeapon(dweller.value.id, weaponId, authStore.token)
  showInventoryModal.value = false
  ctx.actions.refresh()
}

const handleEquipOutfit = async (outfitId: string) => {
  if (!authStore.token || !dweller.value?.id) return
  await equipmentStore.equipOutfit(dweller.value.id, outfitId, authStore.token)
  showInventoryModal.value = false
  ctx.actions.refresh()
}

const openWeaponInventory = () => {
  inventoryMode.value = 'weapon'
  showInventoryModal.value = true
}

const openOutfitInventory = () => {
  inventoryMode.value = 'outfit'
  showInventoryModal.value = true
}

const modalTitle = computed(() =>
  inventoryMode.value === 'weapon' ? 'Select Weapon' : 'Select Outfit'
)
const modalIcon = computed(() =>
  inventoryMode.value === 'weapon' ? 'mdi:pistol' : 'mdi:tshirt-crew'
)
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

        <EquipmentCard
          v-if="equippedWeapon"
          :item="equippedWeapon"
          type="weapon"
          :equipped="true"
          :show-actions="true"
          @unequip="handleUnequipWeapon"
        />

        <button
          v-else
          type="button"
          class="empty-slot"
          @click="openWeaponInventory"
        >
          <Icon icon="mdi:plus-circle" class="empty-icon" />
          <p class="empty-text">Click to equip weapon</p>
        </button>
      </div>

      <!-- Outfit Slot -->
      <div class="equipment-slot">
        <div class="slot-header">
          <Icon icon="mdi:tshirt-crew" class="slot-icon" />
          <h4 class="slot-title">Outfit</h4>
        </div>

        <EquipmentCard
          v-if="equippedOutfit"
          :item="equippedOutfit"
          type="outfit"
          :equipped="true"
          :show-actions="true"
          @unequip="handleUnequipOutfit"
        />

        <button
          v-else
          type="button"
          class="empty-slot"
          @click="openOutfitInventory"
        >
          <Icon icon="mdi:plus-circle" class="empty-icon" />
          <p class="empty-text">Click to equip outfit</p>
        </button>
      </div>
    </div>

    <!-- Inventory Modal -->
    <UModal v-model="showInventoryModal" :title="modalTitle" size="wide">
      <template #header="{ titleId }">
        <h3 :id="titleId" class="modal-title">
          <Icon :icon="modalIcon" />
          {{ modalTitle }}
        </h3>
      </template>

      <div class="items-list pt-5">
        <template v-if="inventoryMode === 'weapon'">
          <EquipmentCard
            v-for="weapon in availableWeapons"
            :key="weapon.id"
            :item="weapon"
            type="weapon"
            :show-actions="true"
            @equip="handleEquipWeapon(weapon.id)"
          />
          <div v-if="availableWeapons.length === 0" class="empty-state">
            <Icon icon="mdi:package-variant" class="empty-state-icon" />
            <p>No weapons available</p>
          </div>
        </template>

        <template v-else>
          <EquipmentCard
            v-for="outfit in availableOutfits"
            :key="outfit.id"
            :item="outfit"
            type="outfit"
            :show-actions="true"
            @equip="handleEquipOutfit(outfit.id)"
          />
          <div v-if="availableOutfits.length === 0" class="empty-state">
            <Icon icon="mdi:package-variant" class="empty-state-icon" />
            <p>No outfits available</p>
          </div>
        </template>
      </div>
    </UModal>
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
  opacity: 0.8;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
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

.modal-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 2rem 1rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  border: 1px dashed var(--color-theme-glow);
  border-radius: 4px;
}

.empty-state-icon {
  width: 2.5rem;
  height: 2.5rem;
}

</style>
