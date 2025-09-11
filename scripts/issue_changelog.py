import os
import json
import requests
from datetime import datetime

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
REPO = os.environ['REPO']
TARGET_ISSUE = int(os.environ.get('TARGET_ISSUE', 1))  # Default to issue #1
SNAPSHOT_FILE = 'issue_snapshot.json'

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
}

def fetch_issues(state='all'):
    issues = []
    page = 1
    while True:
        url = f'https://api.github.com/repos/{REPO}/issues?state={state}&page={page}&per_page=100'
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        issues.extend(data)
        page += 1
    return [i for i in issues if 'pull_request' not in i]  # Exclude PRs

def get_issue_data(issue):
    return {
        'number': issue['number'],
        'title': issue['title'],
        'state': issue['state'],
        'comments': issue['comments'],
        'labels': sorted([l['name'] for l in issue['labels']]),
        'updated_at': issue['updated_at'],
    }

def load_snapshot():
    if not os.path.exists(SNAPSHOT_FILE):
        return {}
    with open(SNAPSHOT_FILE, 'r') as f:
        return json.load(f)

def save_snapshot(snapshot):
    with open(SNAPSHOT_FILE, 'w') as f:
        json.dump(snapshot, f, indent=2)

def compare_snapshots(old, new):
    changes = {'new': [], 'closed': [], 'comments': [], 'labels': []}
    old_keys = set(old)
    new_keys = set(new)

    for key in new_keys - old_keys:
        changes['new'].append(new[key])

    for key in old_keys - new_keys:
        changes['closed'].append(old[key])

    for key in new_keys & old_keys:
        if new[key]['comments'] > old[key]['comments']:
            changes['comments'].append(new[key])
        if new[key]['labels'] != old[key]['labels']:
            changes['labels'].append(new[key])

    return changes

def format_changelog(changes):
    if not any(changes.values()):
        return nil
    
    lines = [f"### Issue Activity Summary ({datetime.utcnow().isoformat()} UTC)\n"]

    if changes['new']:
        lines.append("#### 🆕 New Issues")
        for issue in changes['new']:
            lines.append(f"- #{issue['number']} {issue['title']}")

    if changes['closed']:
        lines.append("#### ✅ Closed Issues")
        for issue in changes['closed']:
            lines.append(f"- #{issue['number']} {issue['title']}")

    if changes['comments']:
        lines.append("#### 💬 New Comments")
        for issue in changes['comments']:
            lines.append(f"- #{issue['number']} {issue['title']} ({issue['comments']} comments)")

    if changes['labels']:
        lines.append("#### 🏷️ Label Changes")
        for issue in changes['labels']:
            lines.append(f"- #{issue['number']} {issue['title']} (Labels: {', '.join(issue['labels'])})")

    return "\n".join(lines)

def post_comment(issue_number, body):
    url = f'https://api.github.com/repos/{REPO}/issues/{issue_number}/comments'
    response = requests.post(url, headers=HEADERS, json={'body': body})
    response.raise_for_status()

def main():
    current_issues_raw = fetch_issues()
    current_issues = {str(i['number']): get_issue_data(i) for i in current_issues_raw}

    old_snapshot = load_snapshot()

    if not old_snapshot:
        print("First run detected. Saving snapshot and skipping changelog.")
        save_snapshot(current_issues)
        return

    changes = compare_snapshots(old_snapshot, current_issues)
    changelog = format_changelog(changes)

    if changelog:
        post_comment(TARGET_ISSUE, changelog)

    save_snapshot(current_issues)

if __name__ == '__main__':
    main()
