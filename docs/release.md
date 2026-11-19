# Release process

Readers use the `stable` branch; development happens on `main`. A release
promotes one commit of `main` to `stable` after **every runnable tutorial has
passed on every KServe version it lists** at that commit.

```text
PR ──(lint + affected e2e)──▶ main ──(release: full matrix passes)──▶ stable + tag YYYY.MM.N
                              development                              what readers use
```

## Rules

1. **Only `main` commits are released**, and `stable` only **fast-forwards**:
   it is always some earlier commit of `main`. No merge commits, no
   back-ports, no direct pushes to `stable`.
2. **Nothing is released unless the full matrix passes** at that exact commit
   (`./tut matrix --scheduled`: every tutorial that CI can run × every
   version in its `kserve.tested`). A missing report counts as a failure.
3. Rules, tests and the site build must pass at that commit (`make check`).
4. Versions are dates: `YYYY.MM.N`, `N` starting at 0 each month. A release is
   a snapshot that was verified on a given day, not an API version.
5. The site is published from `stable`, by the release workflow.

Tutorials that CI cannot run (`archived`, `requires.gpu`) are listed in the
notes as "not run in CI" and do not block a release.

## How to release

```bash skip
make release-plan            # next version, can stable move, what will be verified
make release                 # dry run on GitHub: verify everything, write notes, change nothing
make release DRY_RUN=false   # verify again and publish
```

`make release` starts `.github/workflows/release.yml`
(Actions → release → Run workflow does the same):

| Job | Does |
|---|---|
| `plan` | checks the commit is on `main` and `stable` can fast-forward to it; `make check`; picks the version and the matrix |
| `verify` | runs the full matrix at that commit (`run-tutorials.yml`, artifacts `report-release-*`) |
| `publish` | `./tut release check` (every entry passed), writes notes; unless dry run: pushes the commit to `stable`, creates the tag and GitHub Release |
| `site` | deploys the site from `stable` (only after a real publish) |

If `verify` fails, nothing is published; follow docs/ci-playbook.md, fix on
`main`, and release again.

## Repository settings (once, by a maintainer)

- **Protect `stable`**: Settings → Branches → add a rule for `stable` that
  blocks force pushes and deletion and restricts who can push. Allow
  **GitHub Actions** to push, or the release workflow cannot move the branch.
- **Pages**: Settings → Pages → Source: GitHub Actions (already enabled).

## Local helpers

```bash skip
./tut release next-version
./tut release can-ff <sha>
./tut release notes <version> <sha> [--reports DIR] [--repo owner/name]
./tut release check --reports DIR --expected matrix.json
```
