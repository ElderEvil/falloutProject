<template>
  <div class="playground">
    <header class="playground-header">
      <h1 class="playground-title">Incident playground</h1>
      <p class="playground-subtitle">
        UI-only sandbox — dummy dwellers, dummy incidents, no backend. Treatments are disabled in
        preview mode.
      </p>
    </header>

    <p v-if="!isDev" class="playground-note">Playground is available in development builds only.</p>

    <template v-else>
      <section class="playground-section">
        <h2 class="playground-section-title">Alert strip</h2>
        <IncidentAlert :incidents="alertIncidents" @click="openPreview" />
      </section>

      <section class="playground-section">
        <h2 class="playground-section-title">Battle stages</h2>
        <div class="stage-grid">
          <div v-for="entry in showcase" :key="entry.key" class="stage-card">
            <h3 class="stage-card-title">{{ entry.label }}</h3>
            <IncidentStage
              :incident="entry.incident"
              :dwellers="roster"
              :vault-medical="dummyStocks"
              preview
            />
          </div>
        </div>
      </section>

      <section class="playground-section">
        <h2 class="playground-section-title">Full modals</h2>
        <div class="launcher-grid">
          <button
            v-for="entry in showcase"
            :key="entry.key"
            type="button"
            class="launcher-btn"
            @click="openPreview(entry.incident.id)"
          >
            {{ entry.label }}
          </button>
        </div>
      </section>

      <CombatModal
        v-if="selected"
        :incident-id="selected.incident.id"
        :vault-id="vaultId"
        :dwellers="roster"
        :preview-incident="selected.incident"
        :preview-vault-medical="dummyStocks"
        preview
        @close="selected = null"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import CombatModal from '@/modules/combat/components/incidents/CombatModal.vue'
import IncidentAlert from '@/modules/combat/components/incidents/IncidentAlert.vue'
import IncidentStage from '@/modules/combat/components/incidents/IncidentStage.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import {
  IncidentStatus,
  IncidentType,
  type Incident,
  type VaultMedicalStocks,
} from '@/modules/combat/models/incident'

const isDev = import.meta.env.DEV
const vaultId = 'playground-vault'
const dummyStocks: VaultMedicalStocks = { stimpack: 5, radaway: 3 }

const dummyDweller = (overrides: Record<string, unknown>): DwellerShort =>
  ({
    last_name: null,
    thumbnail_url: null,
    level: 5,
    health: 100,
    max_health: 100,
    radiation: 0,
    room_id: null,
    status: 'idle',
    is_adult: true,
    ...overrides,
  }) as unknown as DwellerShort

const roster: DwellerShort[] = [
  dummyDweller({ id: 'dw-nora', first_name: 'Nora', level: 8, room_id: 'room-fire' }),
  dummyDweller({ id: 'dw-hank', first_name: 'Hank', level: 6, health: 40, room_id: 'room-fire' }),
  dummyDweller({ id: 'dw-ada', first_name: 'Ada', level: 4, health: 15, room_id: 'room-raider' }),
  dummyDweller({ id: 'dw-cap', first_name: 'Cap', level: 6, health: 80, radiation: 20, room_id: 'room-raider' }),
  dummyDweller({ id: 'dw-marcus', first_name: 'Marcus', level: 7, radiation: 60, room_id: 'room-scorpion' }),
  dummyDweller({ id: 'dw-ira', first_name: 'Ira', level: 5, health: 70, radiation: 25, room_id: 'room-ghoul' }),
  dummyDweller({ id: 'dw-boone', first_name: 'Boone', level: 9, room_id: 'room-mole' }),
]

const roundEvents = [
  {
    id: 'evt-spawn-1',
    kind: 'spawned',
    message: '💀 Raider Attack detected in Power Generator — difficulty 4/10, ~8 hostiles incoming. Send defenders.',
    data: { difficulty: 4, expected_threat: 8 },
    created_at: '2026-09-05T00:00:00Z',
  },
  {
    id: 'evt-assign-1',
    kind: 'responders_assigned',
    message: 'Nora, Hank responding (2 defender(s)).',
    data: { count: 2, names: ['Nora', 'Hank'] },
    created_at: '2026-09-05T00:00:20Z',
  },
  {
    id: 'evt-round-1',
    kind: 'round',
    message: 'Round: dealt 12 damage (0/8 down); took 4.',
    data: { damage_to_threat: 12, damage_to_dwellers: 4, enemies_defeated: 0, expected_threat: 8 },
    created_at: '2026-09-05T00:00:45Z',
  },
  {
    id: 'evt-round-2',
    kind: 'round',
    message: 'Round: dealt 18 damage (2/8 down); took 7.',
    data: { damage_to_threat: 18, damage_to_dwellers: 7, enemies_defeated: 2, expected_threat: 8 },
    created_at: '2026-09-05T00:01:30Z',
  },
]

