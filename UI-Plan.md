---
title: "AI chat with GPT-5, Claude, Gemini, and more"
source: "https://t3.chat/chat/9f10657f-366a-4bcc-a709-c23f8efbe891"
author:
published:
created: 2026-06-25
description: "T3 Chat gives you one fast AI chat app for top models from OpenAI, Anthropic, Google, DeepSeek, and more."
tags:
  - "clippings"
---
Yes — the screens share the same “Pip-Boy / Fallout terminal” direction, but the styling is not fully consistent yet. The biggest differences are in layout density, card treatments, typography hierarchy, glow usage, spacing, and page framing.

## Main style differences I can see

### 1\. Page containers are inconsistent

Some screens feel like they have a clear centered content shell:

- Quests
- Training
- Storage

Others feel more like free-form overlays on the vault canvas:

- Overview
- Exploration

For example, Storage has a strong centered column with large glowing panels, while Exploration has a lot of empty black space and a single small card on the left.

**Suggestion:** define one reusable page shell:

```
Sidebar fixed
Topbar fixed
Main content max-width: 1200-1280px
Consistent left/right padding
Consistent top spacing
```

Then all pages should use that unless intentionally using a special layout like the vault map.

---

### 2\. Card styles vary a lot

You currently have several different card looks:

- Thin green outline cards
- Heavy glowing green panels
- Gray gradient quest cards
- Dark blue storage panels
- Orange/brown wasteland panels
- Almost-black list rows on Dwellers

They all fit the theme individually, but together they feel like different UI kits.

**Suggestion:** create 2-3 official card variants:

1. `panel-primary`
	Main page sections, green border, subtle dark gradient.
2. `panel-muted`
	Secondary info blocks, less glow.
3. `panel-warning` / `panel-wasteland`
	Brown/orange wasteland/exploration-only styling.

Avoid inventing a new background/border/glow recipe per screen.

---

### 3\. Glow intensity is inconsistent

Storage title and panels have very strong glow. Training also has heavy glow. Quests are more controlled. Dwellers is much flatter.

The glow is part of the identity, but if every page uses a different intensity, it becomes visually noisy.

**Suggestion:** standardize glow levels:

```
--glow-sm: 0 0 6px rgb(0 255 0 / 0.35);
--glow-md: 0 0 12px rgb(0 255 0 / 0.45);
--glow-lg: 0 0 24px rgb(0 255 0 / 0.55);
```

Use:

- small glow for buttons/icons
- medium glow for selected states
- large glow only for hero headers or very important moments

Storage currently feels like it uses `glow-lg` everywhere.

---

### 4\. Typography hierarchy differs between pages

Examples:

- “Vault 123 Dwellers” is centered and large.
- “Wasteland Exploration” is left-aligned and large.
- “Vault Storage” is large with glow and icon.
- Training has a boxed title panel.
- Overview has no big page title, more of a dashboard.

All are fine separately, but the app would feel more cohesive if every section started similarly.

**Suggestion:** create a standard page header component:

```
[Icon] Page Title
Subtitle / description
Optional stat cards on the right
```

For example:

```
[Compass] Wasteland Exploration
Monitor active explorations and quest parties
                                  [1 Explorations] [0 Quests]
```

This is already close on Exploration. Apply a similar pattern to Dwellers, Quests, Training, Storage.

---

### 5\. Button colors and semantic meaning are unclear

Examples:

- Green buttons mean primary action.
- Red buttons mean destructive/cancel.
- Cyan buttons appear on Training for “Complete”.
- Orange buttons appear for “Recall Early”.
- Gray pills appear for room assignments.

The cyan “Complete” button stands out as not belonging to the green terminal palette, unless cyan has a deliberate semantic role.

**Suggestion:** define semantic button variants:

```
Primary: green
Secondary: dark/outline green
Danger: red
Warning: amber/orange
Info: cyan/blue, only if intentionally separate from primary
Disabled: muted gray/green
```

If “Complete” is a positive primary action, I’d make it green instead of cyan.

---

### 6\. Sidebar is very consistent and strong

The sidebar is probably the most polished and consistent part. It has:

- clear active state
- good icon + label rhythm
- keyboard hint badges
- locked feature section

One small issue: some pages use page-level “Back” links even though the sidebar already handles main navigation. On top-level pages like Storage or Training, “Back” may not be necessary and can create hierarchy confusion.

**Suggestion:** only show “Back” when the page is truly a subpage/detail view.

---

## Screen-by-screen notes

### Overview

The vault layout is cool and distinct, but it feels less polished than the other pages because it mixes:

- resource bar
- unassigned dwellers panel
- wasteland panel
- vault map
- build mode button

The content is functional, but spacing feels a little loose and elements compete.

