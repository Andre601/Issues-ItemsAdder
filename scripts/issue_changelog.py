import os
import json
import requests
from datetime import datetime

TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["SOURCE_REPO"]
TARGET_REPO = os.environ["TARGET_REPO"]
TARGET_ISSUE = int(os.environ["TARGET_ISSUE"])

SNAPSHOT_FILE = "issues_snapshot.json"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

def fetch_issues():
    url = f"https://api.github.com/repos/{REPO}/issues"
    params = {"state": "open", "per_page": 100}
    issues = []
    
    while url:
        res = requests.get(url, headers=HEADERS, params=params)
        res.raise_for_status()
        issues.extend(res.json())

        url = res.links.get("next", {}).get("url")

    return [i for i in issues if "pull_request" not in i]

def load_snapshot():
    if not os.path.exists(SNAPSHOT_FILE):
        return {}

    with open(SNAPSHOT_FILE) as f:
        return json.load(f)

def save_snapshot(data):
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def build_index(issues):
    index = {}
    for i in issues:
        index[str(i["number"])] = {
            "title": i["title"],
            "updated_at": i["updated_at"],
            "comments": i["comments"],
            "labels": sorted([l["name"] for l in i["labels"]]),
            "author": i["user"]["login"],
        }
    return index

def compare(old, new):
    new_issues = []
    closed_issues = []
    updated_comments = []
    label_changes = []

    for num, data in new.items():
        if num not in old:
            new_issues.append((num, data))
            continue

        prev = old[num]

        if data["comments"] > prev["comments"]:
            updated_comments.append((num, data))

        old_labels = set(prev["labels"])
        new_labels = set(data["labels"])

        added = new_labels - old_labels
        removed = old_labels - new_labels

        if added or removed:
            label_changes.append((num, added, removed))

    for num, prev_data in old.items():
        if num not in new:
            closed_issues.append((num, prev_data))

    return new_issues, closed_issues, updated_comments, label_changes

def format_changelog(new_issues, closed_issues, updated_comments, label_changes):
    if not any([new_issues, closed_issues, updated_comments, label_changes]):
        return None

    lines = ["### Issues Activity Summary", "There have been changes in the Issue Tracker since the last check. Changes are listed below!"]

    if new_issues:
        lines.append("\n#### New Issues")
        for num, d in new_issues:
            lines.append(f"- #{num} by {d['author']}")

    if closed_issues:
        lines.append("\n#### Closed Issues")
        for num, d in closed_issues:
            lines.append(f"- #{num}")
    
    if updated_comments:
        lines.append("\n#### Updated Comments")
        for num, d in updated_comments:
            lines.append(f"- #{num} ({d['comments']} Comments)")

    if label_changes:
        lines.append("\n#### Label Changes")
        for num, added, removed in label_changes:
            lines.append(f"- #{num}")
            if added:
                lines.append(f"    - Added `{'`, `'.join(added)}`")
            if removed:
                lines.append(f"    - Removed `{'`, `'.join(removed)}`")

    return "\n".join(lines)

def post_comment(body):
    url = f"https://api.github.com/repos/{TARGET_REPO}/issues/{TARGET_ISSUE}/comments"
    requests.post(url, headers=HEADERS, json={"body": body}).raise_for_status()

def main():
    issues = fetch_issues()
    current = build_index(issues)
    previous = load_snapshot()

    new_issues, closed_issues, updated_comments, label_changes = compare(previous, current)

    changelog = format_changelog(new_issues, closed_issues, updated_comments, label_changes)

    if changelog:
        post_comment(changelog)

    save_snapshot(current)

if __name__ == "__main__":
    main()
