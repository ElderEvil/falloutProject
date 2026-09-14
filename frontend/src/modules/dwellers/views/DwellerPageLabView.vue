<script setup lang="ts">
import { Icon } from '@iconify/vue'
import DwellerPortrait from '../components/DwellerPortrait.vue'
import DwellerGenderBadge from '../components/DwellerGenderBadge.vue'
import DwellerRarityBadge from '../components/DwellerRarityBadge.vue'
import DwellerAgeBadge from '../components/DwellerAgeBadge.vue'
import DwellerStatusBadge from '../components/stats/DwellerStatusBadge.vue'
import DwellerIdentitySignal from '../components/DwellerIdentitySignal.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import { getHappinessLevel, getHappinessColor, type VisualAttributes } from '../models/dweller'

const identity: VisualAttributes = { race: 'ghoul', faction: 'raiders', state_of_being: 'sane' }

const identityRaces: Array<{ name: string; attributes: VisualAttributes }> = [
  { name: 'Human', attributes: { race: 'human', faction: 'vault_dweller' } },
  { name: 'Ghoul', attributes: { race: 'ghoul', faction: 'raiders', state_of_being: 'feral' } },
  { name: 'Super Mutant', attributes: { race: 'super_mutant', state_of_being: 'behemoth' } },
  {
    name: 'Synth gen I',
    attributes: { race: 'synth', faction: 'the_institute', state_of_being: 'gen_1' },
  },
  {
    name: 'Synth gen III',
    attributes: { race: 'synth', faction: 'railroad', state_of_being: 'gen_3' },
  },
]

const health = 82
const maxHealth = 100
const radiation = 12
const happiness = 64
const level = 12
const levelProgress = 62
const happinessColor = getHappinessColor(getHappinessLevel(happiness))
const effectiveMax = maxHealth - radiation

const special = [
  { key: 'S', label: 'STR', value: 6 },
  { key: 'P', label: 'PER', value: 4 },
  { key: 'E', label: 'END', value: 7 },
  { key: 'C', label: 'CHA', value: 3 },
  { key: 'I', label: 'INT', value: 5 },
  { key: 'A', label: 'AGI', value: 8 },
  { key: 'L', label: 'LCK', value: 2 },
]
</script>