const dummyIncident = (type: IncidentType, overrides: Record<string, unknown> = {}): Incident =>
  ({
    id: `preview-${type}`,
    vault_id: vaultId,
    room_id: 'room-1',
    room_name: 'Power Generator',
    status: IncidentStatus.ACTIVE,
    difficulty: 4,
    start_time: '2026-09-05T00:00:00Z',
    end_time: null,
    duration: 120,
    elapsed_time: 45,
    damage_dealt: 12,
    enemies_defeated: 2,
    loot: null,
    rooms_affected: ['room-1'],
    spread_count: 0,
    created_at: '2026-09-05T00:00:00Z',
    updated_at: '2026-09-05T00:00:00Z',
    family: 'intrusion',
    objective: 'defeat',
    progress: { current: 2, target: 8, label: 'Intruders neutralized' },
    risk: { kind: 'breach', rooms_affected: 1 },
    response: { label: 'Send defenders' },
    events: roundEvents,
    type,
    ...overrides,
  }) as unknown as Incident

interface ShowcaseEntry {
  key: string
  label: string
  incident: Incident
}

const showcase: ShowcaseEntry[] = [
  { key: 'raider', label: 'Raider attack', incident: dummyIncident(IncidentType.RAIDER_ATTACK, { room_id: 'room-raider' }) },
  {
    key: 'deathclaw',
    label: 'Deathclaw spreading',
    incident: dummyIncident(IncidentType.DEATHCLAW_ATTACK, {
      room_id: 'room-claw',
      status: IncidentStatus.SPREADING,
      difficulty: 9,
      spread_count: 2,
      rooms_affected: ['room-claw', 'room-2', 'room-3'],
      risk: { kind: 'breach', rooms_affected: 3 },
    }),
  },
  {
    key: 'ghoul',
    label: 'Feral ghoul',
    incident: dummyIncident(IncidentType.FERAL_GHOUL_ATTACK, { room_id: 'room-ghoul', difficulty: 5 }),
  },
  { key: 'radroach', label: 'Radroach infestation', incident: dummyIncident(IncidentType.RADROACH_INFESTATION, { room_id: 'room-roach', difficulty: 2 }) },
  { key: 'mole', label: 'Mole rat attack', incident: dummyIncident(IncidentType.MOLE_RAT_ATTACK, { room_id: 'room-mole', difficulty: 3 }) },
  {
    key: 'scorpion',
    label: 'Radscorpion attack',
    incident: dummyIncident(IncidentType.RADSCORPION_ATTACK, { room_id: 'room-scorpion', difficulty: 6 }),
  },
  {
    key: 'fire',
    label: 'Fire containment',
    incident: dummyIncident(IncidentType.FIRE, {
      room_id: 'room-fire',
      family: 'hazard',
      objective: 'contain',
      progress: { current: 0.4, target: 1, label: 'Fire contained' },
      risk: { kind: 'spread', rooms_affected: 1 },
      response: { label: 'Send responders' },
      events: [
        {
          id: 'evt-fire-1',
          kind: 'containment',
          message: 'Fire containment +20% (40% total, 1 room(s) burning).',
          data: { amount: 0.2, target: 'hazard', total: 40, rooms: 1 },
          created_at: '2026-09-05T00:01:00Z',
        },
      ],
    }),
  },
  {
    key: 'resolved',
    label: 'Resolved with loot',
    incident: dummyIncident(IncidentType.RAIDER_ATTACK, {
      id: 'preview-resolved',
      room_id: 'room-raider',
      status: IncidentStatus.RESOLVED,
      end_time: '2026-09-05T00:05:00Z',
      enemies_defeated: 8,
      progress: { current: 8, target: 8, label: 'Intruders neutralized' },
      loot: {
        caps: 250,
        items: [{ type: 'weapon', name: 'Rusty Laser Pistol', rarity: 'rare', quantity: 1 }],
      },
    }),
  },
  {
    key: 'failed',
    label: 'Failed deathclaw',
    incident: dummyIncident(IncidentType.DEATHCLAW_ATTACK, {
      id: 'preview-failed',
      room_id: 'room-claw',
      status: IncidentStatus.FAILED,
      end_time: '2026-09-05T00:06:00Z',
      damage_dealt: 180,
    }),
  },
]

const alertIncidents = computed(() =>
  showcase
    .filter((entry) => entry.incident.status === IncidentStatus.ACTIVE || entry.incident.status === IncidentStatus.SPREADING)
    .map((entry) => entry.incident)
)

const selected = ref<ShowcaseEntry | null>(null)

function openPreview(incidentId: string) {
  selected.value = showcase.find((entry) => entry.incident.id === incidentId) ?? null
}
</script>

<style scoped>
.playground {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

.playground-title {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  letter-spacing: 0.05em;
  margin: 0;
}

.playground-subtitle,
.playground-note {
  font-size: 0.875rem;
  color: var(--color-gray-400);
  margin: 0.25rem 0 0;
}

.playground-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.playground-section-title {
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  margin: 0;
}

.stage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 0.75rem;
}

.stage-card {
  padding: 0.75rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 8px;
}

.stage-card-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-gray-400);
  margin: 0 0 0.5rem;
}

.launcher-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.launcher-btn {
  padding: 0.5rem 0.9rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  color: var(--color-theme-primary);
  font: inherit;
  font-size: 0.8rem;
  cursor: pointer;
}

.launcher-btn:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-theme-primary);
}
</style>
