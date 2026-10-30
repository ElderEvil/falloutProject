# Account merge policy

Phase 0/1 of #1198 provides a superuser-only way to consolidate two accounts without losing vaults or progress.

Admin previews are bound to the resolved source/target UUIDs in a short-lived server-issued confirmation token. Applying requires that preview token, CSRF, and the same admin session; changing an email or username after preview cannot redirect the merge to a different account. The confirmation token expires after 10 minutes and is cleared on a failed apply, so a new preview is required.

## Surfaces

- **Admin panel:** Accounts → **Merge accounts** (`/admin/merge-accounts`). Search for an account, preview, then confirm; every POST is CSRF-protected. A successful apply opens the new audit row directly.
- **CLI:** `fo-cli merge-users --source <uuid|email|username> --target <uuid|email|username> [--actor ...] [--reason ...] [--dry-run|--apply]`.
- **Audit:** Accounts → **Account merge** lists the immutable `account_merge` rows.

## Policy

- Only an active superuser may run a merge. Superuser and first-superuser accounts cannot be merged. An actor cannot merge their own account, and source and target must differ.
- The target must be active and not deleted. The source may already be inactive or soft-deleted.
- A source can be merged only once. Retry a completed merge with the **source UUID**; retrying with its old email/username is rejected because those identities may now belong to someone else.
- Vaults, notifications, AI interactions, chat history (both directions), OAuth links, and profile lifetime counters move to the survivor.
- The survivor keeps its email, bio, avatar, preferences, monthly token limit, and password. The source password is copied only when the survivor has no password.
- The survivor's profile wins on conflicts; lifetime counters are summed.
- Vault numbers are not unique. The preview reports duplicates; they remain valid but can be confusing.
- If both accounts link the same OAuth provider, the merge is rejected. Unlink one provider first.
- The source is tombstoned: it is soft-deleted, deactivated, credentials/recovery tokens are cleared, and its email/username are replaced with reserved tombstones.
- Only the **source** refresh token is invalidated. The surviving player stays signed in. This intentionally supersedes the older Phase 1 note that suggested invalidating both tokens.
- The admin page performs no mutation on preview; apply requires a fresh CSRF-protected POST and a reason.

## Irreversibility

There is no in-panel undo. The audit row records the source, target, actor, reason, counts and identity snapshots, but reversing a merge requires a database restore. Run a backup before applying a production merge.

## Provider linking (Phase 2)

A signed-in player can link Google/GitHub from Profile -> Connected accounts.

- `POST /api/v1/auth/oauth/{provider}/link` returns an authorize URL; the browser-bound state records the initiating user and the callback links to that user, never by email.
- A successful link redirects to the profile with `linked=<provider>`; it does not issue tokens or move data.
- `DELETE /api/v1/auth/oauth/{provider}` unlinks a provider. The last sign-in method (no password and no other provider) is rejected.
- A provider identity already owned by another account returns `provider_identity_in_use`; use the admin merge path.
- Linking never merges accounts or moves vaults/progress.

## Scope

This policy covers Phase 0/1 and Phase 2 provider linking. Self-service account merge is a later phase and does not implicitly merge accounts.
