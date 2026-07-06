# Drafterino — Project Audit

**Date:** 2026-07-06
**Branch:** `audit`
**Scope:** Full review of the Drafterino GitHub Action — a Node 24 action that turns
labeled, merged pull requests into draft release notes and a computed next version.

> Note on scope: the audit request originally described this repo as "copier-based
> templates." It is not — it is a single composite/JavaScript GitHub Action. This
> audit reflects what the repository actually is.

## What was reviewed

- Action metadata: [`action.yml`](../action.yml)
- Source: [`src/index.js`](../src/index.js) and the committed bundle [`dist/`](../dist)
- Workflows: [`draft-release.yml`](../.github/workflows/draft-release.yml),
  [`update-major-tag.yml`](../.github/workflows/update-major-tag.yml),
  [`delete-old-runs.yml`](../.github/workflows/delete-old-runs.yml)
- Packaging: [`package.json`](../package.json), [`tools/build.sh`](../tools/build.sh),
  [`tools/install.sh`](../tools/install.sh)
- Docs: [`README.md`](../README.md)

## Deliverables

- **[ISSUES.md](ISSUES.md)** — every issue found, grouped by priority.
- **[RECOMMENDATIONS.md](RECOMMENDATIONS.md)** — how to improve the project.

## Issue count by priority

| Priority | Count | Theme |
|----------|-------|-------|
| Highest  | 2     | Wrong version / silently dropped PRs — the action's core output can be incorrect |
| High     | 4     | Unimplemented documented feature, non-SemVer tags, zero tests, no dist-sync guard |
| Medium   | 5     | Scheduled-cleanup bug, unused deps, error-swallowing, weak packaging |
| Low      | 7     | Docs drift, mutable-tag pinning, minor correctness/logging |
| Lowest   | 6     | Dead code, missing repo hygiene files, branding |

## The three things to fix first

1. **Version detection is date-ordered, not version-ordered** (Issue H1). `getLatestTag()`
   returns the most recently *created* semver-valid tag, not the highest *version*, and does
   not restrict to tags reachable from `HEAD`. A hotfix tagged on an old branch, or any
   out-of-order tagging, yields the wrong "previous version" and therefore the wrong next
   version.

2. **Merged-PR discovery silently drops data on any API hiccup** (Issue H2). Each commit is
   resolved to its PRs with an unbounded burst of parallel REST calls; failures are ignored
   (`if (res.ok)` with no else). GitHub secondary rate limits or a transient error silently
   omit PRs — which both truncates the release notes *and* can downgrade the version bump
   (e.g. a missed `significant` label). Replace the hand-rolled `fetch` with the already-
   declared-but-unused `@actions/github` Octokit client, which paginates, retries and
   throttles.

3. **`note-template` is documented and passed by users but never implemented** (Issue H3).
   `generateNotes()` hard-codes `- <title> (#<number>)` and ignores the configured template,
   so `$PR_TITLE` / `$PR_NUMBER` do nothing. Either implement it or remove it from the docs
   and workflow.

See **[ISSUES.md](ISSUES.md)** for the full list with file/line references and fixes.
