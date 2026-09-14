<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Variant {
  key: string
  label: string
  note: string
}

const variants: Variant[] = [
  {
    key: 'row-rule',
    label: 'A — Row rule',
    note: 'Full-width rule under the whole header row. What Biography and Appearance do today.',
  },
  {
    key: 'title-underline',
    label: 'B — Title underline',
    note: 'Rule hugs the title text only. What .panel-title does today.',
  },
  {
    key: 'plain',
    label: 'C — No rule',
    note: 'Typography carries the break: size, weight, glow, then breathing room.',
  },
  {
    key: 'bracket',
    label: 'D — Bracketed title',
    note: 'Terminal styling without a rule. Reads as an indicator, not a divider.',
  },
  {
    key: 'accent',
    label: 'E — Left accent',
    note: 'Vertical accent matches the panel body treatment already used by Appearance.',
  },
  {
    key: 'bar',
    label: 'F — Filled bar',
    note: 'Edge-to-edge fill with a hairline. Strongest separation, heaviest visually.',
  },
]
</script>

<template>
  <div class="lab">
    <header class="lab-intro">
      <h1 class="lab-title">Panel header lockup — variants</h1>
      <p class="lab-sub">
        Separator treatment for the dweller detail tabs (Profile, Appearance, Stats, Equipment,
        Family). Each mock panel is sized like the real right-hand panel, with a header action and
        body copy so rule weight and the gap under it can be judged in context.
      </p>
    </header>

    <div class="lab-grid">
      <section v-for="variant in variants" :key="variant.key" class="variant">
        <div class="variant-meta">
          <span class="variant-label">{{ variant.label }}</span>
          <span class="variant-note">{{ variant.note }}</span>
        </div>

        <div class="panel">
          <div class="lockup" :class="`lockup-${variant.key}`">
            <h3 class="lockup-title">Biography</h3>
            <button type="button" class="lockup-action">
              <Icon icon="mdi:sparkles" class="action-icon" />
              Generate
            </button>
          </div>
          <p class="panel-body">
            Born in Rivet City. Before the vault, I wandered through Megaton and Canterbury Commons.
            Both parents are still on the roster, and the eldest is apprenticed in the diner.
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.lab {
  min-height: 100vh;
  padding: 2.5rem;
  background: var(--color-terminal-background, #0f0e0d);
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.lab-intro {
  max-width: 60rem;
  margin-bottom: 2rem;
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

.lab-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 1.5rem;
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
  line-height: 1.4;
}

.panel {
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.panel-body {
  font-size: 0.8rem;
  line-height: 1.6;
  opacity: 0.7;
}

.lockup {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.lockup-title {
  font-size: 1.25rem;
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
  margin: 0;
}

.lockup-action {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.6rem;
  background: transparent;
  border: 1px solid var(--color-theme-primary);
  border-radius: 4px;
  color: var(--color-theme-primary);
  font-family: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}

.lockup-action:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}

.action-icon {
  width: 0.9rem;
  height: 0.9rem;
}

/* A — rule spanning the whole header row */
.lockup-row-rule {
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}

/* B — rule hugging the title text */
.lockup-title-underline .lockup-title {
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
}

/* C — typography only */
.lockup-plain {
  margin-bottom: 1.25rem;
}

.lockup-plain .lockup-title {
  font-size: 1.35rem;
  letter-spacing: 0.06em;
}

/* D — bracketed, no rule */
.lockup-bracket {
  margin-bottom: 1rem;
}

.lockup-bracket .lockup-title::before {
  content: '[ ';
  opacity: 0.5;
}

.lockup-bracket .lockup-title::after {
  content: ' ]';
  opacity: 0.5;
}

/* E — vertical accent at the title */
.lockup-accent {
  margin-bottom: 1rem;
  border-left: 3px solid var(--color-theme-primary);
  padding-left: 0.75rem;
}

/* F — filled bar with hairline */
.lockup-bar {
  padding: 0.5rem 0.75rem;
  margin: 0 -0.75rem 1rem;
  background: rgba(0, 0, 0, 0.45);
  border-bottom: 1px solid var(--color-theme-glow);
}
</style>
