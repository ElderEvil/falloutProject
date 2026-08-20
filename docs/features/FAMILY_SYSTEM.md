# Family System — Feature Map

> **Status:** Design / planning doc — captures what the family feature **is**, what we are **building**, and what we are **explicitly not doing**. Use this as the source of truth before touching backend or UI code so we don't reinvent or over-scope.
>
> Last updated: 2026-08-20

## 1. Goal

Model a persistent family lineage for vault dwellers — who is related to whom, how couples form, how children are born and inherit, and how all of it is surfaced in the UI (family tree, relationships, pregnancies). This is the "Family Update" theme.

---

## 2. Data Model (backend)

All stored on `Dweller` (one row per dweller) + two child tables.

### 2.1 Dweller family fields
| Field | Type | Meaning |
|---|---|---|
| `partner_id` | `UUID4 \| None` | Reciprocal partner (set for `PARTNER`/`MARRIED`). Both dwellers point at each other. |
| `parent_1_id` | `UUID4 \| None` | One parent (mother). |
| `parent_2_id` | `UUID4 \| None` | Other parent (father). |

> Lineage is **bipartite / single-generation** by design: we store parents and the *current* partner, not a full multi-union graph. Siblings are computed by shared parents; partners by `partner_id` + `PARTNER`/`MARRIED` relationships.

### 2.2 `Relationship` (relationship table)
- Pair `(dweller_1_id, dweller_2_id)` + `relationship_type` + `affinity` (0–100).
- Stages: `acquaintance → friend → romantic → partner → MARRIED → ex`.
- Not the same as `partner_id` — a dweller can have many relationships but at most one *partner* (via `partner_id`).

### 2.3 `Pregnancy`
- `mother_id`, `father_id`, `conceived_at`, `due_at`, `status` (`pregnant | delivered | miscarried`).
- One pregnancy per mother while `PREGNANT`.

---

## 3. Relationship Lifecycle (backend service: `relationship_service.py`)

**What exists (keep):**
- Affinity auto-growth per game tick (+2 when in the same room).
- Auto-upgrade on affinity: `acquaintance→friend→romantic` at 70, `→partner` at 70, `partner→MARRIED` at 85 (defaults: romance 70, partnership 70, marriage 85).
- `initiate_romance` / `make_partners` / `marry` / `break_up` endpoints + service methods.
- `marry` grants **each** dweller a one-time cumulative **+25** happiness bonus (+10 for becoming partners, +15 for becoming married) and fires a `RELATIONSHIP_FORMED` notification.
- `break_up` marks `ex`, −30 affinity, clears `partner_id` for partner-linked couples.
- Compatibility scoring (SPECIAL / happiness / level / proximity weighted).

**Restrictions on couple pairing (NEW — define before building):**
> In line with Fallout universe + vault logic:
- **Heterosexual couples are the default / most likely.**
- **Same-sex couples are possible but less likely** (weighted against in auto-pairing / affinity pairing).
- **Same-sex couples cannot reproduce** (no biological child; pregnancy only from male+female pair).
- The pairing logic must respect these weights so auto-generated / random vaults reflect this distribution, while still allowing same-sex couples to form through the manual UI path.

**NOT doing (out of scope):**
- ❌ Resurrecting removed debug cruft (`quick_pair_dwellers`, the "Irradiated Cupid" button, `PregnancyDebugPanel`, `process-breeding` button). These were deliberately removed.
- ❌ Hard "no same-sex couples ever" — they exist, just rarer.
- ❌ Adoption / step-parents / half-sibling edge-case modeling beyond what shared-parents implies.

---

## 4. Breeding & Inheritance (backend service: `breeding_service.py`)

**What exists (keep):**
- Conception roll for adult partners **in living quarters** (chance = affinity / 100, fallback base).
- Pregnancy duration (default 3h real time), `deliver_baby`, manual delivery endpoint.
- Child trait inheritance: SPECIAL = avg(parents) ±2 × 0.5 child multiplier; rarity ≥ highest parent with upgrade chance; random gender.
- **Last-name inheritance:** father's last name by default, 20% mother's (`maternal_last_name_chance`).
- **Postpartum cooldown:** mother can't conceive again for 6h (`birth_cooldown_hours`) after delivery.
- Child growth: ages to adult after 3h (`child_growth_duration_hours`).
- Newborn bio with clickable parent links; `BABY_BORN` notification; `total_dwellers_born` stat.

