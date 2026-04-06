#!/usr/bin/env python3
"""Generate a GitHub work report for a given time window.

Supports multiple GitHub tokens to aggregate activity across accounts.
Set GH_TOKEN (primary) and optionally GH_TOKEN_SECONDARY for a second account.

Usage:
    python3 generate-report.py [--days N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
    python3 generate-report.py --days 7
    python3 generate-report.py --start 2026-03-18 --end 2026-04-01
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

# Repos to exclude
EXCLUDE_REPOS = {
    "nlscng/meta-runner",
    "nlscng/turbo-doodle",
}

# Only include repos from these owners (empty = no filter)
INCLUDE_OWNERS = {
    "cloud-ecosystem-security",
    "nelsoncheng_microsoft",
    "nlscng",
}


def run_gh(args: list[str], token: str | None = None) -> str:
    env = os.environ.copy()
    if token:
        env["GH_TOKEN"] = token
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True, text=True, timeout=120, env=env,
    )
    if result.returncode != 0:
        print(f"  warn: gh {' '.join(args[:3])}... failed: {result.stderr.strip()}", file=sys.stderr)
        return "[]"
    return result.stdout


def get_tokens() -> list[tuple[str | None, str]]:
    """Return list of (token, label) pairs for all configured accounts."""
    tokens = []
    primary = os.environ.get("GH_TOKEN")
    secondary = os.environ.get("GH_TOKEN_SECONDARY")
    if primary:
        tokens.append((primary, "primary"))
    else:
        tokens.append((None, "default"))
    if secondary:
        tokens.append((secondary, "secondary"))
    return tokens


def gather_repos(start_date: str) -> list[dict]:
    query = """query($cursor: String) {
      viewer {
        repositories(first: 100, after: $cursor, orderBy: {field: PUSHED_AT, direction: DESC}) {
          pageInfo { hasNextPage endCursor }
          nodes {
            nameWithOwner url description pushedAt homepageUrl isPrivate
          }
        }
      }
    }"""
    all_repos: dict[str, dict] = {}
    for token, label in get_tokens():
        print(f"  Gathering repos ({label})...", file=sys.stderr)
        raw = run_gh([
            "api", "graphql", "--paginate",
            "-f", f"query={query}",
            "--jq", f'.data.viewer.repositories.nodes[] | select(.pushedAt >= "{start_date}")',
        ], token=token)
        for line in raw.strip().splitlines():
            if line.strip():
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        name = obj.get("nameWithOwner", "")
                        if name not in all_repos:
                            all_repos[name] = obj
                except json.JSONDecodeError:
                    pass
    return [r for r in all_repos.values() if should_include(r.get("nameWithOwner", ""))]


def gather_prs_for_user(username: str, start_date: str, token: str | None) -> list[dict]:
    fields = "number,title,repository,state,createdAt,closedAt,url"
    created = json.loads(run_gh([
        "search", "prs", f"--author={username}", f"--created=>{start_date}",
        "--limit", "500", "--json", fields,
    ], token=token))
    merged = json.loads(run_gh([
        "search", "prs", f"--author={username}", f"--merged-at=>{start_date}",
        "--limit", "500", "--json", fields,
    ], token=token))
    return created + merged


def gather_prs(start_date: str) -> list[dict]:
    all_prs: list[dict] = []
    for token, label in get_tokens():
        # Resolve username for this token
        user_json = run_gh(["api", "/user", "--jq", ".login"], token=token).strip()
        username = user_json if user_json and not user_json.startswith("[") else "@me"
        print(f"  Gathering PRs for {username} ({label})...", file=sys.stderr)
        all_prs.extend(gather_prs_for_user(username, start_date, token))

    seen: set[str] = set()
    result: list[dict] = []
    for pr in all_prs:
        if pr["url"] not in seen:
            seen.add(pr["url"])
            repo = pr.get("repository", {})
            name = repo.get("nameWithOwner", "") if isinstance(repo, dict) else str(repo)
            if should_include(name):
                result.append(pr)
    return sorted(result, key=lambda p: p["createdAt"])


def gather_issues(start_date: str) -> list[dict]:
    fields = "number,title,repository,state,createdAt,url"
    all_issues: list[dict] = []
    for token, label in get_tokens():
        user_json = run_gh(["api", "/user", "--jq", ".login"], token=token).strip()
        username = user_json if user_json and not user_json.startswith("[") else "@me"
        print(f"  Gathering issues for {username} ({label})...", file=sys.stderr)
        issues = json.loads(run_gh([
            "search", "issues", f"--author={username}", f"--created=>{start_date}",
            "--limit", "200", "--json", fields,
        ], token=token))
        all_issues.extend(issues)

    seen: set[str] = set()
    result: list[dict] = []
    for i in all_issues:
        if i["url"] not in seen:
            seen.add(i["url"])
            if should_include(i.get("repository", {}).get("nameWithOwner", "")):
                result.append(i)
    return result


def should_include(name_with_owner: str) -> bool:
    if name_with_owner in EXCLUDE_REPOS:
        return False
    if INCLUDE_OWNERS:
        owner = name_with_owner.split("/")[0] if "/" in name_with_owner else ""
        return owner in INCLUDE_OWNERS
    return True


def group_by_repo(prs: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for pr in prs:
        repo = pr.get("repository", {})
        name = repo.get("nameWithOwner", "unknown") if isinstance(repo, dict) else str(repo)
        groups.setdefault(name, []).append(pr)
    return dict(sorted(groups.items()))


def state_icon(state: str) -> str:
    return {"merged": "✅", "closed": "❌", "open": "🔵"}.get(state, "⬜")


def generate_report(start_date: str, end_date: str, days: int) -> str:
    print(f"Gathering data for {start_date} → {end_date} ({days} days)...", file=sys.stderr)

    repos = gather_repos(start_date)
    prs = gather_prs(start_date)
    issues = gather_issues(start_date)
    by_repo = group_by_repo(prs)

    merged = sum(1 for p in prs if p["state"] == "merged")
    closed = sum(1 for p in prs if p["state"] == "closed")
    open_prs = sum(1 for p in prs if p["state"] == "open")

    period_label = f"{days} days"
    if days >= 28 and days <= 31:
        period_label += " (Monthly)"
    elif days >= 85 and days <= 95:
        period_label += " (Quarterly)"

    lines = []
    lines.append(f"# GitHub Activity Report: {start_date} → {end_date}\n")
    lines.append(f"> **Generated**: {datetime.utcnow().strftime('%Y-%m-%d')}")
    lines.append(f"> **Period**: {period_label}\n")

    # Summary table
    lines.append("## Activity Summary\n")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Projects active | {len(repos)} |")
    lines.append(f"| PRs created | {len(prs)} |")
    lines.append(f"| PRs merged | {merged} |")
    lines.append(f"| PRs open | {open_prs} |")
    lines.append(f"| Issues opened | {len(issues)} |")
    lines.append("")

    # PR distribution pie chart
    if len(by_repo) > 1:
        lines.append("## PR Distribution\n")
        lines.append("```mermaid")
        lines.append("pie title PRs by Project")
        for repo, repo_prs in by_repo.items():
            short = repo.split("/")[-1]
            lines.append(f'    "{short}" : {len(repo_prs)}')
        lines.append("```\n")

    # Gantt timeline (top 20 PRs)
    if prs:
        lines.append("## Activity Timeline\n")
        lines.append("```mermaid")
        lines.append("gantt")
        lines.append(f"    title PR Activity ({start_date} → {end_date})")
        lines.append("    dateFormat YYYY-MM-DD")
        for repo, repo_prs in by_repo.items():
            short = repo.split("/")[-1]
            lines.append(f"    section {short}")
            for pr in repo_prs[:10]:
                title = pr["title"][:40].replace('"', "'")
                created = pr["createdAt"][:10]
                closed_at = (pr.get("closedAt") or end_date)[:10]
                if closed_at < created:
                    closed_at = created
                status = "done" if pr["state"] == "merged" else ("active" if pr["state"] == "open" else "done")
                lines.append(f"    #{pr['number']} {title} :{status}, {created}, {closed_at}")
        lines.append("```\n")

    # PRs by project
    lines.append("## Pull Requests\n")
    for repo, repo_prs in by_repo.items():
        lines.append(f"### {repo}\n")
        lines.append("| # | Title | Status | Created |")
        lines.append("|---|-------|--------|---------|")
        for pr in repo_prs:
            icon = state_icon(pr["state"])
            date = pr["createdAt"][:10]
            lines.append(f"| [#{pr['number']}]({pr['url']}) | {pr['title']} | {icon} {pr['state'].title()} | {date} |")
        lines.append("")

    # Issues
    if issues:
        lines.append("## Issues\n")
        lines.append("| # | Title | Repository | Status |")
        lines.append("|---|-------|-----------|--------|")
        for i in issues:
            repo = i.get("repository", {}).get("nameWithOwner", "")
            icon = "✅" if i["state"] == "closed" else "🔵"
            lines.append(f"| [#{i['number']}]({i['url']}) | {i['title']} | {repo} | {icon} {i['state'].title()} |")
        lines.append("")

    # Active repos
    lines.append("## Active Repositories\n")
    lines.append("| Repository | Description | Last Push |")
    lines.append("|-----------|-------------|-----------|")
    for r in repos:
        desc = (r.get("description") or "—")[:80]
        pushed = r["pushedAt"][:10]
        lines.append(f"| [{r['nameWithOwner']}]({r['url']}) | {desc} | {pushed} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate GitHub work report")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--start", type=str, default="")
    parser.add_argument("--end", type=str, default="")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    if args.start and args.end:
        start_date = args.start
        end_date = args.end
        d0 = datetime.strptime(start_date, "%Y-%m-%d")
        d1 = datetime.strptime(end_date, "%Y-%m-%d")
        days = (d1 - d0).days
    else:
        days = args.days
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    report = generate_report(start_date, end_date, days)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
