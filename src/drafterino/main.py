# SPDX-FileCopyrightText: 2025 drafterino contributors <https://github.com/enhantica/drafterino>
# SPDX-License-Identifier: MIT

import json
import os
import re
import requests
import semver
import sys
import yaml

from collections import defaultdict
from typing import Any
from typing import Dict
from typing import List


def parse_config() -> Dict[str, Any]:
    """
    Parse the YAML configuration from the CONFIG environment variable.

    Returns:
        Dict[str, Any]: Parsed configuration dictionary.

    Raises:
        ValueError: If CONFIG is not set or YAML parsing fails.
    """
    raw_config = os.environ.get('CONFIG')
    if not raw_config:
        raise ValueError("CONFIG environment variable not set")
    try:
        cfg = yaml.safe_load(raw_config)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML config: {e}")
    return cfg


def get_latest_tag() -> str:
    """
    Get the latest valid SemVer-compatible git tag in the repository.

    Returns:
        str: Latest valid SemVer tag string, or "0.0.0" if none found.
    """
    tags = os.popen("git tag --sort=-creatordate").read().splitlines()
    for tag in tags:
        cleaned = tag.lstrip('v')
        # Allow .postN suffix
        base = cleaned.split('.post')[0]
        try:
            semver.VersionInfo.parse(base)
            return tag
        except ValueError:
            continue
    return "0.0.0"


def get_merged_prs() -> List[Dict[str, Any]]:
    """
    Retrieve merged pull requests from the GitHub API that were merged after the latest tag.

    Returns:
        list: List of merged pull request dictionaries.
    """
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.isfile(event_path):
        print("⚠️ No event payload found, skipping PR lookup.")
        return []

    with open(event_path, "r") as f:
        event = json.load(f)

    repo = event.get("repository", {})
    owner = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")

    token = os.environ.get("GITHUB_TOKEN")
    if not (owner and repo_name and token):
        print("⚠️ Missing GitHub context for API call.")
        return []

    # Get the latest tag and corresponding merge commits since that tag
    prev_tag = get_latest_tag()
    log_cmd = f"git log {prev_tag}..HEAD --merges --pretty=format:%H"
    # Validate prev_tag and construct git log command safely
    if not prev_tag or prev_tag == "0.0.0":
        # No valid previous tag, get all merge commits up to HEAD
        log_args = ["git", "log", "--merges", "--pretty=format:%H"]
    else:
        log_args = ["git", "log", f"{prev_tag}..HEAD", "--merges", "--pretty=format:%H"]
    try:
        merge_shas = subprocess.check_output(log_args, text=True).splitlines()
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to run git log: {e}")
        return []

    if not merge_shas:
        print("⚠️ No merge commits found since latest tag.")
        return []

    url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls?state=closed&sort=updated&direction=desc&per_page=100"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch PRs: {response.status_code} {response.text}")

    all_merged_prs = [pr for pr in response.json() if pr.get("merged_at")]
    recent_merged_prs = [pr for pr in all_merged_prs if pr.get("merge_commit_sha") in merge_shas]

    return recent_merged_prs


def determine_bump(prs: List[Dict[str, Any]],
                   cfg: Dict[str, Any]) -> str:
    """
    Determine the version bump type based on PR labels and configuration.

    Args:
        prs (list): List of pull request dictionaries.
        cfg (dict): Configuration dictionary with bump label groups.

    Returns:
        str: Bump type ('major', 'minor', 'patch', 'post', or default).
    """
    label_groups = {
        'major': cfg.get("major-bump-labels", []),
        'minor': cfg.get("minor-bump-labels", []),
        'patch': cfg.get("patch-bump-labels", []),
        'post':  cfg.get("post-bump-labels", []),
    }

    print("🧪 Bump label groups from config:")
    for key, val in label_groups.items():
        print(f"   {key}-bump-labels: {val}")

    found = {k: False for k in label_groups}

    for pr in prs:
        pr_labels = [label['name'] for label in pr.get("labels", [])]
        for bump, labels in label_groups.items():
            if any(l in pr_labels for l in labels):
                found[bump] = True

    print("🔍 Bump decision flags:", found)

    if found['major']:
        return 'major'
    elif found['minor']:
        return 'minor'
    elif found['patch']:
        return 'patch'
    elif found['post']:
        return 'post'
    else:
        return cfg.get("default-bump", "post")


