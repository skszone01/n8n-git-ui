#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Git DAG Generator for n8n-style UI (Zero-Server Architecture)
Generates an interactive visual topology from any Git repository:
- Central Primary Backbone (Lane 0) in the middle (main / master)
- Upper lanes (Lane -1, -2) for merged feature branches
- Lower lanes (Lane +1, +2, +3...) for active / ongoing feature branches
- Explicit Branch and Merge Bézier cables
- Real-time WIP Working Directory node for uncommitted changes
"""

import os
import sys
import json
import subprocess
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Determine REPO_ROOT: CLI argument > parent repo > current dir
if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
    REPO_ROOT = os.path.abspath(sys.argv[1])
else:
    candidate_parent2 = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
    candidate_parent1 = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
    if os.path.exists(os.path.join(candidate_parent2, ".git")):
        REPO_ROOT = candidate_parent2
    elif os.path.exists(os.path.join(candidate_parent1, ".git")):
        REPO_ROOT = candidate_parent1
    elif os.path.exists(os.path.join(CURRENT_DIR, ".git")):
        REPO_ROOT = CURRENT_DIR
    else:
        REPO_ROOT = os.getcwd()

OUTPUT_JS = os.path.join(CURRENT_DIR, "git_data.js")

def run_git(args):
    """Run a git command in REPO_ROOT and return stdout."""
    try:
        res = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", REPO_ROOT] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.stdout
    except Exception:
        return ""

def generate():
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

    # Check for detached HEAD
    head_rev = run_git(["rev-parse", "HEAD"]).strip()
    sym_ref = run_git(["symbolic-ref", "-q", "--short", "HEAD"]).strip()
    if not sym_ref and head_rev:
        head_branch = "DETACHED"
        branches["DETACHED"] = {"hash": head_rev, "is_head": True}

    # 3. Detect Primary Trunk Branch (main or master)
    primary_branch = "main"
    if run_git(["rev-parse", "--verify", "main"]).strip():
        primary_branch = "main"
    elif run_git(["rev-parse", "--verify", "master"]).strip():
        primary_branch = "master"
    elif head_branch and head_branch != "DETACHED":
        primary_branch = head_branch
    elif branches:
        primary_branch = list(branches.keys())[0]

    merged_raw = run_git(["branch", "--merged", primary_branch])
    merged_to_primary = set([b.strip().replace("*", "").strip() for b in merged_raw.splitlines() if b.strip()])

    # 4. Tags
    tag_raw = run_git(["tag", "--list", "--format=%(refname:short)|||%(objectname)"])
    tags = {}
    for line in tag_raw.strip().splitlines():
        if not line:
            continue
        parts = line.split("|||")
        if len(parts) >= 2:
            tags.setdefault(parts[1].strip(), []).append(parts[0].strip())

    # 5. Commits
    log_raw = run_git([
        "log", "--branches", "--topo-order",
        "--format=%H|||%h|||%P|||%an|||%ae|||%aI|||%s|||%D###ENDRECORD###"
    ])

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

    # 6. Lane Allocation with Central Primary Trunk Line (Lane 0)
    primary_shas_raw = run_git(["rev-list", "--first-parent", primary_branch])
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

    # Dynamic lane assignment for branches
    available_lanes = [1, 2, 3, -1, 4, -2, 5, 6]
    branch_palette = ["#f97316", "#a855f7", "#10b981", "#38bdf8", "#ec4899", "#f59e0b", "#3b82f6", "#14b8a6"]
    assigned_count = 0

    for b_name, b_info in branches.items():
        if b_name == primary_branch or b_name == "DETACHED":
            continue
        b_hash = b_info["hash"]
        b_shas_raw = run_git(["rev-list", b_hash, "--not"] + list(primary_highway_shas))
        b_shas = [s.strip() for s in b_shas_raw.splitlines() if s.strip() and s.strip() in commits]
        unassigned = [c for c in b_shas if c not in commit_lane]

        if unassigned:
            lane = available_lanes[assigned_count % len(available_lanes)]
            color = branch_palette[assigned_count % len(branch_palette)]
            assigned_count += 1
            for c in unassigned:
                commit_lane[c] = lane
                commit_lane_name[c] = b_name
                commit_lane_color[c] = color

    # Fallback for any unassigned commit: never pollute Lane 0
    for c in commits:
        if c not in commit_lane:
            commit_lane[c] = 1
            commit_lane_name[c] = "feature/active"
            commit_lane_color[c] = "#64748b"

    # 7. Topological Ordering (Parents appear before Children)
    topo_raw = run_git(["log", "--branches", "--topo-order", "--reverse", "--format=%H"])
    topo_order = [s.strip() for s in topo_raw.splitlines() if s.strip() and s.strip() in commits]
    for c in commits:
        if c not in topo_order:
            topo_order.append(c)
    sorted_commits = topo_order

    NODE_WIDTH = 300
    NODE_HEIGHT = 88
    X_SPACING = 85
    Y_SPACING = 120
    BASE_Y = 320 + 2 * Y_SPACING

    nodes = []
    coords = {}
    for gen, c in enumerate(sorted_commits):
        lane = commit_lane[c]
        x = 120 + gen * (NODE_WIDTH + X_SPACING)
        y = BASE_Y + lane * (NODE_HEIGHT + Y_SPACING)
        coords[c] = (x, y)

        c_data = commits[c]
        status = "normal"
        if c_data["is_head"]:
            status = "head"
        elif c in primary_highway_shas:
            status = "master"
        elif c_data["branches"]:
            status = "branch_tip"

        nodes.append({
            "id": c,
            "short_id": c_data["short_hash"],
            "title": c_data["subject"],
            "author": c_data["author_name"],
            "author_full": c_data["author"],
            "date": c_data["date"],
            "branches": c_data["branches"],
            "tags": c_data["tags"],
            "is_head": c_data["is_head"],
            "is_merge": c_data["is_merge"],
            "parents": c_data["parents"],
            "lane": lane,
            "lane_name": commit_lane_name[c],
            "lane_color": commit_lane_color[c],
            "x": x,
            "y": y,
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
            "status": status
        })

    # 8. Dynamic WIP Node for Current Active Branch Working Directory
    active_wip_id = None
    if dirty_lines:
        head_commit_sha = branches.get(head_branch, {}).get("hash", head_rev)
        if head_commit_sha and head_commit_sha in coords:
            active_wip_id = "active-wip"
            h_x, h_y = coords[head_commit_sha]
            active_wip_x = h_x + NODE_WIDTH + X_SPACING
            wip_lane = commit_lane.get(head_commit_sha, 0)
            wip_lane_name = commit_lane_name.get(head_commit_sha, head_branch)
            wip_lane_color = commit_lane_color.get(head_commit_sha, "#10b981")

            active_wip_y = BASE_Y + wip_lane * (NODE_HEIGHT + Y_SPACING)
            coords[active_wip_id] = (active_wip_x, active_wip_y)

            nodes.append({
                "id": active_wip_id,
                "short_id": "WIP",
                "title": f"WIP: Uncommitted Changes ({len(dirty_lines)} files)",
                "author": "Working Tree",
                "author_full": "Local Working Tree <uncommitted>",
                "date": datetime.now().isoformat(),
                "branches": ["WIP", head_branch],
                "tags": [],
                "is_head": True,
                "is_wip": True,
                "is_merge": False,
                "parents": [head_commit_sha],
                "lane": wip_lane,
                "lane_name": f"{wip_lane_name} (WIP)",
                "lane_color": wip_lane_color,
                "x": active_wip_x,
                "y": active_wip_y,
                "width": NODE_WIDTH,
                "height": NODE_HEIGHT,
                "status": "wip"
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

            if p_y == c_y:
                svg_path = f"M {x_start} {y_start} L {x_end} {y_end}"
            else:
                dx = min(160, max(45, abs(x_end - x_start) * 0.35))
                svg_path = f"M {x_start} {y_start} C {x_start + dx} {y_start}, {x_end - dx} {y_end}, {x_end} {y_end}"

            if p_lane != 0 and c_lane == 0:
                edge_type = "merge"
                color = "#10b981"
                label = f"MERGE TO {primary_branch.upper()}"
            elif c_data["is_merge"] and idx >= 1:
                edge_type = "merge"
                color = "#10b981"
                p_name = commit_lane_name.get(p, "branch")
                label = f"MERGE: {p_name}"
            elif p_lane == 0 and c_lane != 0:
                edge_type = "branch_out"
                color = commit_lane_color[c]
                c_name = commit_lane_name.get(c, "branch")
                label = f"BRANCH: {c_name}"
            elif p_lane != c_lane:
                edge_type = "branch_out"
                color = commit_lane_color[c]
                c_name = commit_lane_name.get(c, "branch")
                label = f"BRANCH: {c_name}"
            elif c_lane == 0:
                edge_type = "normal"
                color = "#06b6d4"
                label = primary_branch.upper()
            else:
                edge_type = "normal"
                color = commit_lane_color[c]
                label = ""

            edge_key = (p, c)
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edges.append({
                    "id": f"e-{p[:7]}-{c[:7]}",
                    "from": p,
                    "to": c,
                    "type": edge_type,
                    "is_to_master": (c_lane == 0),
                    "color": color,
                    "label": label,
                    "svg_path": svg_path
                })

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
            if p_y == c_y:
                svg_path = f"M {x_start} {y_start} L {x_end} {y_end}"
            else:
                dx = min(160, max(45, abs(x_end - x_start) * 0.35))
                svg_path = f"M {x_start} {y_start} C {x_start + dx} {y_start}, {x_end - dx} {y_end}, {x_end} {y_end}"
            edges.append({
                "id": f"trunk-{m_from[:7]}-{m_to[:7]}",
                "from": m_from,
                "to": m_to,
                "type": "master-trunk",
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
            wip_lane = commit_lane.get(head_commit_sha, 0)
            wip_lane_color = commit_lane_color.get(head_commit_sha, "#3b82f6")
            if h_y == w_y:
                svg_path = f"M {h_x + NODE_WIDTH} {h_y + (NODE_HEIGHT / 2)} L {w_x} {w_y + (NODE_HEIGHT / 2)}"
            else:
                dx = min(160, max(45, abs(x_end - x_start) * 0.35)) if 'x_end' in locals() else 50
                svg_path = f"M {h_x + NODE_WIDTH} {h_y + (NODE_HEIGHT / 2)} C {h_x + NODE_WIDTH + dx} {h_y + (NODE_HEIGHT / 2)}, {w_x - dx} {w_y + (NODE_HEIGHT / 2)}, {w_x} {w_y + (NODE_HEIGHT / 2)}"
            edges.append({
                "id": f"e-{active_wip_id}",
                "from": head_commit_sha,
                "to": active_wip_id,
                "type": "wip",
                "is_to_master": (wip_lane == 0),
                "color": wip_lane_color,
                "label": "UNCOMMITTED WORK",
                "svg_path": svg_path
            })

    # 10. Extract diffs
    diffs = {}
    for c in sorted_commits:
        stat_raw = run_git(["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", c])
        files = []
        for line in stat_raw.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t")
            files.append({"status": parts[0].strip(), "path": parts[1].strip() if len(parts) > 1 else ""})

        full_diff = run_git(["show", "--stat", "--patch", "--format=fuller", c])
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

        raw_diff = run_git(["diff", "HEAD"])
        untracked = [l[2:].strip() for l in dirty_lines if l.startswith("??")]
        untracked_block = ""
        if untracked:
            untracked_block = "\n\n=== Untracked New Files ===\n" + "\n".join(f"+ {u}" for u in untracked)

        diffs[active_wip_id] = {
            "files": wip_files,
            "full_output": (raw_diff + untracked_block)[:100000]
        }

    all_lanes = list(commit_lane.values())
    total_lanes = (max(all_lanes) - min(all_lanes) + 1) if all_lanes else 8

    bundle = {
        "repo": os.path.basename(REPO_ROOT),
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
                "lane": commit_lane.get(data["hash"], 0)
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
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"Successfully generated git_data.js ({len(nodes)} commits, {len(edges)} edges) at {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    generate()
