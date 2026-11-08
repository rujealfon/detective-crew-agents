## Opus review

Run this review once on a diff that touches an Opus type, in addition to the
default inspector. Check the diff against the qualified types below first; when
it matches none of them, skip this review.

### Opus types

- migrations, including squashing or rewriting history
- authentication or authorization changes, including sessions, tokens, and
  crypto
- tenant-isolation scoping
- payment, billing, or financial record logic (balances, fund allocations,
  closed-period locks)
- changes to how audit entries are written or which fields they record, not
  features that only add an entry through the existing mechanism
- changes to how sensitive or personal data is encrypted, masked, or revealed,
  or new paths that could copy it into logs, errors, or audit entries
- data deletion

### Steps

1. Use the default inspector while iterating, so the costly pass sees only the
   settled diff.
2. On the settled diff before the PR or final handoff, without asking the user,
   spawn `inspector` with the Agent tool's `model: "opus"` override at medium
   effort.
3. Give it the diff, requirements, and check results, but not the earlier
   inspector's findings, so it reviews independently.
4. Fix confirmed findings and review the fix diff with the default inspector.
   Rerun the Opus review only if the fix itself touches an Opus type.
5. Report in your summary that the Opus review ran and what it found.