def bump_version(prev_version: str,
                 bump_type: str) -> str:
    """
    Compute the next version string based on the previous version and bump type.

    Args:
        prev_version (str): Previous version string.
        bump_type (str): Type of bump ('major', 'minor', 'patch', 'post').

    Returns:
        str: New version string.

    Raises:
        ValueError: If previous version is invalid or bump type unknown.
    """
    if 'post' in prev_version:
        base = prev_version.lstrip('v').split('.post')[0]
    else:
        base = prev_version.lstrip('v')

    try:
        next_ver = semver.VersionInfo.parse(base)
    except ValueError as e:
        raise ValueError(f"Invalid previous version: {base} ({e})")

    if bump_type == 'major':
        next_ver = next_ver.bump_major()
    elif bump_type == 'minor':
        next_ver = next_ver.bump_minor()
    elif bump_type == 'patch':
        next_ver = next_ver.bump_patch()
    elif bump_type == 'post':
        # Find last postN suffix
        match = re.search(r'\.post(\d+)', prev_version)
        n = int(match.group(1)) + 1 if match else 1
        return f"{base}.post{n}"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")

    return str(next_ver)


def generate_release_notes(prs: List[Dict[str, Any]],
                           cfg: Dict[str, Any]) -> str:
    """
    Generate release notes based on merged PRs and configuration sections.

    Args:
        prs (list): List of pull request dictionaries.
        cfg (dict): Configuration dictionary with release notes sections.

    Returns:
        str: Formatted release notes string.
    """
    note_sections = cfg.get("release-notes", [])
    grouped = defaultdict(list)

    for pr in prs:
        pr_labels = [label['name'] for label in pr.get("labels", [])]
        pr_title = pr.get("title", "Untitled")
        pr_number = pr.get("number", "")
        for section in note_sections:
            if any(label in pr_labels for label in section.get("labels", [])):
                entry = f"- {pr_title} (#{pr_number})"
                grouped[section["title"]].append(entry)

    notes = []
    for section in note_sections:
        title = section["title"]
        entries = grouped.get(title, [])
        if entries:
            notes.append(f"## {title}\n" + "\n".join(entries))

    return "\n\n".join(notes) if notes else "_No notable changes._"


def substitute_placeholders(cfg: Dict[str, Any],
                            computed_version: str) -> None:
    """
    Replace placeholder variables in config strings with the computed version.

    Args:
        cfg (Dict[str, Any]): Configuration dictionary to modify in-place.
        computed_version (str): Computed version string to inject into placeholders.
    """
    for key in ['tag', 'title']:
        if isinstance(cfg.get(key), str):
            cfg[key] = cfg[key].replace('$COMPUTED_VERSION', computed_version)


def run_release_workflow(cfg: Dict[str, Any]) -> None:
    """
    Run the draft release workflow including version bump and note generation.

    Args:
        cfg (Dict[str, Any]): Parsed configuration dictionary.
    """
    print("🔧 Starting release preparation...")

    pretty_cfg = yaml.dump(cfg, sort_keys=False, default_flow_style=False, indent=2)
    print("🔧 Loaded config:\n", pretty_cfg)

    prev = get_latest_tag()
    print("🔖 Latest tag:", prev)

    prs = get_merged_prs()
    print(f"📦 Merged PRs: {len(prs)}")

    bump = determine_bump(prs, cfg)
    print("🔧 Selected bump type:", bump)

    new_version = bump_version(prev, bump)
    print(f"🧮 Computed new version: {new_version}")

    substitute_placeholders(cfg, new_version)

    release_notes = generate_release_notes(prs, cfg)
    print("📝 Generated release notes:\n", release_notes)

    output_file = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(output_file, "a") as f:
        f.write(f"version={new_version}\n")
        f.write(f"tag_name={cfg.get('tag')}\n")
        f.write(f"release_name={cfg.get('title')}\n")
        f.write(f"release_notes<<EOF\n{release_notes}\nEOF\n")


def main() -> None:
    """
    Entrypoint for running the release draft logic.
    """
    try:
        cfg = parse_config()
        run_release_workflow(cfg)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
