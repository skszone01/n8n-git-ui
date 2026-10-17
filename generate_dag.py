#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Git DAG Generator for n8n-style UI (Zero-Server Architecture)
Generates an interactive visual topology from any Git repository:
- Central Primary Backbone (Lane 0) in the middle (main / master)
- Upper lanes (Lane -1, -2, -3...) for merged feature branches (collision-free)
- Lower lanes (Lane +1, +2, +3...) for active / ongoing feature branches (collision-free)
- Explicit Branch and Merge Bézier cables
- Real-time WIP Working Directory node for uncommitted changes
"""

import os
import sys
import json
import subprocess
import argparse
import tempfile
import time
import stat
from datetime import datetime
from collections import deque

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JS = os.path.join(CURRENT_DIR, "git_data.js")

def find_repo_root(custom_path=None):
    if custom_path and os.path.isdir(custom_path):
        return os.path.abspath(custom_path)
    candidate_parent2 = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
    candidate_parent1 = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
    if os.path.exists(os.path.join(candidate_parent2, ".git")):
        return candidate_parent2
    elif os.path.exists(os.path.join(candidate_parent1, ".git")):
        return candidate_parent1
    elif os.path.exists(os.path.join(CURRENT_DIR, ".git")):
        return CURRENT_DIR
    else:
        return os.getcwd()

REPO_ROOT = find_repo_root()

def run_git(args, cwd=None, check_err=True):
    """Run a git command in REPO_ROOT (or cwd) and return stdout."""
    target_dir = cwd or REPO_ROOT
    try:
        res = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", target_dir] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if res.returncode != 0 and check_err:
            err_msg = res.stderr.strip() if res.stderr else f"exit code {res.returncode}"
            sys.stderr.write(f"[WARNING] git {' '.join(args)} failed: {err_msg}\n")
        return res.stdout
    except Exception as e:
        if check_err:
            sys.stderr.write(f"[WARNING] Failed to execute git {' '.join(args)}: {e}\n")
        return ""

def write_atomic_file(target_path, content, encoding="utf-8"):
    """Atomically write content to target_path using tempfile.NamedTemporaryFile.

    Ensures data durability via flush() and os.fsync(fileno), closes file handle
    prior to os.replace for Windows compatibility, retries on transient Windows
    sharing violations, and guarantees cleanup on failure.
    """
    target_abs = os.path.abspath(target_path)
    target_dir = os.path.dirname(target_abs)
    os.makedirs(target_dir, exist_ok=True)

    prefix = f".tmp-{os.path.basename(target_abs)}-"
    tf = tempfile.NamedTemporaryFile(
        "w",
        dir=target_dir,
        prefix=prefix,
        suffix=".tmp",
        delete=False,
        encoding=encoding
    )
    tmp_path = tf.name
    try:
        try:
            tf.write(content)
            tf.flush()
            os.fsync(tf.fileno())
        finally:
            tf.close()
        for attempt in range(5):
            try:
                os.replace(tmp_path, target_abs)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

def compute_cable_route(x_start, y_start, p_lane, x_end, y_end, c_lane, x_spacing=85):
    """Compute SVG path and optional label anchor coordinates for an edge cable.
    
    Guarantees:
    1. Zero horizontal S-kinks: dx is clamped so CP1_x <= CP2_x on all spans (dx <= span * 0.45).
    2. Zero card slicing: when |p_lane - c_lane| >= 2 and span > x_spacing + 10,
       vertical transition is routed entirely within inter-column channels:
       - Branch-out (|c_lane| > |p_lane|): vertical transition in channel after parent, then horizontal.
       - Merge (|c_lane| <= |p_lane|): horizontal, then vertical transition in channel before child.
    """
    if y_start == y_end:
        return f"M {x_start} {y_start} L {x_end} {y_end}", None, None

    span = abs(x_end - x_start)
    lane_diff = abs(p_lane - c_lane)

    # F4: Channel-aware routing for multi-lane spans crossing intermediate columns
    if lane_diff >= 2 and span > x_spacing + 10:
        ch_w = min(float(x_spacing), span * 0.45)
        dx = ch_w * 0.45
        if abs(c_lane) > abs(p_lane):
            # Branching out: transition vertically in channel after parent, then horizontal to child
            x_trans = x_start + ch_w
            svg_path = (
                f"M {x_start} {y_start} "
                f"C {x_start + dx:.1f} {y_start}, {x_trans - dx:.1f} {y_end}, {x_trans:.1f} {y_end} "
                f"L {x_end} {y_end}"
            )
            fixed_x = (x_trans + x_end) / 2
            fixed_y = y_end
        else:
            # Merging towards trunk: horizontal from parent, then transition vertically in channel before child
            x_trans = x_end - ch_w
            svg_path = (
                f"M {x_start} {y_start} "
                f"L {x_trans:.1f} {y_start} "
                f"C {x_trans + dx:.1f} {y_start}, {x_end - dx:.1f} {y_end}, {x_end} {y_end}"
            )
            fixed_x = (x_start + x_trans) / 2
            fixed_y = y_start
        return svg_path, fixed_x, fixed_y

    # F3: Standard single cubic Bezier curve with clamped dx (CP1_x <= CP2_x)
    dx = min(160.0, max(15.0, span * 0.35))
    if span > 0 and dx > span * 0.45:
        dx = span * 0.45
    svg_path = f"M {x_start} {y_start} C {x_start + dx:.1f} {y_start}, {x_end - dx:.1f} {y_end}, {x_end} {y_end}"
    return svg_path, None, None

def generate(repo_path=None, max_count=None, output_path=None):
    global REPO_ROOT
    if repo_path:
        REPO_ROOT = find_repo_root(repo_path)

    # 1. Working tree status
    status_raw = run_git(["status", "--porcelain"])
    dirty_lines = [l.strip() for l in status_raw.splitlines() if l.strip()]

    # 2. Branches
    ref_raw = run_git(["for-each-ref", "--format=%(refname:short)|||%(objectname)|||%(HEAD)", "refs/heads/"])
    branches = {}
    head_branch = "main"
    for line in ref_raw.strip().splitlines():
        if not line:
            continue
        parts = line.split("|||")
        if len(parts) >= 3:
            b_name = parts[0].strip()
            b_hash = parts[1].strip()
            is_head = parts[2].strip() == "*"
            branches[b_name] = {"hash": b_hash, "is_head": is_head}
            if is_head:
                head_branch = b_name

    # Check for detached HEAD or empty branch
    head_rev_raw = run_git(["rev-parse", "--verify", "HEAD"], check_err=False).strip()
    head_rev = head_rev_raw.splitlines()[0].strip() if head_rev_raw else ""
    sym_ref = run_git(["symbolic-ref", "-q", "--short", "HEAD", "--"], check_err=False).strip()
    if not sym_ref:
        head_branch = "DETACHED"
        if head_rev:
            branches["DETACHED"] = {"hash": head_rev, "is_head": True}
    elif not head_branch or head_branch == "DETACHED":
        head_branch = sym_ref

    # 3. Tags
    tag_raw = run_git(["for-each-ref", "--format=%(refname:short)|||*%(objectname)", "refs/tags/"])
    tags = {}
    for line in tag_raw.strip().splitlines():
        if not line:
            continue
        parts = line.split("|||")
        if len(parts) >= 2:
            tags.setdefault(parts[1].strip().lstrip("*"), []).append(parts[0].strip())

    # 4. Commits (Include HEAD along with --branches so detached HEAD commits and active WIP are never dropped)
    log_args = ["log", "--branches"]
    if head_rev:
        log_args.append("HEAD")
    log_args.extend([
        "--topo-order",
        "--format=%H|||%h|||%P|||%an|||%ae|||%aI|||%s|||%D###ENDRECORD###"
    ])
    if max_count is not None and max_count > 0:
        log_args.extend(["-n", str(max_count)])
    log_args.append("--")
    log_raw = run_git(log_args)

    commits = {}
    for rec in log_raw.split("###ENDRECORD###"):
        rec = rec.strip()
        if not rec:
            continue
        fields = rec.split("|||")
        if len(fields) < 7:
            continue
        c_hash = fields[0].strip()
        short_hash = fields[1].strip()
        parents = [p.strip() for p in fields[2].split() if p.strip()]
        author_name = fields[3].strip()
        author_email = fields[4].strip()
        date_iso = fields[5].strip()
        subject = fields[6].strip()

        c_branches = [b for b, data in branches.items() if data["hash"] == c_hash]
        c_tags = tags.get(c_hash, [])
        is_head = (c_hash == branches.get(head_branch, {}).get("hash"))

        commits[c_hash] = {
            "hash": c_hash,
            "short_hash": short_hash,
            "parents": parents,
            "author": f"{author_name} <{author_email}>",
            "author_name": author_name,
            "date": date_iso,
            "subject": subject,
            "branches": c_branches,
            "tags": c_tags,
            "is_head": is_head,
            "is_merge": len(parents) >= 2
        }

    # 5. Primary Trunk Line (Lane 0) Detection
    primary_branch = "main"
    for cand in ["main", "master", head_branch]:
        if cand and cand != "DETACHED" and cand in branches:
            primary_branch = cand
            break
    if primary_branch not in branches and branches:
        primary_branch = list(branches.keys())[0]

    primary_ref = f"refs/heads/{primary_branch}" if (primary_branch in branches and not primary_branch.startswith("refs/")) else primary_branch
    primary_shas_raw = run_git(["rev-list", "--first-parent", primary_ref, "--"])
    primary_shas = [s.strip() for s in primary_shas_raw.splitlines() if s.strip() and s.strip() in commits]
    primary_highway_ordered = list(reversed(primary_shas))
    primary_highway_shas = set(primary_shas)

    commit_lane = {}
    commit_lane_name = {}
    commit_lane_color = {}

    # Assign Lane 0 for Primary Trunk
    for c in primary_highway_shas:
        commit_lane[c] = 0
        commit_lane_name[c] = primary_branch
        commit_lane_color[c] = "#06b6d4"

    # 6. Topological Ordering (Parents ALWAYS appear before Children on X-axis)
    topo_args = ["log", "--branches"]
    if head_rev:
        topo_args.append("HEAD")
    topo_args.extend(["--topo-order", "--reverse", "--format=%H"])
    if max_count is not None and max_count > 0:
        topo_args.extend(["-n", str(max_count)])
    topo_args.append("--")
    topo_raw = run_git(topo_args)
    topo_order = [s.strip() for s in topo_raw.splitlines() if s.strip() and s.strip() in commits]
    for c in commits:
        if c not in topo_order:
            topo_order.append(c)
    sorted_commits = topo_order
    topo_index = {c: i for i, c in enumerate(sorted_commits)}

    # 7. Collision-Free Dynamic Lane Allocation
    # Multi-branch mapping: group all branch names per commit hash to prevent dict key overwrites
    head_refs_all = {}
    for b_name, data in branches.items():
        head_refs_all.setdefault(data["hash"], []).append(b_name)

    # Deterministic lookup resolution: head_branch > primary_branch > first branch
    head_refs = {}
    for b_hash, names in head_refs_all.items():
        if head_branch in names:
            head_refs[b_hash] = head_branch
        elif primary_branch in names:
            head_refs[b_hash] = primary_branch
        else:
            head_refs[b_hash] = names[0]

    def get_branch_commits_and_fork(tip_sha):
        branch_shas = []
        fork_sha = None
        queue = deque([tip_sha])
        visited = set()
        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)
            if curr in primary_highway_shas:
                if fork_sha is None or topo_index.get(curr, 0) > topo_index.get(fork_sha, 0):
                    fork_sha = curr
                continue
            branch_shas.append(curr)
            for p in commits.get(curr, {}).get("parents", []):
                queue.append(p)
        return branch_shas, fork_sha

    dynamic_branches = []
    assigned_shas = set(commit_lane.keys())

    # Detect merged branches from Primary Trunk merge commits
    for m in primary_highway_ordered:
        parents = commits.get(m, {}).get("parents", [])
        if len(parents) >= 2:
            for p_side in parents[1:]:
                b_shas, fork_sha = get_branch_commits_and_fork(p_side)
                new_b_shas = [c for c in b_shas if c not in assigned_shas and c in topo_index]
                if new_b_shas:
                    assigned_shas.update(new_b_shas)
                    b_name = head_refs.get(p_side, "")
                    if not b_name:
                        for c in new_b_shas:
                            if c in head_refs:
                                b_name = head_refs[c]
                                break
                    if not b_name:
                        subj = commits.get(m, {}).get("subject", "")
                        b_name = subj if subj else f"merged-{p_side[:7]}"
                    dynamic_branches.append({
                        "name": b_name,
                        "type": "merged",
                        "fork": fork_sha,
                        "merge": m,
                        "shas": new_b_shas,
                        "tip": p_side
                    })

    # Detect open / ongoing branches from refs/heads/
    for b_hash, names in head_refs_all.items():
        active_names = [n for n in names if n != primary_branch and n != "DETACHED"]
        if not active_names:
            continue
        if b_hash in assigned_shas:
            continue
        b_name = active_names[0]
        b_shas, fork_sha = get_branch_commits_and_fork(b_hash)
        new_b_shas = [c for c in b_shas if c not in assigned_shas and c in topo_index]
        if new_b_shas:
            assigned_shas.update(new_b_shas)
            dynamic_branches.append({
                "name": b_name,
                "type": "open",
                "fork": fork_sha,
                "merge": None,
                "shas": new_b_shas,
                "tip": b_hash
            })

    lane_intervals = {}

    def allocate_lane(branch_type, start_idx, end_idx, b_name):
        if branch_type == "open":
            cand = 1
            while True:
                collision = False
                for (s, e, _) in lane_intervals.get(cand, []):
                    if not (end_idx < s - 1 or start_idx > e + 1):
                        collision = True
                        break
                if not collision:
                    lane_intervals.setdefault(cand, []).append((start_idx, end_idx, b_name))
                    return cand
                cand += 1
        else: # merged
            cand = -1
            while True:
                collision = False
                for (s, e, _) in lane_intervals.get(cand, []):
                    if not (end_idx < s - 1 or start_idx > e + 1):
                        collision = True
                        break
                if not collision:
                    lane_intervals.setdefault(cand, []).append((start_idx, end_idx, b_name))
                    return cand
                cand -= 1

    branch_palette = [
        "#10b981", "#8b5cf6", "#f59e0b", "#ec4899",
        "#14b8a6", "#3b82f6", "#e11d48", "#84cc16",
        "#06b6d4", "#f97316", "#a855f7", "#6366f1"
    ]

    for i, b in enumerate(dynamic_branches):
        all_indices = [topo_index[c] for c in b["shas"]]
        if b["fork"] and b["fork"] in topo_index:
            all_indices.append(topo_index[b["fork"]])
        if b["merge"] and b["merge"] in topo_index:
            all_indices.append(topo_index[b["merge"]])
        s_idx = min(all_indices)
        e_idx = max(all_indices)
        lane = allocate_lane(b["type"], s_idx, e_idx, b["name"])
        color = branch_palette[i % len(branch_palette)]
        cur_sub_name = b["name"]
        for idx_c, c in enumerate(b["shas"]):
            if idx_c > 0 and c in head_refs and head_refs[c] != primary_branch:
                cur_sub_name = head_refs[c]
            commit_lane[c] = lane
            commit_lane_name[c] = cur_sub_name
            commit_lane_color[c] = color

    # Safety fallback for any orphan commit
    for c in commits:
        if c not in commit_lane:
            commit_lane[c] = 1
            commit_lane_name[c] = "feature/active"
            commit_lane_color[c] = "#64748b"

    NODE_WIDTH = 300
    NODE_HEIGHT = 88
    X_SPACING = 85
    Y_SPACING = 120
    WIP_SPACING = max(X_SPACING + 95, 180)

    # Pre-calculate WIP node placement and lane allocation so it never collides with other branches
    head_commit_sha = branches.get(head_branch, {}).get("hash", head_rev) if dirty_lines else None
    has_active_wip = bool(dirty_lines and head_commit_sha and head_commit_sha in topo_index)
    wip_h_idx = topo_index[head_commit_sha] if has_active_wip else -1
    wip_lane = 0
    wip_lane_name = ""
    wip_lane_color = "#06b6d4"

    if has_active_wip:
        h_lane = commit_lane.get(head_commit_sha, 0)
        has_later_on_h_lane = any(
            commit_lane.get(c) == h_lane and topo_index[c] > wip_h_idx
            for c in sorted_commits
        )
        if head_branch != primary_branch and head_branch != "DETACHED":
            if h_lane != 0 and not has_later_on_h_lane:
                wip_lane = h_lane
                wip_lane_name = commit_lane_name.get(head_commit_sha, head_branch)
                wip_lane_color = commit_lane_color.get(head_commit_sha, "#10b981")
            else:
                wip_lane = allocate_lane("open", wip_h_idx, wip_h_idx + 1, head_branch)
                wip_lane_name = head_branch
                wip_lane_color = branch_palette[len(dynamic_branches) % len(branch_palette)]
        else:
            if h_lane == 0 and not has_later_on_h_lane:
                wip_lane = 0
                wip_lane_name = f"{primary_branch} (WIP)"
                wip_lane_color = "#06b6d4"
            elif not has_later_on_h_lane:
                wip_lane = h_lane
                wip_lane_name = f"{commit_lane_name.get(head_commit_sha, head_branch)} (WIP)"
                wip_lane_color = commit_lane_color.get(head_commit_sha, "#10b981")
            else:
                wip_lane = allocate_lane("open", wip_h_idx, wip_h_idx + 1, head_branch)
                wip_lane_name = f"{head_branch} (WIP)"
                wip_lane_color = "#f59e0b"

    # Dynamic BASE_Y to guarantee upper lanes have clean top margin
    all_assigned_lanes = list(commit_lane.values()) + ([wip_lane] if has_active_wip else [])
    min_lane = min(all_assigned_lanes) if all_assigned_lanes else 0
    if min_lane < 0:
        BASE_Y = 120 + abs(min_lane) * (NODE_HEIGHT + Y_SPACING)
    else:
        BASE_Y = 320 + 2 * (NODE_HEIGHT + Y_SPACING)

    nodes = []
    coords = {}

    for idx, c in enumerate(sorted_commits):
        c_data = commits[c]
        lane = commit_lane[c]
        wip_x_shift = (NODE_WIDTH + WIP_SPACING) if (has_active_wip and idx > wip_h_idx) else 0
        x = 80 + idx * (NODE_WIDTH + X_SPACING) + wip_x_shift
        y = BASE_Y + lane * (NODE_HEIGHT + Y_SPACING)
        coords[c] = (x, y)

        status = "normal"
        if c_data["is_head"]:
            status = "head"
        elif c_data["is_merge"]:
            status = "merge"

        nodes.append({
            "id": c,
            "hash": c,
            "short_id": c_data["short_hash"],
            "short_hash": c_data["short_hash"],
            "title": c_data["subject"],
            "subject": c_data["subject"],
            "author": c_data["author_name"],
            "author_full": c_data["author"],
            "date": c_data["date"],
            "branches": c_data["branches"],
            "tags": c_data["tags"],
            "parents": c_data["parents"],
            "lane": lane,
            "lane_name": commit_lane_name[c],
            "lane_color": commit_lane_color[c],
            "x": x,
            "y": y,
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
            "status": status,
            "is_head": c_data["is_head"],
            "is_merge": c_data["is_merge"],
            "is_wip": False
        })

    # 8. Dynamic WIP Node for Current Active Branch Working Directory
    active_wip_id = None
    if has_active_wip and head_commit_sha in coords:
        active_wip_id = "active-wip"
        h_x, h_y = coords[head_commit_sha]
        active_wip_x = h_x + NODE_WIDTH + WIP_SPACING
        active_wip_y = BASE_Y + wip_lane * (NODE_HEIGHT + Y_SPACING)
        coords[active_wip_id] = (active_wip_x, active_wip_y)

        wip_title = f"Working Tree ({len(dirty_lines)} uncommitted changes)"
        nodes.append({
            "id": active_wip_id,
            "hash": active_wip_id,
            "short_id": "WIP",
            "short_hash": "WIP",
            "title": wip_title,
            "subject": wip_title,
            "author": "Local Working Directory",
            "author_full": "Local Working Tree <uncommitted>",
            "date": datetime.now().isoformat(),
            "branches": [head_branch] if head_branch else [],
            "tags": [],
            "parents": [head_commit_sha],
            "lane": wip_lane,
            "lane_name": f"{wip_lane_name} (WIP)" if not wip_lane_name.endswith("(WIP)") else wip_lane_name,
            "lane_color": wip_lane_color,
            "x": active_wip_x,
            "y": active_wip_y,
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
            "status": "wip",
            "is_head": False,
            "is_merge": False,
            "is_wip": True
        })

    # 9. Edges with Bézier Connections
    edges = []
    edge_set = set()

    for c in sorted_commits:
        c_x, c_y = coords[c]
        c_lane = commit_lane[c]
        c_data = commits[c]

        for idx, p in enumerate(c_data["parents"]):
            if p not in coords:
                continue
            p_x, p_y = coords[p]
            p_lane = commit_lane[p]

            x_start = p_x + NODE_WIDTH
            y_start = p_y + (NODE_HEIGHT / 2)
            x_end = c_x
            y_end = c_y + (NODE_HEIGHT / 2)

            svg_path, fixed_x, fixed_y = compute_cable_route(
                x_start, y_start, p_lane,
                x_end, y_end, c_lane,
                x_spacing=X_SPACING
            )

            # Resolve source branch name for attribution
            p_branches = commits.get(p, {}).get("branches", [])
            non_primary_branches = [b for b in p_branches if b != primary_branch and b != "DETACHED"]
            if non_primary_branches:
                p_display_name = non_primary_branches[0].replace("feature/", "")
                edge_branch = non_primary_branches[0]
            else:
                p_display_name = commit_lane_name.get(p, "branch").replace("feature/", "")
                edge_branch = commit_lane_name.get(p, "branch")
            if not p_display_name or p_display_name == "branch":
                p_display_name = p[:7]

            is_merge_edge = (p_lane != 0 and c_lane == 0) or (c_data["is_merge"] and idx >= 1)

            if is_merge_edge:
                edge_type = "merge"
                color = "#10b981"
                label = f"MERGE: {p_display_name}"
            elif p_lane == 0 and c_lane != 0:
                edge_type = "branch_out"
                color = commit_lane_color[c]
                c_name = commit_lane_name.get(c, "branch").replace("feature/", "")
                label = f"BRANCH: {c_name}"
                edge_branch = commit_lane_name.get(c, "branch")
            elif p_lane != c_lane:
                edge_type = "branch_out"
                color = commit_lane_color[c]
                c_name = commit_lane_name.get(c, "branch").replace("feature/", "")
                label = f"BRANCH: {c_name}"
                edge_branch = commit_lane_name.get(c, "branch")
            elif c_lane == 0:
                edge_type = "normal"
                color = "#06b6d4"
                label = primary_branch.upper()
                edge_branch = primary_branch
            else:
                edge_type = "normal"
                color = commit_lane_color[c]
                if commit_lane_name.get(p) != commit_lane_name.get(c):
                    c_name = commit_lane_name.get(c, "branch").replace("feature/", "")
                    label = f"BRANCH: {c_name}"
                else:
                    label = ""
                edge_branch = commit_lane_name.get(c, "branch")

            edge_key = (p, c)
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edge_dict = {
                    "id": f"e-{p[:7]}-{c[:7]}",
                    "from": p,
                    "to": c,
                    "type": edge_type,
                    "branch": edge_branch,
                    "is_to_master": (c_lane == 0),
                    "color": color,
                    "label": label,
                    "svg_path": svg_path
                }
                if fixed_x is not None and fixed_y is not None:
                    edge_dict["fixed_x"] = fixed_x
                    edge_dict["fixed_y"] = fixed_y
                edges.append(edge_dict)

    # Primary Trunk continuation wire along Lane 0
    for i in range(len(primary_highway_ordered) - 1):
        m_from = primary_highway_ordered[i]
        m_to = primary_highway_ordered[i+1]
        edge_key = (m_from, m_to)
        if edge_key not in edge_set and m_from in coords and m_to in coords:
            edge_set.add(edge_key)
            p_x, p_y = coords[m_from]
            c_x, c_y = coords[m_to]
            x_start = p_x + NODE_WIDTH
            y_start = p_y + (NODE_HEIGHT / 2)
            x_end = c_x
            y_end = c_y + (NODE_HEIGHT / 2)
            svg_path, _, _ = compute_cable_route(
                x_start, y_start, 0,
                x_end, y_end, 0,
                x_spacing=X_SPACING
            )
            edges.append({
                "id": f"trunk-{m_from[:7]}-{m_to[:7]}",
                "from": m_from,
                "to": m_to,
                "type": "master-trunk",
                "branch": primary_branch,
                "is_to_master": True,
                "color": "#06b6d4",
                "label": f"{primary_branch.upper()} TRUNK",
                "svg_path": svg_path
            })

    # Connect Head Commit to Active WIP Node
    if active_wip_id and active_wip_id in coords:
        head_commit_sha = branches.get(head_branch, {}).get("hash", head_rev)
        if head_commit_sha in coords:
            h_x, h_y = coords[head_commit_sha]
            w_x, w_y = coords[active_wip_id]
            x_start = h_x + NODE_WIDTH
            y_start = h_y + (NODE_HEIGHT / 2)
            x_end = w_x
            y_end = w_y + (NODE_HEIGHT / 2)
            svg_path, _, _ = compute_cable_route(
                x_start, y_start, commit_lane.get(head_commit_sha, 0),
                x_end, y_end, wip_lane,
                x_spacing=WIP_SPACING
            )
            edges.append({
                "id": f"e-{active_wip_id}",
                "from": head_commit_sha,
                "to": active_wip_id,
                "type": "wip",
                "branch": head_branch,
                "is_to_master": (wip_lane == 0),
                "color": wip_lane_color,
                "label": "UNCOMMITTED WORK",
                "svg_path": svg_path
            })

    # 10. Extract diffs (reuse existing cached commit diffs for fast execution)
    existing_diffs = {}
    target_output = os.path.abspath(output_path) if output_path else OUTPUT_JS
    if os.path.exists(target_output):
        try:
            with open(target_output, "r", encoding="utf-8") as ef:
                eraw = ef.read()
            if "window.GIT_DAG_DATA = " in eraw:
                ebundle = json.loads(eraw.split("window.GIT_DAG_DATA = ", 1)[1].rstrip(";\n "))
                existing_diffs = ebundle.get("diffs", {})
        except Exception:
            existing_diffs = {}

    diffs = {}
    for c in sorted_commits:
        if c in existing_diffs and c != "active-wip":
            diffs[c] = existing_diffs[c]
            continue
        stat_raw = run_git(["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", c, "--"])
        files = []
        for line in stat_raw.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t")
            files.append({"status": parts[0].strip(), "path": parts[1].strip() if len(parts) > 1 else ""})

        full_diff = run_git(["show", "--stat", "--patch", "--format=fuller", c, "--"])
        diffs[c] = {
            "files": files,
            "full_output": full_diff[:100000]
        }

    # WIP Diff
    if active_wip_id and active_wip_id in coords:
        wip_files = []
        for line in dirty_lines:
            status_code = line[:2].strip()
            filepath = line[2:].strip()
            wip_files.append({"status": status_code, "path": filepath})

        raw_diff = run_git(["diff", "HEAD", "--"])
        untracked = [l[2:].strip() for l in dirty_lines if l.startswith("??")]
        untracked_block = ""
        if untracked:
            untracked_block = "\n\n=== Untracked New Files ===\n" + "\n".join(f"+ {u}" for u in untracked)

        diffs[active_wip_id] = {
            "files": wip_files,
            "full_output": (raw_diff + untracked_block)[:100000]
        }

    all_lanes = all_assigned_lanes
    total_lanes = (max(all_lanes) - min(all_lanes) + 1) if all_lanes else 8

    primary_ref = f"refs/heads/{primary_branch}" if (primary_branch in branches and not primary_branch.startswith("refs/")) else primary_branch
    merged_to_primary_raw = run_git(["branch", "--merged", primary_ref, "--"])
    merged_to_primary = set([b.strip().lstrip("*+").strip() for b in merged_to_primary_raw.splitlines() if b.strip()])

    bundle = {
        "schema_version": 2,
        "repo": os.path.basename(REPO_ROOT),
        "primary_branch": primary_branch,
        "head_branch": head_branch,
        "head_commit": branches.get(head_branch, {}).get("hash", head_rev),
        "master_y": BASE_Y + (NODE_HEIGHT / 2),
        "generated_at": datetime.now().isoformat(),
        "status": {
            "is_dirty": len(dirty_lines) > 0,
            "dirty_count": len(dirty_lines),
            "changes": dirty_lines[:20]
        },
        "branches": [
            {
                "name": b,
                "hash": data["hash"],
                "short_hash": data["hash"][:7],
                "is_head": data["is_head"],
                "is_merged_to_master": (b in merged_to_primary),
                "lane": wip_lane if (b == head_branch and has_active_wip) else commit_lane.get(data["hash"], 0)
            }
            for b, data in branches.items()
        ],
        "stats": {
            "total_commits": len(nodes),
            "total_branches": len(branches),
            "total_lanes": total_lanes
        },
        "nodes": nodes,
        "edges": edges,
        "diffs": diffs
    }

    js_content = f"/* Auto-generated Git DAG Data */\nwindow.GIT_DAG_DATA = {json.dumps(bundle, ensure_ascii=False, indent=2)};\n"
    target_output = os.path.abspath(output_path) if output_path else OUTPUT_JS
    write_atomic_file(target_output, js_content, encoding="utf-8")

    print(f"Successfully generated {os.path.basename(target_output)} for repository '{os.path.basename(REPO_ROOT)}' ({len(nodes)} commits, {len(edges)} edges, {len(branches)} branches) at {datetime.now().strftime('%H:%M:%S')}")

def install_git_hooks(repo_path=None):
    """Install synchronous, Job-Object-safe Git hooks (post-commit, post-checkout, post-merge, post-rewrite)."""
    target_repo = find_repo_root(repo_path)
    common_dir_raw = run_git(["rev-parse", "--git-common-dir"], cwd=target_repo, check_err=False).strip()
    if not common_dir_raw:
        common_dir = os.path.join(target_repo, ".git")
    elif os.path.isabs(common_dir_raw):
        common_dir = common_dir_raw
    else:
        common_dir = os.path.abspath(os.path.join(target_repo, common_dir_raw))

    hooks_dir = os.path.join(common_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    hook_body = (
        "#!/bin/sh\n"
        "# Auto-update n8n Git UI data (runs synchronously so automated terminals do not kill child processes before git_data.js is written)\n"
        'COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null || echo .git)"\n'
        'python "$COMMON_DIR/n8n-git-ui/generate_dag.py" > /dev/null 2>&1 || true\n'
    )

    hook_names = ["post-commit", "post-checkout", "post-merge", "post-rewrite"]
    for h_name in hook_names:
        h_path = os.path.join(hooks_dir, h_name)
        write_atomic_file(h_path, hook_body, encoding="utf-8")
        try:
            st = os.stat(h_path)
            os.chmod(h_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass

    print(f"Installed synchronous Git hooks ({', '.join(hook_names)}) in {hooks_dir}")
    return hooks_dir

def main():
    parser = argparse.ArgumentParser(description="Standalone Git DAG Generator for n8n-style UI")
    parser.add_argument("repo_path", nargs="?", default=None, help="Path to Git repository (optional)")
    parser.add_argument("-n", "--max-count", type=int, default=None, help="Limit commit count (default: all commits)")
    parser.add_argument("-o", "--output", default=None, help="Output JS file path (default: git_data.js)")
    parser.add_argument("--install-hooks", action="store_true", help="Install synchronous Git hooks (post-commit, post-checkout, post-merge, post-rewrite)")
    args = parser.parse_args()

    if args.install_hooks:
        install_git_hooks(repo_path=args.repo_path)

    generate(repo_path=args.repo_path, max_count=args.max_count, output_path=args.output)

if __name__ == "__main__":
    main()
