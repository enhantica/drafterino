# Drafterino — Issues (by priority)

Each issue lists **location**, **what's wrong**, **impact**, and a **fix**. Line numbers
refer to the state of the `audit` branch at review time.

Legend: 🟥 Highest · 🟧 High · 🟨 Medium · 🟦 Low · ⬜ Lowest

---

## 🟥 Highest

### H1 — Version detection is ordered by tag *date*, not by *version*, and ignores reachability
**Where:** [`src/index.js:8-21`](../src/index.js) (`getLatestTag`), used at `src/index.js:40`, `src/index.js:173`.

```js
const tags = execSync('git tag --sort=-creatordate', ...).trim().split('\n');
for (const tag of tags) {
  const cleaned = tag.replace(/^v/, '').split('.post')[0];
  if (semver.valid(cleaned)) return tag;   // first by DATE, not highest version
}
```

**What's wrong:**
- `--sort=-creatordate` returns the newest-*created* tag, not the highest semantic version.
  If `v1.2.1` is tagged (e.g. a hotfix on a maintenance branch) *after* `v2.0.0` already
  exists, `getLatestTag()` returns `v1.2.1` and the next version is computed from the `1.2.x`
  line — a regression.
- It does **not** restrict to tags reachable from `HEAD`. The `--merged HEAD` variant the
  author considered is commented out at `src/index.js:164`. A tag pushed on an unrelated
  branch can be selected, after which `git log <tag>..HEAD` (`src/index.js:41`) spans an
  unintended range.

**Impact:** The single most important output of the action — the computed next version — can
be wrong, with no error. Downstream draft releases get the wrong tag/name.

**Fix:** Select the previous version by SemVer precedence among tags **merged into HEAD**.
For example: `git tag --merged HEAD`, strip `^v` and any `.post*`, keep `semver.valid`
entries, and pick the max with `semver.rsort`. Preserve the original tag string for the
`git log <tag>..HEAD` range.

---

### H2 — Merged-PR discovery silently drops PRs on any API failure (and floods the API)
**Where:** [`src/index.js:57-73`](../src/index.js) (`getMergedPRs`).

```js
return Promise.all(commitShas.map(async sha => {
  const url = `.../commits/${sha}/pulls`;
  const res = await fetch(url, { headers });
  if (res.ok) { ... }          // no else: non-2xx is silently ignored
}))
```

**What's wrong:**
- **One REST request per commit**, all fired concurrently via `Promise.all`. For a release
  with many commits this is an unbounded burst that trips GitHub's secondary rate limits.
- Any non-`ok` response (403 rate-limited, 5xx, network error) is **silently discarded** —
  there is no `else`, no retry, no aggregate error. Rejected promises would also reject the
  whole `Promise.all` and be caught only by the top-level handler as a generic failure.

**Impact:** Missing PRs both **truncate the release notes** and **corrupt the bump decision**:
if the one PR carrying a `significant`/major label is dropped, `determineBump`
(`src/index.js:76-101`) silently downgrades the release. Failures look like success.

**Fix:** Use the already-declared-but-unused `@actions/github` Octokit client
(`octokit.rest.repos.listPullRequestsAssociatedWithCommit`) with `octokit.paginate`, its
built-in throttling/retry plugins, and bounded concurrency. Surface partial failures instead
of swallowing them. This also removes the manual `Authorization`/`Accept` header handling.

---

## 🟧 High

### H3 — `note-template` is documented and configured but never implemented
**Where:** [`src/index.js:129-149`](../src/index.js) (`generateNotes`) hard-codes the format at
`src/index.js:140`; advertised in [`README.md:49`](../README.md) and passed in
[`.github/workflows/draft-release.yml:30`](../.github/workflows/draft-release.yml).

