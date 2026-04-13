# gh-work-reports

Automated GitHub activity reports with GitHub Pages site. Supports dual-account
aggregation (personal + EMU/work) so a single report covers all your activity.

## How it works

- **Weekly** (Monday 08:00 UTC): Generates a 7-day report automatically
- **Monthly** (1st of month): Generates a 30-day report automatically
- **On-demand**: Trigger manually from Actions tab with custom day range
- Reports are committed to `docs/reports/` and deployed to GitHub Pages

## Setup

### 1. Create PATs (Personal Access Tokens)

You need **two** PATs — one per GitHub account:

| Secret Name | Account | How to Create |
|---|---|---|
| `GH_WORK_REPORTS_TOKEN` | **nlscng** (personal) | [github.com/settings/tokens](https://github.com/settings/tokens) logged in as `nlscng` |
| `GH_WORK_REPORTS_TOKEN_MS` | **nelsoncheng_microsoft** (EMU) | [github.com/settings/tokens](https://github.com/settings/tokens) logged in as `nelsoncheng_microsoft` |

Both PATs need scopes: **`repo`** + **`read:org`**

- The **nlscng** PAT provides: personal repos (`nlscng/*`)
- The **nelsoncheng_microsoft** PAT provides: org repos (`cloud-ecosystem-security/*`) and EMU repos

### 2. Add the secrets

Go to [repo Settings → Secrets → Actions](https://github.com/nlscng/gh-work-reports/settings/secrets/actions) and add both:

```bash
# Or via CLI (logged in as nlscng):
gh secret set GH_WORK_REPORTS_TOKEN --repo nlscng/gh-work-reports
# Paste nlscng PAT when prompted

gh secret set GH_WORK_REPORTS_TOKEN_MS --repo nlscng/gh-work-reports
# Paste nelsoncheng_microsoft PAT when prompted
```

> **Single-account mode**: If only `GH_WORK_REPORTS_TOKEN` is set, reports
> will cover that account only. The secondary token is optional.

### 3. Enable GitHub Pages

1. Go to Settings → Pages
2. Source: **GitHub Actions** (not "Deploy from a branch")

### 4. Set up the self-hosted runner

The EMU enterprise disables GitHub-hosted runners, so this repo uses a
self-hosted runner on the WSL2 machine `nelsoncheng-wsl`.

**First-time setup:**

```bash
# Download and extract (update version as needed)
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -sL https://github.com/actions/runner/releases/latest/download/actions-runner-linux-x64-2.333.1.tar.gz \
  | tar xz

# Register with the repo (get a fresh token each time)
TOKEN=$(gh api -X POST repos/nlscng/gh-work-reports/actions/runners/registration-token --jq '.token')
./config.sh \
  --url https://github.com/nlscng/gh-work-reports \
  --token "$TOKEN" \
  --name "nelsoncheng-wsl" \
  --labels "self-hosted,Linux,X64,work-reports" \
  --unattended --replace

# Install as a systemd service (survives reboots)
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status   # verify it's active
```

**Managing the service:**

```bash
sudo ./svc.sh status     # check runner health
sudo ./svc.sh stop       # stop the runner
sudo ./svc.sh start      # start again
sudo ./svc.sh uninstall  # remove the service entirely
```

**Re-registering** (if the runner gets orphaned):

```bash
cd ~/actions-runner
sudo ./svc.sh stop
REMOVE_TOKEN=$(gh api -X POST repos/nlscng/gh-work-reports/actions/runners/remove-token --jq '.token')
./config.sh remove --token "$REMOVE_TOKEN"
# Then repeat the registration steps above
```

### 5. Run the first report

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

Activity from all three owners is included: `cloud-ecosystem-security`, `nelsoncheng_microsoft`, `nlscng`.
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
