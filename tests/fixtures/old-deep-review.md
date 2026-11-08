## Deep review

Run this review once with `deep-inspector` on a diff that touches a deep-review
type, in addition to the default inspector. Check the diff against the types below first; when it matches
none of them, skip this review.

### Deep-review types

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
- secrets, CI/CD, or infrastructure changes
- new or changed paths by which untrusted input reaches SQL, shell or template
  construction, deserialization, uploads, redirects, or server-side fetches of
  user-supplied URLs
- data deletion

### Steps

1. Use the default inspector while iterating, so the deeper pass sees only the
   settled diff.
2. On the settled diff before the PR or final handoff, without asking the user,
   launch `deep-inspector`, which runs inspector's review at max effort.
3. Give it the diff, baseline, requirements, and check results, but not the
   earlier inspector's findings, so it reviews independently.
4. Fix confirmed findings and review the fix diff with the default inspector.
   Rerun the deep review only if the fix itself touches a deep-review type.
5. Report in your summary that the deep review ran and what it found.
