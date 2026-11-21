## Change

<!-- Describe the concrete trigger and resulting behavior. -->

## Validation

<!-- Record commands/results and any relevant manual checks. For each applicable item below,
     include the evidence; remove items that do not apply to this PR. -->

- Composed writes: transaction owner and called commit/rollback paths; late-write failure, rejection
  and persisted-state checks; success/progression delivery only after commit.
- Shared frontend state/events: existing service/store reused; vault/account switch and
  duplicate-event/reconnect behavior checked.
- Refactors: public/error/auth/locking contracts preserved; describe the ownership or duplication
  improvement. File moves and test deletion alone are not simplification evidence.
- Size/scope (≥300 handwritten application/test lines added; tooling excluded): what this replaces, or
  why nothing could be removed; any material overage against the advisory targets
  (`python3 scripts/size-report.py <base-ref>`).