<template>
  <div class="lab">
    <header class="lab-intro">
      <h1 class="lab-title">Dweller detail — V1 vs V1 improved</h1>
      <p class="lab-sub">
        Same shell, same content, same separator (option A, full-width row rule). Both show the
        S.P.E.C.I.A.L. panel so the column depths are directly comparable. Improved applies:
        activity inline with the name, alerts right-aligned on that row, badges moved out of the
        card, tighter rhythm, narrower column gap, no fixed panel height, and the portrait sized to
        run exactly as deep as the stats panel.
      </p>
    </header>

    <!-- ============================ V1 — today ============================ -->
    <section class="variant">
      <div class="variant-meta">
        <span class="variant-label">V1 — Today</span>
        <span class="variant-note">
          Four stacked rows above the content (crumbs, name, activity, alerts), badges parked inside
          the card, a 2rem column gap, and a ratio-preserving portrait (shown vertical at 3:4, as
          game art can be) that runs the column past the panel.
        </span>
      </div>

      <div class="mock-frame">
        <div class="shell baseline">
          <div class="crumb-row">
            <span class="crumb-muted">← Back to Dwellers</span>
            <span class="crumb-muted">Vault / Dwellers / Nora Vance</span>
          </div>

          <div class="identity-row">
            <h2 class="dweller-name">Nora Vance</h2>
            <DwellerStatusBadge status="working" :show-label="true" size="large" />
          </div>
          <span class="activity-caption">Power Generator</span>
          <div class="alert-line">
            <span class="alert-chip warning"
              ><Icon icon="mdi:radiation" class="alert-icon" />Radiated — 12</span
            >
          </div>

          <div class="grid gap-wide">
            <div class="card-col">
              <div class="portrait-box">
                <DwellerPortrait
                  alt="Nora Vance"
                  fallback-class="h-32 w-32 text-theme-primary opacity-30"
                />
              </div>
              <div class="badge-row">
                <DwellerGenderBadge gender="female" :show-label="true" />
                <DwellerRarityBadge rarity="rare" :show-label="true" />
                <DwellerAgeBadge age-group="adult" :show-label="true" />
              </div>
              <div class="vital">
                <span class="vital-label">Level {{ level }}</span>
                <UProgressBar :model-value="levelProgress" :height="8" />
              </div>
              <div class="vital">
                <span class="vital-label">Health</span>
                <span class="vital-value">{{ health }} / {{ effectiveMax }} ({{ maxHealth }})</span>
                <UProgressBar :model-value="health" :radiation="radiation" :height="10" />
              </div>
              <div class="vital">
                <span class="vital-label">Happiness</span>
                <span class="vital-value" :style="{ color: happinessColor }">{{ happiness }}%</span>
                <UProgressBar :model-value="happiness" :height="10" :color="happinessColor" />
              </div>
              <div class="inventory-row">
                <span class="inv-item"
                  ><Icon icon="mdi:medical-bag" class="inv-icon" />2 Stimpack</span
                >
                <span class="inv-item"
                  ><Icon icon="mdi:radiation" class="inv-icon" />1 RadAway</span
                >
              </div>
              <div class="actions stacked">
                <button class="action-btn primary">
                  <Icon icon="mdi:message-text" class="action-icon" />Chat
                </button>
                <button class="action-btn">
                  <Icon icon="mdi:office-building" class="action-icon" />Assign to Room
                </button>
                <button class="action-btn">
                  <Icon icon="mdi:map-marker-radius" class="action-icon" />Send to Wasteland
                </button>
                <button class="action-btn">
                  <Icon icon="mdi:school" class="action-icon" />Train Stats
                </button>
              </div>
            </div>

            <div class="panel-col">
              <div class="panel panel-fixed">
                <div class="lockup row-rule">
                  <h3 class="lockup-title">S.P.E.C.I.A.L.</h3>
                  <span class="lockup-hint">Level 12</span>
                </div>
                <div class="stats">
                  <div v-for="stat in special" :key="stat.key" class="stat">
                    <span class="stat-label">{{ stat.label }}</span>
                    <span class="stat-value">{{ stat.value }}</span>
                    <div class="stat-bar">
                      <div class="stat-fill" :style="{ width: stat.value * 10 + '%' }" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================ V1 improved ============================ -->
    <section class="variant">
      <div class="variant-meta">
        <span class="variant-label">V1 improved — A + B + C + E + F</span>
        <span class="variant-note">
          Two header lines: name + room on top with the alerts, status and the overflow menu; then
          one metadata line holding gender/rarity/age, a divider, and the race/faction/state chips.
          The columns still end level, and the portrait takes its height from the panel so vertical
          art is never squashed.
        </span>
      </div>

      <div class="mock-frame">
        <div class="shell improved">
          <div class="crumb-row">
            <span class="crumb-muted">← Back to Dwellers</span>
            <span class="crumb-muted">Vault / Dwellers / Nora Vance</span>
          </div>

          <div class="header-block">
            <div class="identity-row">
              <div class="name-line">
                <h2 class="dweller-name">Nora Vance</h2>
                <span class="activity-caption">Power Generator</span>
              </div>
              <div class="status-line">
                <span class="alert-chip warning"
                  ><Icon icon="mdi:radiation" class="alert-icon" />Radiated — 12</span
                >
                <DwellerStatusBadge status="working" :show-label="true" size="large" />
                <span class="icon-btn" title="More actions"><Icon icon="mdi:dots-vertical" /></span>
              </div>
            </div>
            <div class="meta-line">
              <span class="badge-cluster">
                <DwellerGenderBadge gender="female" :show-label="true" />
                <DwellerRarityBadge rarity="rare" :show-label="true" />
                <DwellerAgeBadge age-group="adult" :show-label="true" />
              </span>
              <span class="name-divider" aria-hidden="true" />
              <DwellerIdentitySignal :visual-attributes="identity" />
            </div>
          </div>

          <div class="grid gap-tight">
            <div class="card-col">
              <div class="portrait-rail">
                <div class="portrait-box">
                  <DwellerPortrait
                    alt="Nora Vance"
                    fallback-class="h-24 w-24 text-theme-primary opacity-30"
                  />
                </div>
                <div class="rail">
                  <div class="vital">
                    <span class="vital-label">Level {{ level }}</span>
                    <UProgressBar :model-value="levelProgress" :height="8" />
                  </div>
                  <div class="vital">
                    <span class="vital-label">Health</span>
                    <span class="vital-value"
                      >{{ health }} / {{ effectiveMax }} ({{ maxHealth }})</span
                    >
                    <UProgressBar :model-value="health" :radiation="radiation" :height="10" />
                  </div>
                  <div class="vital">
                    <span class="vital-label">Happiness</span>
                    <span class="vital-value" :style="{ color: happinessColor }"
                      >{{ happiness }}%</span
                    >
                    <UProgressBar :model-value="happiness" :height="10" :color="happinessColor" />
                  </div>
                  <div class="inventory-row">
                    <span class="inv-item"
                      ><Icon icon="mdi:medical-bag" class="inv-icon" />2 Stimpack</span
                    >
                    <span class="inv-item"
                      ><Icon icon="mdi:radiation" class="inv-icon" />1 RadAway</span
                    >
                  </div>
                </div>
              </div>
              <div class="actions paired">
                <button class="action-btn primary">
                  <Icon icon="mdi:message-text" class="action-icon" />Chat
                </button>
                <button class="action-btn">
                  <Icon icon="mdi:office-building" class="action-icon" />Assign
                </button>
                <button class="action-btn">
                  <Icon icon="mdi:map-marker-radius" class="action-icon" />Wasteland
                </button>
                <button class="action-btn">
                  <Icon icon="mdi:school" class="action-icon" />Train
                </button>
              </div>
            </div>

            <div class="panel-col">
              <div class="panel">
                <div class="lockup row-rule">
                  <h3 class="lockup-title">S.P.E.C.I.A.L.</h3>
                  <span class="lockup-hint">Level 12</span>
                </div>
                <div class="stats">
                  <div v-for="stat in special" :key="stat.key" class="stat">
                    <span class="stat-label">{{ stat.label }}</span>
                    <span class="stat-value">{{ stat.value }}</span>
                    <div class="stat-bar">
                      <div class="stat-fill" :style="{ width: stat.value * 10 + '%' }" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
    <!-- ==================== header actions placement ==================== -->
    <section class="options-block">
      <div class="variant-meta">
        <span class="variant-label">Header actions — where rename &amp; soft-delete live</span>
        <span class="variant-note">
          They are rare and one of them is destructive, so they should not add noise next to the
          name. Three ways to hold them; the name/badge/activity lockup and divider are identical in
          all three.
        </span>
      </div>

      <div class="mock-frame options-grid">
        <div class="option">
          <span class="option-label">A — Inline after the name (today)</span>
          <div class="identity-row">
            <div class="name-line">
              <h2 class="dweller-name sm">Nora Vance</h2>
              <span class="icon-btn"><Icon icon="mdi:pencil" /></span>
              <span class="icon-btn danger"><Icon icon="mdi:account-remove" /></span>
              <span class="name-divider" aria-hidden="true" />
              <span class="badge-cluster">
                <DwellerGenderBadge gender="female" :show-label="true" />
                <DwellerRarityBadge rarity="rare" :show-label="true" />
              </span>
            </div>
          </div>
          <span class="option-verdict">
            Closest to the thing it acts on, but the danger icon sits beside the name and the row
            grows with every badge.
          </span>
        </div>

        <div class="option">
          <span class="option-label">B — Right cluster beside the status</span>
          <div class="identity-row">
            <div class="name-line">
              <h2 class="dweller-name sm">Nora Vance</h2>
              <span class="name-divider" aria-hidden="true" />
              <span class="badge-cluster">
                <DwellerGenderBadge gender="female" :show-label="true" />
                <DwellerRarityBadge rarity="rare" :show-label="true" />
              </span>
            </div>
            <div class="status-line">
              <span class="icon-btn"><Icon icon="mdi:pencil" /></span>
              <span class="icon-btn danger"><Icon icon="mdi:account-remove" /></span>
              <DwellerStatusBadge status="working" :show-label="true" size="large" />
            </div>
          </div>
          <span class="option-verdict">
            Keeps identity clean and groups management with the other right-edge controls. Two extra
            icons, still always visible.
          </span>
        </div>

        <div class="option chosen">
          <span class="option-label"
            >C — Overflow menu at the right <span class="chosen-tag">Chosen</span></span
          >
          <div class="identity-row">
            <div class="name-line">
              <h2 class="dweller-name sm">Nora Vance</h2>
              <span class="name-divider" aria-hidden="true" />
              <span class="badge-cluster">
                <DwellerGenderBadge gender="female" :show-label="true" />
                <DwellerRarityBadge rarity="rare" :show-label="true" />
              </span>
            </div>
            <div class="status-line">
              <span class="icon-btn"><Icon icon="mdi:dots-vertical" /></span>
              <DwellerStatusBadge status="working" :show-label="true" size="large" />
            </div>
          </div>
          <span class="option-verdict">
            One control instead of two, and destructive actions sit behind a deliberate click. Costs
            a click and a little discoverability. <strong>Applied to the variant above.</strong>
          </span>
        </div>
      </div>
    </section>
    <!-- ==================== identity signal chips ==================== -->
    <section class="options-block">
      <div class="variant-meta">
        <span class="variant-label">Identity chips — race / faction / state of being</span>
        <span class="variant-note">
          Only ghoul, super mutant and synth carry a state of being, so humans show two chips and
          the rest show three. Mutation severity reads as a numeral; synth generations keep the
          robot glyph and name the generation in the label, since "machine" is the useful signal
          there.
        </span>
      </div>

      <div class="mock-frame identity-grid">
        <div v-for="race in identityRaces" :key="race.name" class="identity-row-demo">
          <span class="option-label">{{ race.name }}</span>
          <DwellerIdentitySignal :visual-attributes="race.attributes" />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.lab {
  min-height: 100vh;
  padding: 2rem;
  background: var(--color-terminal-background, #0f0e0d);
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
}

.lab-intro {
  max-width: 62rem;
}

.lab-title {
  font-size: 1.5rem;
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
  margin-bottom: 0.5rem;
}

.lab-sub {
  font-size: 0.875rem;
  opacity: 0.7;
  line-height: 1.6;
}

.variant-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin-bottom: 0.6rem;
}

