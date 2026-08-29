import { markRaw, type Component } from 'vue'
import DwellerBio from '../components/DwellerBio.vue'
import DwellerAppearance from '../components/DwellerAppearance.vue'
import DwellerStats from '../components/stats/DwellerStats.vue'
import DwellerEquipment from '../components/DwellerEquipment.vue'
import FamilyTreePanel from '../components/FamilyTreePanel.vue'

export interface DwellerSection {
  key: string
  label: string
  component: Component
}

export const dwellerDetailSections: DwellerSection[] = [
  { key: 'profile', label: 'Profile', component: markRaw(DwellerBio) },
  { key: 'appearance', label: 'Appearance', component: markRaw(DwellerAppearance) },
  { key: 'stats', label: 'Stats', component: markRaw(DwellerStats) },
  { key: 'equipment', label: 'Equipment', component: markRaw(DwellerEquipment) },
  { key: 'family', label: 'Family', component: markRaw(FamilyTreePanel) },
]