```js
grouped[sec.title].push(`- ${title} (#${number})`);   // template ignored
```

**What's wrong:** The README and the live workflow both set
`note-template: '- $PR_TITLE (#$PR_NUMBER)'`, but `cfg['note-template']` is never read, and
`$PR_TITLE` / `$PR_NUMBER` are never substituted. The config key is silently ignored.

**Impact:** Users configuring their note format get no effect and no warning — a broken
public contract. Anyone customizing the template will be confused.

**Fix:** Implement templating (substitute `$PR_TITLE`, `$PR_NUMBER`, and any other documented
placeholders per entry), **or** remove `note-template` from the README and workflow and
document the fixed format. Whichever is chosen, docs and behavior must agree.

---

### H4 — `.postN` version suffix is not valid SemVer, contradicting the README
**Where:** [`src/index.js:112-116`](../src/index.js) (`bumpVersion` `post` case);
README claims SemVer at [`README.md:11-12`](../README.md).

**What's wrong:** The README states versions follow *"Semantic Versioning (`MAJOR.MINOR.PATCH`)
with an optional `.postN` suffix."* But `.postN` is a **PEP 440** (Python) convention, not
SemVer. Verified: `semver.valid('2.0.0.post1')` → `null`. The code only survives by stripping
`.post` everywhere before handing strings to `semver` (`src/index.js:14`, `src/index.js:104`).

**Impact:** Tags like `v2.0.0.post1` are not parseable by any SemVer-based tooling downstream
(release managers, package ecosystems, sorters). Ordering of `.post` tags is undefined outside
this action's own bespoke handling. The documentation is internally contradictory.

**Fix:** Pick one model and state it plainly. Either (a) use a real SemVer pre/build form such
as `2.0.0+post.1` or a prerelease `2.0.1-post.1`, or (b) keep `.postN` but stop calling it
SemVer and document the scheme explicitly. Update the README either way.

---

### H5 — No tests, and nothing guarantees `dist/` matches `src/`
**Where:** whole repo; build is a loose script at [`tools/build.sh`](../tools/build.sh)
(`npx ncc build src/index.js -o dist`); the runtime entry is
[`action.yml:11`](../action.yml) → `dist/index.js`.

**What's wrong:**
- There are **zero tests** for logic that is easy to get subtly wrong: version parsing, bump
  precedence, `.post` incrementing, note grouping.
- The action runs the **committed `dist/` bundle**, not `src/`. A contributor who edits `src`
  and forgets to run `tools/build.sh` ships stale behavior. (At review time `dist/` *is* in
  sync — verified function-by-function — but nothing enforces that.)

**Impact:** Regressions ship silently; a stale `dist/` means the reviewed source and the
executed code diverge.

**Fix:** Add a unit test suite (e.g. `node --test`) around the pure functions, and a CI job
that runs `ncc build` and fails if `git diff --exit-code dist/` is dirty (the standard
"check-dist" guard for JS actions). See [RECOMMENDATIONS.md](RECOMMENDATIONS.md).

### H6 — No CI at all for build/lint/test
**Where:** [`.github/workflows/`](../.github/workflows) contains only release/cleanup
automation; there is no push/PR validation workflow.

**What's wrong:** Nothing runs on pull requests. Combined with H5, there is no automated gate
on correctness, bundle freshness, or style before merge to `develop`/`main`.

**Impact:** All quality enforcement is manual. Broken or unbuilt changes can merge unnoticed.

**Fix:** Add a `ci.yml` triggered on `pull_request`/`push` that installs deps, lints, runs
tests, rebuilds `dist/`, and asserts no diff.

---

## 🟨 Medium

### M1 — `delete-old-runs.yml`: `workflow_dispatch` defaults don't apply to the `schedule` run
**Where:** [`.github/workflows/delete-old-runs.yml:8-9`](../.github/workflows/delete-old-runs.yml)
(cron) with inputs consumed at lines 71-79.

**What's wrong:** Input `default:` values only populate for **manual** `workflow_dispatch`
runs. On the monthly `schedule` trigger, `github.event.inputs.*` are all empty, so
`retain_days`, `keep_minimum_runs`, `delete_workflow_by_state_pattern`, etc. are passed as
empty strings.

**Impact:** The scheduled cleanup — the main purpose of the workflow — does not use the
intended `days: 30` / `minimum_runs: 6` values and may behave unexpectedly (over-delete or
error), quietly.

**Fix:** Provide fallbacks at the use site, e.g. `retain_days: ${{ github.event.inputs.days || 30 }}`,
`keep_minimum_runs: ${{ github.event.inputs.minimum_runs || 6 }}`, and default the pattern
inputs to `'All'`.

### M2 — Two declared dependencies are never used
**Where:** [`package.json:4`](../package.json) (`@actions/github`) and
[`package.json:6`](../package.json) (`node-fetch`).

**What's wrong:** `src/index.js` imports only `@actions/core`, `js-yaml`, `semver` (plus core
`fs`/`child_process`). `@actions/github` and `node-fetch` are unreferenced. `fetch` used at
`src/index.js:59` is the Node 24 global, not `node-fetch` (which is ESM-only and could not be
`require`d here anyway).

**Impact:** Dead dependencies enlarge the bundle and mislead maintainers. Note the irony:
`@actions/github` is exactly the client that should replace the hand-rolled fetch in H2.

**Fix:** Remove `node-fetch`. Remove `@actions/github` *or* (preferably) adopt it to fix H2.

### M3 — `getLatestTag` swallows all errors and falls back to `0.0.0`
**Where:** [`src/index.js:17-20`](../src/index.js).

```js
} catch { /* fallthrough */ }
return '0.0.0';
```

**What's wrong:** Any git failure (not just "no tags") is indistinguishable from a fresh repo.
The `0.0.0` sentinel then makes `getMergedPRs` walk **all** history (`src/index.js:41`) and
`bumpVersion` start from zero.

**Impact:** A transient git error silently produces a wrong version and a full-history notes
regeneration instead of failing loudly.

**Fix:** Distinguish "no tags found" from "git errored." Let real errors propagate to
`core.setFailed`; only use the `0.0.0` baseline when the tag list is genuinely empty.

### M4 — `substitutePlaceholders` replaces only the first `$COMPUTED_VERSION`
**Where:** [`src/index.js:121-127`](../src/index.js).

```js
cfg[k] = cfg[k].replace('$COMPUTED_VERSION', version);  // first occurrence only
```

**What's wrong:** `String.prototype.replace(string, ...)` replaces a single occurrence. A
`title`/`tag` template referencing `$COMPUTED_VERSION` more than once is only partially
substituted.

**Impact:** Malformed release title/tag whenever the placeholder appears twice.

**Fix:** Use `replaceAll('$COMPUTED_VERSION', version)` (or a global regex).

### M5 — `package.json` is missing standard metadata and scripts
**Where:** [`package.json`](../package.json) (only `dependencies` + `devDependencies`).

**What's wrong:** No `name`, `version`, `description`, `license`, `private`, `engines`, or
`scripts`. Building relies on the ad-hoc [`tools/build.sh`](../tools/build.sh) rather than
`npm run build`. There is no `"private": true` guard against accidental `npm publish`, and no
`engines` pin documenting the Node 24 requirement that `action.yml` assumes.

**Impact:** Weaker supply-chain hygiene, no conventional build entry point, publish risk,
undocumented runtime requirement.

**Fix:** Add `name`, `version`, `description`, `license: "MIT"`, `"private": true`,
`engines: { "node": ">=24" }`, and `scripts` (`build`, `test`, `lint`, `package`).

---

## 🟦 Low

### L1 — README examples drift from the live workflows
**Where:** [`README.md:37-38`](../README.md) uses `actions/checkout@v5` and
[`README.md:70`](../README.md) uses `softprops/action-gh-release@v2`; the workflow uses
`actions/checkout@v6` ([`draft-release.yml:19`](../.github/workflows/draft-release.yml)) and
`action-gh-release@v3` ([`draft-release.yml:50`](../.github/workflows/draft-release.yml)).
Example labels also differ (`significant` vs `[scope] significant`).

**What's wrong:** Both action versions are valid (v6 and v3 exist), but the README trails the
workflow and uses a different label convention, so copy-pasting the README yields a config that
doesn't match the project's own labels.

**Impact:** Confusion for adopters; examples that don't reproduce the maintainers' setup.

**Fix:** Align README examples with the workflows (versions and label names), or explicitly
note they are illustrative.

### L2 — External actions and the self-reference are pinned to mutable tags
**Where:** [`draft-release.yml:25`](../.github/workflows/draft-release.yml)
(`enhantica/drafterino@develop`), plus `@v6`/`@v3` on third-party actions; README recommends
`enhantica/drafterino@v2`.

**What's wrong:** Mutable major tags (and especially a moving `@develop` branch) can change
under you. Pinning your own release automation to `@develop` means an in-progress dev change
can alter production release behavior.

**Impact:** Supply-chain and reproducibility risk; non-deterministic CI.

**Fix:** Pin third-party actions to full commit SHAs (with a comment naming the version); use
Dependabot to bump them. For the self-reference, pin to a released tag on `main`.

### L3 — Empty commit range triggers a wasted, malformed API call
**Where:** [`src/index.js:44-45`](../src/index.js).

**What's wrong:** When `git log <tag>..HEAD` is empty, `''.split('\n')` yields `['']`, so the
map runs once with `sha === ''` and requests `/commits//pulls` (a guaranteed 404, silently
ignored per H2).

