# drafterino roadmap — milestones & tasks

Milestone prefix **D** (registered in the org portfolio —
`enhantica/org` `knowledge/roadmap/portfolio.md`). Tier **C (solo)** under the org
orchestration model: one agent per task, PR-gated, `feature → main` squash (ORG-0003).
Status: ✅ done · 🟡 partial · ⬜ open. `AUD-##` = findings in the org audit
(`enhantica/org` `audit/ISSUES.md`); resolve per ORG-0025 (the fixing PR flips the finding's
status there in the same change).

drafterino is **the org's release engine** (labeled PRs → draft release + SemVer bump,
ORG-0004) — its hardening has org-wide supply-chain leverage (audit R3).

## D01 — Hardening (the release engine earns CI) — audit R3

| Task | Status | What |
|---|:--:|---|
| D01-T01 | ⬜ | **check-dist workflow**: on every PR, rebuild (`tools/build.sh` / ncc) and `git diff --exit-code dist/` — nothing may merge with `dist/` ≠ `src/` (AUD-03) |
| D01-T02 | ⬜ | **Test suite + CI** around the version-bump and release-notes grouping logic (the SemVer computation every repo trusts must not silently regress; seed cases: `[scope]` map incl. `.postN`, mixed-label PRs, no-PR pushes) (AUD-03) |
| D01-T03 | ⬜ | **package.json metadata**: `name`, `version`, `scripts` (`build`/`test`/`lint`) so standard tooling and scanners work (AUD-20) |
| D01-T04 | ⬜ | **TS/JS lint lane** per ORG-0014: ESLint (strict) + format check, as npm scripts + CI job (AUD-03) |
| D01-T05 | 🟡 | **Workflow + branch hygiene** — *2026-07-06: `@develop` self-ref → `@v2`, `master`/`develop` triggers dropped, and the merged `develop`/`audit`/`node-24` branches deleted (all verified ancestor-merged; `delete_branch_on_merge` now on).* **Remaining:** top-level `permissions: contents: read` in `draft-release.yml` (AUD-09); SHA-pin third-party actions (AUD-07, ORG-0024) |

## D02 — Org-base compliance — ORG-T28

| Task | Status | What |
|---|:--:|---|
| D02-T01 | ⬜ | **Labels**: full `[scope]`/`[priority]`/`[maintainer]` set arrives via `.github`'s `TARGET_REPOS` extension (AUD-11 — the change lands in `.github`; verify here + relabel open items) |
| D02-T02 | ⬜ | **License**: execute the owner's AUD-04 decision (relicense MIT→BSD-3, or keep MIT under an ORG-0020 amendment); then SPDX headers (ORG-0016) |
| D02-T03 | ⬜ | **Ruleset + health defaults**: adopt the branch-protection ruleset and inherit `.github` community-health defaults once ORG-T06/T22 ship them |

---

`audit/` (repo root) is this repo's own audit record (the ORG-0025 reference layout);
repo-level findings continue there, org-level findings in the org audit.