**NEW — enforce reproduction rule (from §3):**
- Conception must only occur for **male+female** couples. A same-sex couple may be `PARTNER`/`MARRIED` but never triggers `create_pregnancy`. (Current code already requires a female mother + male father via `create_pregnancy`, but auto-conception pair eligibility must also explicitly skip same-sex pairs rather than relying on gender checks alone — make it explicit and tested.)

**NOT doing (out of scope):**
- ❌ Miscarriage / stillbirth gameplay — **see §4.1 (future plan).**
- ❌ Twin/multiple births.
- ❌ Surrogacy / non-biological reproduction mechanics.

### 4.1 Miscarriage — FUTURE PLAN (not built yet)

> Captured as a **planned** enhancement, not current scope. There is already an unused `miscarried` value in `PregnancyStatusEnum` — a natural seam for this.

**Concept:** a pregnancy can end in miscarriage before term, adding risk to the breeding economy.

**Design sketch (for a future update):**
- **Base chance:** small chance per game tick (or per pregnancy) of spontaneous miscarriage, so a pregnancy is not a guaranteed birth. Tune to keep births the norm.
- **Combat / incident risk (the interesting hook):** when a pregnant mother is in a room being hit by an incident (`incident_service.process_incident` already applies `damage_per_dweller` to dwellers in the affected room), give her an **elevated** miscarriage chance. Heavier damage / higher difficulty → higher chance. A mother who is *not* involved in the incident is unaffected (only mothers in the affected room roll the elevated chance).
- **Result:** set `Pregnancy.status = MISCARRIED`, fire a notification (e.g. `BABY_LOST` / reuse an existing type), optionally a small happiness penalty to the mother/partner.
- **UI:** the Pregnancies tab should show miscarried pregnancies (or a notification of the loss) rather than silently dropping them.

**Explicitly deferred decisions (do not start now):**
- Exact base chance / per-tick formula.
- Whether incident risk applies on the tick the mother *enters* the room vs. continuously while the incident is active.
- Whether the father/partner also takes a happiness hit.

> Gate: this should only be implemented once the core family feature (couple pairing + reproduction rule in §3–§4) is stable and tested.

---

## 5. Lineage / Family Tree (backend: `lineage_service.py`)

**What exists (keep):**
- `GET /dwellers/{id}/lineage` → `LineageResponse` with `parents`, `children`, `siblings`, `partners`, `generation`.
- `_compute_generation`: walks parents upward (orphan = 0).
- Same-vault scoping, soft-delete filtering.

