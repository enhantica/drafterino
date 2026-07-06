# Drafterino — Recommendations

Improvement recommendations, ordered roughly by impact. These complement
[ISSUES.md](ISSUES.md); issue IDs are cross-referenced as `(Hx/Mx/...)`.

## 1. Make version detection correct and deterministic (H1, M3)

The next version is the action's core output, so it must be robust:

- Select the previous version by **SemVer precedence among tags reachable from `HEAD`**, not by
  creation date. Concretely: `git tag --merged HEAD`, strip `^v` and `.post*`, keep
  `semver.valid` entries, `semver.rsort`, take the max — while preserving the original tag
  string for the `git log <tag>..HEAD` range.
- Fail loudly on git errors; only use the `0.0.0` baseline when there are genuinely no tags.
- Add unit tests covering: no tags, out-of-order tags, `.post` tags, mixed `v`-prefixed and
  bare tags.

## 2. Replace hand-rolled REST calls with Octokit (H2, M2, L5)

`@actions/github` is already declared but unused — adopt it:

- Use `octokit.rest.repos.listPullRequestsAssociatedWithCommit` with `octokit.paginate`.
- Add the `@octokit/plugin-throttling` and `@octokit/plugin-retry` behaviors so secondary
  rate limits and transient errors are handled instead of silently dropping PRs.
- Bound concurrency (e.g. a small pool) rather than firing one unbounded `Promise.all` over
  every commit.
- Surface partial failures (count failed lookups; `core.warning` or fail) so a truncated
  result never masquerades as success.
- This removes the manual `Authorization`/`Accept` headers and the deprecated `groot-preview`
  media type. Then drop `node-fetch` entirely.

Consider reading the commit range from the GitHub compare API or the event payload rather than
shelling out to `git log`, so the action depends less on the checkout depth.

## 3. Decide and document the versioning scheme (H4)

`.postN` is PEP 440, not SemVer, yet the README says SemVer. Pick one:

- **Keep `.postN`** but document it as a deliberate non-SemVer post-release scheme, and make
  sorting/parsing rules explicit; or
- **Move to real SemVer** (`2.0.0+post.1` build metadata, or a `-post.N` prerelease) so
  downstream tooling can parse and order tags.

Either way, align README wording, `getLatestTag`, and `bumpVersion`.

## 4. Implement or remove `note-template` (H3, LO6)

Users are configuring a template that does nothing. Either implement placeholder substitution
(`$PR_TITLE`, `$PR_NUMBER`, and document the full set) in `generateNotes`, or remove
`note-template` from the README and the workflow. Add a test asserting the rendered format.

## 5. Add tests and CI (H5, H6)

- **Unit tests** (`node --test`, no extra deps) for the pure functions: `getLatestTag`
  parsing, `determineBump` precedence (major > minor > patch > post > default), `bumpVersion`
  (including `.post` increment and reset on major/minor/patch), and `generateNotes` grouping
  and de-duplication.
- **CI workflow** on `pull_request`/`push` that runs install → lint → test → `ncc build` →
  `git diff --exit-code dist/`. The last step is the standard "check-dist" guard that prevents
  a stale bundle (H5) from ever shipping.
- Add a linter (ESLint) and a formatter (Prettier) with a matching CI check.

## 6. Tighten packaging and the build (M5, LO4)

- Flesh out `package.json`: `name`, `version`, `description`, `license: "MIT"`,
  `"private": true`, `engines: { "node": ">=24" }`, and `scripts`:
  `{ "build": "ncc build src/index.js -o dist", "test": "node --test", "lint": "eslint .", "package": "npm run build" }`.
- Retire `tools/build.sh` / `tools/install.sh` in favor of `npm run build` and `npm ci`
  (reproducible from the lockfile). If the scripts stay, add shebangs, mark them executable,
  and stop re-declaring dependencies by hand.

## 7. Fix the scheduled cleanup workflow (M1)

In `delete-old-runs.yml`, add fallbacks so the monthly `schedule` run uses real values:
`retain_days: ${{ github.event.inputs.days || 30 }}`,
`keep_minimum_runs: ${{ github.event.inputs.minimum_runs || 6 }}`, and default the pattern
inputs to `'All'`. Test with a `dry_run` first.

## 8. Harden the supply chain (L2, LO3)

- Pin third-party actions to full commit SHAs (comment the human version alongside).
- Add `.github/dependabot.yml` for `github-actions` and `npm` so pins are bumped
  automatically.
- Stop pinning the org's own release automation to `enhantica/drafterino@develop`; use a
  released tag on `main`.

## 9. Improve observability and robustness of the source (L4, L7, LO1, L3, L6)

- Route logs through `@actions/core` (`info`/`debug`/`warning`) for grouping, annotations and
  debug gating.
- Use `execFileSync('git', [...])` instead of interpolating into shell strings.
- Delete the commented-out dead code.
- Guard empty git-log output (`filter(Boolean)`) and short-circuit no-op runs.
- Define and enforce whether a multi-labeled PR appears in one section or several.

## 10. Documentation (LO5, LO2, L1)

- Add **Inputs / Outputs / Permissions** reference tables to the README (outputs are
  `version`, `tag_name`, `release_name`, `release_notes`; `GITHUB_TOKEN` and `contents: write`
  are required).
- Align README examples with the actual workflow (action versions and `[scope] …` label
  names), or mark them as illustrative.
- Add a `branding` block to `action.yml` for the Marketplace listing.
- Consider `CONTRIBUTING.md` (documenting the "rebuild `dist/` before commit" rule until CI
  enforces it), `SECURITY.md`, `CODEOWNERS`, and issue/PR templates.

## Suggested sequencing

1. **Correctness first:** H1, H2, H4, H3, M1 — these change behavior/output.
2. **Safety net:** H5 + H6 (tests + CI + check-dist) so the above changes are verifiable and
   can't regress.
3. **Hygiene:** M2–M5, then the Low/Lowest items and docs.