**Suggestions:**

- Give Overview a clearer dashboard header.
- Align resource bar and top controls inside the same content width as other screens.
- Make the “Unassigned Dwellers” and “The Wasteland” panels use the same base card style, with only color accents differing.
- Reduce the empty vertical space inside the unassigned dwellers card when empty.

---

### Dwellers

This screen is clean and readable. It feels more “app UI” than “terminal game UI” compared with Storage/Training.

**Suggestions:**

- Add a page header matching other pages.
- Make filter/sort controls use the same panel treatment as other pages.
- Dwellers list rows could use a bit more green accent/glow to match the rest.
- The room pill on the right is useful, but the gray style is visually disconnected. Maybe make it dark green-outline instead.

---

### Exploration

This is the most sparse screen. The card is nice, but the huge empty black area makes it feel unfinished.

**Suggestions:**

- Add an “empty state” area for no quest parties or historical expeditions.
- Use a grid layout for expedition cards, even if there is only one.
- Consider adding a map/radar-style background or wasteland scan panel to justify the empty space.
- Make the top stat boxes visually match the cards from other screens.

---

### Quests

This is one of the most cohesive screens. The quest cards have a good layout and consistent rhythm.

Potential issue: quest cards look more gray/metal than the rest of the green/black UI. That is not bad, but if other screens do not share that gradient style, it stands apart.

**Suggestions:**

- Reuse this card style elsewhere, or tone it closer to the global panel style.
- The tabs look good; consider using the same tab pattern in Storage and Dwellers.

---

### Training

Training looks strong but visually heavy. Almost every element has a border, glow, or intense green. The active training list is also very bright.

**Suggestions:**

- Reduce glow on nested training cards.
- Make the top title panel less tall or align it with standard page headers.
- Use the same card background as Quest/Storage panels.
- Change cyan “Complete” to primary green unless cyan is a global “instant/ready” action color.

---

### Storage

Storage has a nice inventory feel, but its style is the most different:

- blue/dark navy panels
- strong title glow
- tab row differs from Quests tabs
- inventory cards are compact and very saturated

**Suggestions:**

- Tone down the title glow.
- Use the same tab component as Quests.
- Keep the dark blue storage panel if you like, but make it a formal design token, e.g. `--panel-storage-bg`.
- Align item cards with a consistent size and spacing grid.

---

## Concrete design system suggestions

### Define core tokens

Something like:

```
:root {
  --color-bg: #020402;
  --color-panel: #081108;
  --color-panel-elevated: #101810;
  --color-border: rgb(0 255 0 / 0.45);
  --color-border-strong: rgb(0 255 0 / 0.85);

  --color-text: #00ff00;
  --color-text-muted: rgb(0 255 0 / 0.65);
  --color-text-dim: rgb(0 255 0 / 0.35);

  --color-danger: #ff4d5e;
  --color-warning: #d8912a;
  --color-info: #18c8ff;

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;

  --glow-sm: 0 0 6px rgb(0 255 0 / 0.35);
  --glow-md: 0 0 12px rgb(0 255 0 / 0.45);
  --glow-lg: 0 0 24px rgb(0 255 0 / 0.55);
}
```

---

### Standardize the page structure

```
Page
  PageHeader
  Optional Toolbar / Filters
  ContentGrid
```

Example:

```
[Icon] Vault Storage
Manage weapons, outfits, medical supplies, and junk

[Capacity Panel]

[Tabs]

[Inventory Grid]
```

---

### Standardize tabs

Use the same tab system for:

- Quests: Active / Completed
- Storage: Weapons / Outfits / Junk
- Dwellers: List / Grid
- Maybe Objectives later

Right now each screen seems to implement its own tab style.

---

### Standardize empty states

You already have an empty state in Overview: “All dwellers are assigned!” Use the same style everywhere.

Examples:

```
No active explorations
Send an idle dweller to the wasteland from the Overview screen.
[Go to Overview]
```

```
No completed quests
Complete side quests to see them here.
```

---

### Standardize locked/upcoming styling

The sidebar locked items look good. If locked quests, rooms, features, or requirements appear elsewhere, use the same icon, opacity, and color treatment.

---

## Priority recommendations

If you want the biggest improvement with the least work:

1. Create one `PageHeader` component and use it everywhere.
2. Create one `Panel/Card` component with variants.
3. Unify tabs and buttons.
4. Reduce glow intensity on Storage and Training.
5. Give Exploration more content structure or a stronger empty/background state.
6. Align all main page content to the same max width and spacing.

Overall, the visual identity is strong. The issue is not that the screens look bad — they just look like they were designed in separate passes. A small design-token/component pass would make the whole app feel much more professional and intentional.