**NOT doing (out of scope):**
- ❌ Full recursive multi-generation tree rendering (we only render the focal dweller's direct family + generation number).
- ❌ Cross-vault family (a dweller's family is always within their vault).

---

## 6. UI (frontend)

**What exists (keep):**
- `/vault/:id/relationships` view — 4 tabs: **Forming**, **Partners**, **Pregnancies**, **Children** + stat cards.
- `RelationshipCard` actions gated by stage/affinity: Romance (acquaintance ≥70), Partner (romantic), Marry (partner ≥85), Break Up (committed types).
- `PregnancyTracker` with manual deliver.
- Dweller detail **Family tab** → `FamilyTreePanel` (parents / self+partners / children / generation, clickable nodes navigating to dweller).
- Pregnancy, relationship, and family stores + services.

**NEW / planned (gaps):**
- Reflect **same-sex couples** visually (a same-sex partner is a valid partner; no "mother/father" assumption in UI labels — use neutral "parents"/"partners" where reproduction is not implied, or label child parents generically).
- Clear empty/edge states already present (em-dash rows) — verify they hold for same-sex couples.
- If a same-sex couple exists in the tree, **no** pregnancy/reproduction affordance should be offered (mirrors backend rule).

**NOT doing (out of scope):**
- ❌ Restoring the debug PregnancyDebugPanel / quick-pair button.
- ❌ A marriage proposal ceremony UI beyond the existing Marry button.
- ❌ Baby-name picker / family-name lineage editor (names are inherited automatically).

---

## 7. Manual Test Checklist (family)

See `../AGENTS.md` "Bug Fix Workflow" + this doc. Key manual checks:

**Relationships**
- [ ] Affinity auto-growth for co-located dwellers (+2/tick).
- [ ] Stage progression at 70 / 70 / 85 thresholds.
- [ ] Romance / Partner / Marry buttons appear exactly when allowed.
- [ ] Marry: happiness bonus +25, `RELATIONSHIP_FORMED` notification, badge shows `MARRIED`.
- [ ] Break up: `ex` stage, −30 affinity, `partner_id` cleared.

**Couple restrictions (NEW)**
- [ ] Same-sex couples **can** form via manual UI.
- [ ] Same-sex couples are **rarer** than opposite-sex in auto-pairing.
- [ ] Same-sex couples **cannot** conceive / produce a pregnancy.

**Breeding**
- [ ] Only adult partners in living quarters roll for conception.
- [ ] Pregnancy appears with due time; no second pregnancy while pregnant.
- [ ] Child inherits traits/rarity; father's last name default (20% mother).
- [ ] Postpartum cooldown 6h blocks re-conception.
- [ ] Child grows to adult after 3h.

**Family tree**
- [ ] Lineage endpoint returns parents/children/siblings/partners/generation.
- [ ] Family tab renders all rows; clickable nodes navigate.
- [ ] Empty states (orphan, no children) render cleanly.

---

## 8. Open Questions (resolve before implementing)

1. **Pairing weight mechanics:** Where does the same-sex weighting live — in `relationship_service` auto-pairing, in the affinity auto-upgrade path, or only in a test-scenario tool? (Likely: auto-pairing + test tool respect it; manual UI is user-driven and unrestricted.)
2. **UI labelling for same-sex couples:** what shows in the family tree / relationship card for a same-sex couple — "partners" (neutral) vs gendered labels. Recommend neutral.
3. **Should a dev/QA scenario tool (CLI) exist at all**, and if so should its couple-pairing live in `relationship_service` or stay as a contained dev tool? (Given the "don't resurrect debug cruft" direction, lean: **contained dev/QA tool, not a production service change**.)

## 9. Roadmap (future updates)

- **Miscarriage** (see §4.1) — base chance + combat/incident-elevated risk; uses the already-existing `miscarried` `PregnancyStatusEnum` value. Not in current scope; revisit after core family is stable.
- **Same-sex reproduction** — explicitly NOT planned (same-sex couples never reproduce).
- **Pydantic AI relationship tool** (see §10) — dweller chat agent reads the dweller's family/relationship state for in-character conversation. Read-only; no debug controls.
- Twin/multiple births, adoption, surrogacy — explicitly NOT planned.

## 10. Pydantic AI — Relationship Status Tool (FUTURE PLAN)

> Captured as a **planned** enhancement. Not in current scope — gate behind the core family feature being stable.

**Idea:** give the dweller chat agent a tool that reads the dweller's family/relationship state so dwellers can talk about their relationships in-character (partner, children, parents, marriage, affinity, recent breakup, etc.) — making the family system feel alive in conversation.

**Why it's useful:** the existing `dweller_chat_agent` already has tools (`list_all_rooms`, `list_production_rooms`, `get_dweller_activity_briefing`) and a `DwellerChatDeps` dataclass carrying `db_session`, `dweller`, `vault_id`. A relationship tool slots into this exact pattern.

**Design sketch (follow the existing agent pattern):**
- Add a `DwellerRelationshipBriefing` Pydantic model mirroring `DwellerActivityBriefing`:
  ```python
  class DwellerRelationshipBriefing(BaseModel):
      partner_name: str | None = None
      relationship_stage: str | None = None      # friend/romantic/partner/MARRIED/ex
      affinity: int | None = None                # 0-100
      is_pregnant: bool = False
      children: list[str] = []                   # names
      parents: list[str] = []                    # names
  ```
- Add a tool on `dweller_chat_agent`:
  ```python
  @dweller_chat_agent.tool
  async def get_dweller_relationship_briefing(
      ctx: RunContext[DwellerChatDeps],
  ) -> DwellerRelationshipBriefing:
      """Read the dweller's current family/relationship state so the dweller
      can respond in-character about their partner, children, or marriage."""
  ```
  - Implementation reads `dweller.partner_id` / `parent_*` and queries `Relationship` (via `relationship_crud.get_by_dweller`) + `Pregnancy` (via `breeding_service.get_active_pregnancies` or a mother-scoped query), scoped to `ctx.deps.vault_id`.
  - Respects the §3 reproduction rule: a same-sex partner is reported as a partner, never implies a pregnancy.
- **Instructions:** add a line to `chat_instructions` telling the dweller to call the tool when the user asks about family, romance, marriage, or children — and to stay in character (e.g., a MARRIED dweller mentions their spouse; an `ex` dweller might be guarded/emotional).
- **Respect removed-debug direction:** this is a *read-only conversational* tool — it does NOT resurrect `quick_pair_dwellers` or add any debug pairing/pregnancy buttons.

**NOT doing (out of scope):**
- ❌ The AI performing relationship *actions* (auto-marry, auto-break-up, force-pair). Read-only awareness only.
- ❌ Any new debug controls or endpoints.
- ❌ Wiring this into a separate chat flow beyond the existing dweller chat.
