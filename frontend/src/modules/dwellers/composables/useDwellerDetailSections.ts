import { markRaw, type Component } from 'vue'
import DwellerBio from '../components/DwellerBio.vue'
import DwellerAppearance from '../components/DwellerAppearance.vue'
import DwellerStats from '../components/stats/DwellerStats.vue'
import DwellerEquipment from '../components/DwellerEquipment.vue'
import DwellerCollectibles from '../components/DwellerCollectibles.vue'
import FamilyTreePanel from '../components/FamilyTreePanel.vue'

export interface DwellerSection {
  key: string
  label: string
  component: Component
}

export const dwellerDetailSections: DwellerSection[] = [
  { key: 'profile', label: 'Profile', component: markRaw(DwellerBio) },
  { key: 'appearance', label: 'Appearance', component: markRaw(DwellerAppearance) },
  { key: 'stats', label: 'SPECIAL', component: markRaw(DwellerStats) },
  { key: 'equipment', label: 'Equipment', component: markRaw(DwellerEquipment) },
  { key: 'collectibles', label: 'Collectibles', component: markRaw(DwellerCollectibles) },
  { key: 'family', label: 'Family', component: markRaw(FamilyTreePanel) },
]
