# Verify release asset

A guard workflow that fails loudly when a published release is missing the
HACS download asset.

## Intent

`hacs.json` sets `zip_release: true` with `filename: cowboy-ha.zip`, so HACS
downloads the release asset rather than the source tree. If that asset is
absent, every HACS install and update of that version fails with a 404.

This happened on v1.3.0 (#126). The `Release` workflow triggered correctly on
`release: published`, but GitHub never allocated a runner:

> The job was not acquired by Runner of type hosted even after multiple attempts

The run failed after ~16 minutes without executing a single step, so the zip
was never built or uploaded. The release itself stayed published and looked
healthy — nothing surfaced the problem until two users reported broken
installs a day later.

The failure mode is what matters here, not the specific cause: a published
release with no asset is silently broken for every HACS user, and the existing
workflow cannot detect it.

## Architecture

A separate workflow, `.github/workflows/verify-release-asset.yml`, that
resolves a target release, confirms the expected asset is attached, and opens
a tracking issue if it is not.

Triggers:

- `release: published` — the primary check, running alongside `Release`.
- `schedule` (daily) — a backstop, checking the latest release. Covers the
  case where the release-triggered guard run itself fails to start, which is
  exactly the failure being guarded against.
- `workflow_dispatch` — manual re-check, with an optional tag input.

Flow:

1. Read `hacs.json` for `zip_release` and `filename`. Exit early if
   `zip_release` is not `true` — HACS installs from source then, and a missing
   asset is not a problem.
2. Resolve the tag: the event's tag on `release`, the dispatch input if given,
   otherwise the latest release.
3. Poll the releases API until an asset with that filename reaches state
   `uploaded`.
4. If it never appears, open a deduplicated issue and fail the job.

## Decisions & trade-offs

**Separate workflow, not a step in `Release`.** A verification step appended
to `Release` cannot catch this failure: when no runner is acquired, no step
runs at all, so the check would be skipped along with everything else. Only a
job that fails independently surfaces it.

**`release: published` rather than `workflow_run` on `Release`.** A
`workflow_run: completed` trigger would also have fired here, but it couples
the guard to the `Release` workflow's identity and misses releases where
`Release` never got queued. Triggering on the release event itself keeps the
guard independent of how — or whether — the build ran.

**Poll for 25 minutes on release events.** `Release` gives up after ~16
minutes when it cannot acquire a runner, and completes in ~10 seconds when
healthy. Polling past the 16-minute mark avoids a false alarm while `Release`
is still retrying. Scheduled and manual runs check once, since they inspect
releases that are already long published.

**Open an issue instead of relying on a failed run.** A failed workflow run is
the notification that already went unnoticed on v1.3.0. An issue is visible in
the same place users report the problem, and dedupes naturally against the
daily backstop. The job also exits non-zero so the run itself is red.

**Read the filename from `hacs.json`.** The expected asset name lives in one
place; the guard cannot drift from what HACS actually requests.

## Non-goals

- No change to `.github/workflows/release.yml`. The build logic is correct and
  succeeded unchanged on every prior release.
- No automatic re-run or self-healing. Recovery is a one-line
  `gh run rerun <id> --failed`, and a guard that retries builds on its own is
  harder to reason about than one that reports.
- No verification of the zip's *contents*. Scope is presence of the asset.

## Implementation checklist

- [x] Write spec
- [x] Add `.github/workflows/verify-release-asset.yml`
- [x] Validate workflow syntax (`actionlint` clean, `bash -n` on every step)
- [x] Dry-run the check logic against v1.3.0 (asset present) and against a
      nonexistent tag and a wrong filename (both report missing, no crash)
