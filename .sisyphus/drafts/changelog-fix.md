# Draft: Changelog not working (branch review)

## Requirements (partially confirmed)
- User reports: "There were few things done for changelog, but in the end it doesn't work".
- Symptom (confirmed): **Changelog UI/page broken**.
- Target (confirmed): **In-app page** (frontend route/view).
- Environment (confirmed): **Local dev**.
- Route/path (confirmed): **`/system/changelog`**.
- Failure mode (confirmed): **Page renders but list/content is empty**.
- Error logs: not available yet.

## User Answers (new)
- Branch source: **local branch only** (possibly unpushed and/or uncommitted changes).
- Intended changelog data source: **static JSON in frontend**.

## Current Understanding
- "Changelog" in this context is the in-app UI route/view.

## Research Findings (preliminary)
- A probe of the current working copy suggests the current git branch may be identical to `origin/master` (no branch-specific diff).
- Code search did **not** find any registered Vue route or view/component matching `/system/changelog` or "changelog".
- Closest existing page: `/about` mapped to `frontend/src/modules/profile/views/AboutView.vue` and backed by `GET /api/v1/system/info`.
- Repo docs `CHANGELOG.md` / `ROADMAP.md` exist but appear not to be referenced by the frontend.

## Suggestion Audit (user-provided) — applicability to current repo
- `backend/app/api/v1/endpoints/changelog.py`: **NOT PRESENT** in current working tree.
- `backend/app/api/v1/endpoints/system.py`: present; contains only `/info` and already uses `datetime.now(UTC)` (timezone-aware). No changelog parsing helpers exist here.
- `CHANGELOG.md`: does **not** contain `2.7.0` section in current file (latest section is `2.4.1`). The duplicate-heading suggestion appears to target a different changelog revision.
- `frontend/src/App.vue`: already uses single quotes and no semicolons in the `<script setup>` block.
- `frontend/src/core/components/common/NavBar.vue`: no version badge / `showChangelog()` / `versionBadgeVisible` found in current file.
- `frontend/src/core/composables/useVersionDetection.ts`: **NOT PRESENT**.
- `frontend/src/modules/profile/components/ChangelogModal.vue`: **NOT PRESENT**.
- `frontend/src/modules/profile/routes/changelog.ts`: **NOT PRESENT**.
- `frontend/src/modules/profile/services/changelogService.ts` (+ test): **NOT PRESENT**.
- `frontend/src/modules/profile/views/ChangelogView.vue`: present in current working tree; uses plain text rendering (no `v-html`) and stable keys (`idx`).

## Open Questions
- What URL/route is the changelog page (e.g. `/changelog`, `/about`, `/settings`)?
- What is the visible failure: blank screen, 404, infinite spinner, error toast, or data missing?
- Is it broken in **dev** (localhost:5173), **staging**, or **production**?
- Are there browser console errors and/or network request failures (status codes)?
- Which branch/PR are we looking at, and what base branch should we compare against?
- Is `/system/changelog` coming from a different router base (e.g., nested routes/modules) or a menu link that is now stale?
- If it loads but empty: what network requests fire on that page (URLs + status codes)?

## Scope Boundaries (pending)
- INCLUDE: identify cause, propose fix plan, verification steps.
- EXCLUDE: none stated yet.