**Impact:** One pointless API call and a misleading log line on no-op runs.

**Fix:** `.split('\n').filter(Boolean)` before mapping; short-circuit when there are no commits.

### L4 — Tag name is interpolated into a shell command string
**Where:** [`src/index.js:41`](../src/index.js): `` `git log ${prevTag}..HEAD ...` `` via `execSync`.

**What's wrong:** `prevTag` comes from `git tag` output, so it is low-risk, but building shell
strings from dynamic values is a fragile pattern.

**Impact:** Low. Defense-in-depth only.

**Fix:** Use `execFileSync('git', ['log', `${prevTag}..HEAD`, '--pretty=format:%H'])` to avoid
the shell entirely (apply the same to the other `execSync` git calls).

### L5 — Deprecated `groot-preview` Accept header
**Where:** [`src/index.js:54`](../src/index.js): `Accept: application/vnd.github.groot-preview+json`.

**What's wrong:** "List pull requests associated with a commit" graduated from preview to GA
long ago; the preview media type is legacy.

**Impact:** Works today, but relies on a deprecated preview header.

**Fix:** Drop the preview Accept header (or, with Octokit per H2, this is handled for you).

### L6 — A PR can appear in multiple release-note sections
**Where:** [`src/index.js:137-142`](../src/index.js) (`generateNotes`).