.variant-label {
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.variant-note {
  font-size: 0.75rem;
  opacity: 0.6;
  line-height: 1.5;
  max-width: 62rem;
}

.mock-frame {
  border: 1px dashed color-mix(in srgb, var(--color-theme-primary) 35%, transparent);
  border-radius: 8px;
  padding: 1rem;
}

.shell {
  max-width: 1180px;
  margin: 0 auto;
}

.crumb-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.crumb-muted {
  font-size: 0.75rem;
  opacity: 0.5;
}

.identity-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.baseline .identity-row {
  margin-bottom: 0.5rem;
}

.baseline .activity-caption {
  display: block;
  margin-bottom: 0.75rem;
}

.baseline .alert-line {
  margin-bottom: 1.5rem;
}

.improved .crumb-row {
  margin-bottom: 0.75rem;
}

.improved .identity-row {
  margin-bottom: 0;
}

.header-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.meta-line {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.name-line {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  min-width: 0;
}

.name-divider {
  width: 1px;
  height: 1.75rem;
  flex-shrink: 0;
  background: color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.badge-cluster {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.dweller-name {
  font-size: 2.25rem;
  font-weight: 700;
  text-shadow: 0 0 10px var(--color-theme-glow);
  margin: 0;
}

.activity-caption {
  font-size: 0.8rem;
  opacity: 0.65;
}

.alert-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.alert-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  border: 1px solid currentColor;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.35);
  font-size: 0.75rem;
  white-space: nowrap;
}

.alert-chip.warning {
  color: var(--color-warning);
}

.alert-icon {
  width: 0.9rem;
  height: 0.9rem;
}

.grid {
  display: grid;
  align-items: start;
  margin-top: 0.25rem;
}

.grid.gap-wide {
  grid-template-columns: 380px minmax(0, 1fr);
  gap: 2rem;
}

.grid.gap-tight {
  grid-template-columns: minmax(320px, 350px) minmax(0, 1fr);
  gap: 1.5rem;
}

/* Improved: two columns that end level. The portrait keeps its ratio but takes
   its height from the panel, and the data that used to stack below it moves
   into the width the vertical portrait leaves free beside it. */
.improved .grid {
  align-items: stretch;
}

.improved .card-col {
  height: 100%;
}

.portrait-rail {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-height: 0;
}

.rail {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.6rem;
  min-width: 0;
  flex: 1;
}

.inventory-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.inv-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  opacity: 0.75;
}

.inv-icon {
  width: 0.9rem;
  height: 0.9rem;
}

.actions {
  display: grid;
  gap: 0.5rem;
}

.actions.stacked {
  grid-template-columns: 1fr;
}

.actions.paired {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.4rem 0.6rem;
  background: transparent;
  border: 1px solid var(--color-theme-primary);
  border-radius: 4px;
  color: var(--color-theme-primary);
  font-family: inherit;
  font-size: 0.75rem;
  cursor: pointer;
  white-space: nowrap;
}

.action-btn:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}

