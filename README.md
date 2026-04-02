# gh-work-reports

Automated GitHub activity reports with GitHub Pages site.

## How it works

- **Weekly** (Monday 08:00 UTC): Generates a 7-day report automatically
- **Monthly** (1st of month): Generates a 30-day report automatically
- **On-demand**: Trigger manually from Actions tab with custom day range
- Reports are committed to `docs/reports/` and deployed to GitHub Pages

## Setup

### 1. Create a PAT (Personal Access Token)

Create a **fine-grained** or **classic** PAT from your **EMU account** (`nelsoncheng_microsoft`) with `repo` scope. This is what lets the workflows see private org repos.

1. Go to https://github.com/settings/tokens (while logged in as the EMU account)
2. Generate new token → Classic → scope: `repo`, `read:org`
3. Copy the token

### 2. Add the secret

1. Go to this repo's Settings → Secrets and variables → Actions
2. New repository secret: `REPORT_TOKEN` = the PAT from step 1

### 3. Enable GitHub Pages

1. Go to Settings → Pages
2. Source: **GitHub Actions** (not "Deploy from a branch")

### 4. Run the first report

Go to Actions → "Weekly Work Report" → Run workflow → Pick days → Run

## Local usage

```bash
# Generate a 7-day report locally
./run.sh 7

# Custom date range
python3 scripts/generate-report.py --start 2026-03-18 --end 2026-04-01 --output docs/reports/report-2026-03-18-to-2026-04-01.md
python3 scripts/build-html.py
```

## Repo filtering

Only `cloud-ecosystem-security/*` repos are included. Personal repos are excluded.
Edit `EXCLUDE_REPOS` and `INCLUDE_OWNERS` in `scripts/generate-report.py` to adjust.

## Architecture

```
.github/workflows/
  weekly-report.yml     # Cron: every Monday
  monthly-report.yml    # Cron: 1st of month
scripts/
  generate-report.py    # Gathers data via gh CLI, produces markdown
  build-html.py         # Converts markdown → HTML, updates index
docs/
  index.html            # Landing page (GitHub Pages)
  reports/              # Generated reports (.md + .html)
run.sh                  # Local runner
```