**What's wrong:** Each section independently tests its label set, so a PR whose labels span two
sections is listed in both. There is no de-duplication or "first match wins" rule.

**Impact:** Duplicate entries in the notes for multi-labeled PRs.

**Fix:** Decide the desired semantics (first-match-only vs. intentional multi-listing) and
implement/document it; de-duplicate if single-listing is intended.

### L7 — Logging uses raw `console.log` instead of the Actions core logger
**Where:** throughout `src/index.js` (e.g. `src/index.js:26`, `src/index.js:68`, `src/index.js:94`).

**What's wrong:** `core.info`/`core.debug`/`core.warning`/`core.error` integrate with the
Actions log UI (grouping, `::debug::` gating, annotations). Raw `console.log` with emoji does
not, and debug-level chatter can't be toggled off.

**Impact:** Noisier logs, no annotations, no debug gating.

**Fix:** Route messages through `@actions/core` (already a dependency); use `core.warning` for
the `⚠️` paths and `core.debug` for verbose output.

---

## ⬜ Lowest

### LO1 — Large blocks of commented-out dead code
**Where:** [`src/index.js`](../src/index.js): lines 70, 84, 156, 162-171, 190-202, 208.

**What's wrong:** Remnants of a removed `files` input and debug logging clutter the source and
obscure the real logic.

**Fix:** Delete dead code; recover it from git history if ever needed.

### LO2 — `action.yml` has no `branding`
**Where:** [`action.yml`](../action.yml).

**What's wrong:** Marketplace-listed actions typically set `branding: { icon, color }` for a
recognizable listing.

**Fix:** Add a `branding` block.

### LO3 — Missing repository hygiene files
**Where:** repo root / `.github/`.

**What's wrong:** No `dependabot.yml`, `CODEOWNERS`, `CONTRIBUTING.md`, `SECURITY.md`, or
issue/PR templates.

**Fix:** Add the ones that fit the project's process; `dependabot.yml` is especially valuable
given L2.

### LO4 — Build/install scripts are fragile and duplicate `package.json`
**Where:** [`tools/build.sh`](../tools/build.sh), [`tools/install.sh`](../tools/install.sh).

**What's wrong:** No shebang, not marked executable, and `install.sh` re-lists dependencies by
hand (`npm install @actions/core ... node-fetch`) — which will drift from `package.json` and
reintroduces the unused deps from M2. `npm ci` from the lockfile is the reproducible approach.

**Fix:** Replace both with `npm` scripts (`build`, `package`) and use `npm ci` for installs;
if the shell scripts stay, add shebangs and stop re-declaring deps.

### LO5 — README lacks Inputs/Outputs/Permissions reference
**Where:** [`README.md`](../README.md).

**What's wrong:** The action's `config` schema (all keys), its outputs (`version`, `tag_name`,
`release_name`, `release_notes` from `src/index.js:204-207`), the required `GITHUB_TOKEN`, and
the `contents: write` permission are only shown implicitly in one example.

**Fix:** Add explicit Inputs, Outputs, and Permissions tables, and note the `.postN` scheme
(ties to H4).

### LO6 — `note-template` left in the workflow config despite being unimplemented
**Where:** [`.github/workflows/draft-release.yml:30`](../.github/workflows/draft-release.yml).

**What's wrong:** The project's own workflow sets a key the code ignores (see H3), modeling a
non-functional configuration for anyone who copies it.

**Fix:** Remove it until implemented, or implement H3.