.action-btn.primary {
  background: color-mix(in srgb, var(--color-theme-primary) 14%, transparent);
}

.action-icon {
  width: 0.9rem;
  height: 0.9rem;
  flex-shrink: 0;
}

.options-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.5rem;
}

.identity-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.identity-row-demo {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.identity-row-demo .option-label {
  min-width: 8rem;
}

.option {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.option-label {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.option.chosen {
  border-left: 2px solid var(--color-theme-primary);
  padding-left: 0.9rem;
}

.chosen-tag {
  margin-left: 0.4rem;
  padding: 0.05rem 0.4rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 999px;
  font-size: 0.6rem;
  letter-spacing: 0.08em;
  opacity: 0.85;
}

.option-verdict {
  font-size: 0.72rem;
  opacity: 0.6;
  line-height: 1.5;
}

.dweller-name.sm {
  font-size: 1.5rem;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  border-radius: 4px;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.icon-btn.danger {
  color: var(--color-danger);
  border-color: color-mix(in srgb, var(--color-danger) 40%, transparent);
}

.icon-btn :deep(svg) {
  width: 1rem;
  height: 1rem;
}

.card-col {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.portrait-box {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.35);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

/* Today: the portrait keeps its own ratio, so a vertical one drives the column
   as deep as the art wants and the two columns end unevenly. */
.baseline .portrait-box {
  width: 100%;
  max-width: 300px;
  margin: 0 auto;
  aspect-ratio: 3 / 4;
}

/* Improved: the portrait shares the row with the data rail, so it is a vertical
   slice of the column rather than a full-width hero. Height follows from the
   ratio, and the rail fills the width the vertical portrait leaves free. */
.improved .portrait-box {
  flex: 1 1 0;
  min-height: 8rem;
  aspect-ratio: 3 / 4;
  align-self: center;
}

.badge-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.vital {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.vital-label {
  font-size: 0.75rem;
  opacity: 0.7;
}

.vital-value {
  font-size: 0.85rem;
  font-weight: 700;
}

.panel {
  padding: 1.25rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.panel-fixed {
  min-height: 400px;
}

.lockup {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.lockup.row-rule {
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}

.lockup-title {
  font-size: 1.25rem;
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
  margin: 0;
}

.lockup-hint {
  font-size: 0.75rem;
  opacity: 0.55;
}

.stats {
  display: grid;
  gap: 0.6rem;
}

.stat {
  display: grid;
  grid-template-columns: 3rem 2rem minmax(0, 1fr);
  align-items: center;
  gap: 0.6rem;
}

.stat-label {
  font-size: 0.75rem;
  opacity: 0.7;
}

.stat-value {
  font-size: 0.85rem;
  font-weight: 700;
}

.stat-bar {
  height: 8px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  overflow: hidden;
}

.stat-fill {
  height: 100%;
  background: var(--color-theme-primary);
}
</style>
