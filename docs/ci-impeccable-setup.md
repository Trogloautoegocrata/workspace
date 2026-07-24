# 🎨 CI/CD Setup: Impeccable Detect — Design Quality Gate (Gate 4)

> **Plan:** Plan Maestro Impeccable — Gate 4
> **Tool:** [Impeccable](https://github.com/pbakaus/impeccable) — Design quality CLI
> **Workflow template:** `.github/workflows/impeccable-detect.yml`

---

## 📋 Overview

Impeccable Detect is the **CI/CD quality gate** for design. It runs on every PR and push to `main`, scanning your codebase for design issues using configurable rulesets.

**Three workflow variants are provided:**

| Workflow file | Target repo | Scope | Threshold |
|---|---|---|---|
| `impeccable-detect.yml` | **Generic** — any repo | Entire project (`.`) | 70 |
| `impeccable-detect-thuban.yml` | **Thuban** (Next.js) | `src/components/` | 80 |

---

## 🚀 Installation Per Repo

### Option A: Monorepo (workspace)

The workflows live at `workspace/.github/workflows/` and activate automatically when pushed to the monorepo's `main` branch.

```bash
# Already in place — verify:
ls -la .github/workflows/impeccable-detect*.yml
```

Push to the monorepo and the generic workflow (`impeccable-detect.yml`) triggers on PRs/pushes to `main`.

### Option B: Thuban (independent repo)

```bash
# 1. Clone the repo
git clone git@github.com:Trogloautoegocrata/thuban.git
cd thuban

# 2. Create the workflows directory
mkdir -p .github/workflows

# 3. Copy the thuban-specific workflow
cp /path/to/workspace/.github/workflows/impeccable-detect-thuban.yml \
   .github/workflows/impeccable-detect.yml

# 4. Commit and push
git add .github/workflows/impeccable-detect.yml
git commit -m "chore(ci): add Impeccable Design Quality Gate (Gate 4)"
git push origin main
```

### Option C: Conexium (independent repo)

```bash
# 1. Clone the repo
git clone git@github.com:Trogloautoegocrata/Conexium.git
cd Conexium

# 2. Create the workflows directory
mkdir -p .github/workflows

# 3. Copy the generic workflow (adjust THRESHOLD_WARN as needed)
cp /path/to/workspace/.github/workflows/impeccable-detect.yml \
   .github/workflows/impeccable-detect.yml

# 4. Optionally customise the threshold
#    Edit .github/workflows/impeccable-detect.yml and change:
#      THRESHOLD_WARN: 70   →   THRESHOLD_WARN: 75

# 5. Commit and push
git add .github/workflows/impeccable-detect.yml
git commit -m "chore(ci): add Impeccable Design Quality Gate (Gate 4)"
git push origin main
```

---

## ⚙️ Customisation

### Variables (edit at the top of the workflow file)

| Variable | Default | Description |
|---|---|---|
| `THRESHOLD_WARN` | `70` | Minimum acceptable score (0–100). Below this → warning in PR comment. |
| `PATHS_TO_SCAN` | `.` | Directory/glob to scan. For Next.js apps usually `src/components/`. |

### Transitioning from Warning Mode → Failing Mode

The workflows ship with `continue-on-error: true` (warning mode). **To make design quality blocking:**

1. Open the workflow file
2. Change `continue-on-error: true` → `continue-on-error: false` on the **Run Impeccable Detect** step
3. Commit and push — CI will now fail if the score is below `THRESHOLD_WARN`

**Recommended transition plan:**
1. **Week 1–2:** Warning mode (monitor, fix issues)
2. **Week 3:** Lower threshold to soft fail at 60
3. **Week 4+:** Hard fail at desired threshold (70 generic, 80 Thuban)

---

## 📁 Artifacts

Every run produces an `impeccable-report.json` artifact (retained 30 days):
- Contains full scan results: issues, scores, metadata
- Download from the workflow run page on GitHub
- Machine-parseable for dashboards or trend analysis

Artifact names:
- Generic workflow: `impeccable-report`
- Thuban workflow: `impeccable-report-thuban`

---

## 🔍 Verification

After installation, verify the workflow is active:

1. **Push a PR** to the target repo → the `design-quality` job should appear in the Actions tab
2. **Check the PR comment** — Impeccable posts a formatted report as a PR comment
3. **Inspect the artifact** — `impeccable-report.json` should be downloadable from the run

### Manual local test (alternative)

```bash
# Run Impeccable locally (no GitHub required)
npx impeccable detect . --json

# To scope to a directory:
npx impeccable detect src/components/ --json

# Save to file:
npx impeccable detect . --json > report.json
```

---

## 🐛 Troubleshooting

**Q: Workflow doesn't appear in Actions tab**
A: Ensure the workflow is on the default branch (`main`) and the file has `.yml` extension in `.github/workflows/`.

**Q: `npx impeccable` fails with "command not found"**
A: Impeccable is fetched on-the-fly by `npx --yes`. If blocked by network, install globally: `npm install -g @pbakaus/impeccable`

**Q: PR comment not posted**
A: The `GITHUB_TOKEN` needs `pull-requests: write` permission. This is default for `GITHUB_TOKEN` but verify if org policies override it.

**Q: No issues found — empty report**
A: Run locally first to verify Impeccable can scan your codebase. Some languages/frameworks have limited rule coverage.

---

## 📐 Architecture

```
[PR or Push]
    │
    ▼
GitHub Actions Trigger
    │
    ├── checkout repo
    ├── setup Node.js 22
    ├── dependencies (npm ci / install)
    ├── npx impeccable detect <PATH> --json
    │       │
    │       ▼
    │   impeccable-report.json
    │       │
    │       ├── evaluate score vs THRESHOLD_WARN
    │       ├── comment findings on PR  ────►  developer sees feedback in PR
    │       └── upload artifact         ────►  downloadable JSON report
    │
    ▼
[CI passes / warns / fails]
```

---

## 📦 Requirements

- **Node.js 22** (set up by the workflow)
- **npm** (included with Node.js)
- **GitHub Actions** enabled on the repository
- **Internet access** for `npx` to fetch Impeccable

No additional secrets or tokens required — uses the default `GITHUB_TOKEN`.

---

*Part of the Plan Maestro Impeccable — Gate 4: CI/CD Quality Gate for Design*
