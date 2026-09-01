# Upstream Synchronization

CodexVideo is published with a standalone snapshot history so its GitHub contributor
list reflects work performed on CodexVideo itself. The project preserves OpenMontage
attribution and licensing, but it does not merge OpenMontage commit ancestry into
the public `main` branch.

The local checkout uses two remotes:

```text
origin    https://github.com/tengbot/codexvideo.git
upstream  https://github.com/calesthio/OpenMontage.git
```

## Update Procedure

Start with a clean working tree. A fresh clone must add the upstream remote once:

```bash
git status --short
git remote add upstream https://github.com/calesthio/OpenMontage.git
git fetch upstream
```

If `upstream` already exists, skip `git remote add`. `UPSTREAM_BASE` records the
OpenMontage revision currently incorporated into CodexVideo. Import only the code
difference between that revision and the latest upstream revision:

```bash
BASE=$(cat UPSTREAM_BASE)
TARGET=$(git rev-parse upstream/main)
git diff --binary "$BASE" "$TARGET" | git apply --3way --index
```

This deliberately applies a patch instead of running `git merge upstream/main`.
Merging would reattach the complete upstream ancestry and repopulate GitHub's
CodexVideo contributor graph with upstream contributors.

Resolve conflicts by preserving both upstream infrastructure changes and the
CodexVideo business-layer extensions. Review every staged file, then update the
recorded baseline:

```bash
git rev-parse upstream/main > UPSTREAM_BASE
```

The most likely overlap areas are:

- `AGENT_GUIDE.md`
- `backlot/state.py`
- `docs/ARCHITECTURE.md`
- `lib/checkpoint.py`
- `schemas/artifacts/__init__.py`
- `remotion-composer/package.json`
- `remotion-composer/package-lock.json`

CodexVideo-specific pipelines, schemas, tools, tests, and skills use separate paths wherever possible so that most upstream updates merge without manual intervention.

## Required Verification

Run the combined Python contract suite:

```bash
.venv/bin/python -m pytest -p no:cacheprovider -q
```

Verify the Remotion project:

```bash
cd remotion-composer
npm install
npx tsc --noEmit
```

For changes that affect rendering, also run one product-promo campaign through planning, rendering, QA, and a second unchanged `resume` operation. The second run should render zero jobs and use only validated cached outputs.

## Publish the Update

After verification:

```bash
git add -A
git commit -m "Import latest OpenMontage changes"
git push origin main
```

Do not publish `.env` files, credentials, caches, project workspaces, downloaded media, or rendered videos.
