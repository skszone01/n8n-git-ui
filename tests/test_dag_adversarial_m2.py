#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adversarial Stress Test Suite for Milestone M2
DAG Layout, Cable Routing, and Collision-Free Rendering

Tests complex synthetic Git topologies:
a) Multiple branches forked from the same commit (5+, 10+, co-located branches).
b) Detached HEAD with uncommitted changes (tip, mid-history, root, single-commit repo).
c) Octopus merges with 3+ parents.
d) Orphan/root commits (unrelated histories, disjoint roots, orphan WIP).
e) Criss-cross merges and deep histories.
f) Non-ASCII / Thai UTF-8 metadata and emoji resilience.

Verifies:
1) Zero pairwise node bounding box overlaps (dx < 300 and dy < 88).
2) active-wip node presence, is_wip: True, is_head: False when dirty.
3) Detached HEAD commit presence and is_head: True.
4) Bézier curve control point monotonicity (CP1_x <= CP2_x).
5) Zero pill-to-node card collisions and zero pill-to-pill collisions via simulation.
6) Strict Schema v2 validation compliance via tools/check_schema.py.
"""

import os
import sys
import json
import re
import tempfile
import subprocess
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATE_DAG_SCRIPT = os.path.join(PROJECT_ROOT, "generate_dag.py")
CHECK_SCHEMA_SCRIPT = os.path.join(PROJECT_ROOT, "tools", "check_schema.py")


def run_git(args, cwd, author_name="Test Author", author_email="author@example.com"):
    """Run git command in cwd, ensuring git author config."""
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = author_name
    env["GIT_AUTHOR_EMAIL"] = author_email
    env["GIT_COMMITTER_NAME"] = author_name
    env["GIT_COMMITTER_EMAIL"] = author_email
    res = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env
    )
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
    return res.stdout.strip()


def check_pairwise_collisions(nodes, context=""):
    """Verify that all node bounding boxes (width=300, height=88) have 0 pairwise overlaps."""
    n = len(nodes)
    collisions = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = nodes[i], nodes[j]
            dx = abs(a["x"] - b["x"])
            dy = abs(a["y"] - b["y"])
            if dx < 300 and dy < 88:
                collisions.append({
                    "node_a": a.get("id"),
                    "node_b": b.get("id"),
                    "a_pos": (a["x"], a["y"]),
                    "b_pos": (b["x"], b["y"]),
                    "dx": dx,
                    "dy": dy,
                    "context": context
                })
    return collisions


def check_bezier_curves(edges, context=""):
    """Verify that Bézier curves do not have horizontal reversal bulges (CP1_x <= CP2_x)."""
    kinks = []
    bezier_re = re.compile(r"C\s+([\d\.\-]+)\s+([\d\.\-]+),\s+([\d\.\-]+)\s+([\d\.\-]+),\s+([\d\.\-]+)\s+([\d\.\-]+)")
    for edge in edges:
        path = edge.get("svg_path", "")
        for m in bezier_re.finditer(path):
            cp1_x = float(m.group(1))
            cp2_x = float(m.group(3))
            if cp1_x > cp2_x + 1e-4:  # Horizontal inversion / kink
                kinks.append({
                    "edge_id": edge.get("id"),
                    "cp1_x": cp1_x,
                    "cp2_x": cp2_x,
                    "path": path,
                    "context": context
                })
    return kinks


def simulate_pill_placements(data, context=""):
    """Simulate frontend 8-iteration relaxation solver to detect card and pill collisions."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    def get_bezier_pt(t, x1, y1, cx1, cy1, cx2, cy2, x2, y2):
        u = 1 - t
        return (
            u**3 * x1 + 3 * u**2 * t * cx1 + 3 * u * t**2 * cx2 + t**3 * x2,
            u**3 * y1 + 3 * u**2 * t * cy1 + 3 * u * t**2 * cy2 + t**3 * y2
        )

    # 1. Collect horizontal segments
    segments = []
    for e in edges:
        p = e.get("svg_path", "")
        mC = re.match(r"M\s+([-\d.]+)\s+([-\d.]+)\s+C\s+([-\d.]+)\s+([-\d.]+),\s+([-\d.]+)\s+([-\d.]+),\s+([-\d.]+)\s+([-\d.]+)", p)
        mL = re.match(r"M\s+([-\d.]+)\s+([-\d.]+)\s+L\s+([-\d.]+)\s+([-\d.]+)", p)
        if mC:
            x1, y1 = float(mC.group(1)), float(mC.group(2))
            x2, y2 = float(mC.group(7)), float(mC.group(8))
            if abs(y1 - y2) < 4:
                segments.append({"y": (y1 + y2) / 2, "minX": min(x1, x2), "maxX": max(x1, x2)})
            else:
                dx = abs(x2 - x1) * 0.45
                segments.append({"y": y1, "minX": min(x1, x1 + dx * 0.4), "maxX": max(x1, x1 + dx * 0.4)})
                segments.append({"y": y2, "minX": min(x2 - dx * 0.4, x2), "maxX": max(x2 - dx * 0.4, x2)})
        elif mL:
            x1, y1 = float(mL.group(1)), float(mL.group(2))
            x2, y2 = float(mL.group(3)), float(mL.group(4))
            if abs(y1 - y2) < 4:
                segments.append({"y": (y1 + y2) / 2, "minX": min(x1, x2), "maxX": max(x1, x2)})

    def find_colliding_wire(px, py, pw):
        half_w = pw / 2 + 10
        for seg in segments:
            if px + half_w >= seg["minX"] and px - half_w <= seg["maxX"]:
                if abs(py - seg["y"]) < 26:
                    return seg
        return None

    def find_colliding_card(px, py, pw, ph=24):
        half_w = pw / 2 + 10
        half_h = ph / 2 + 6
        for n in nodes:
            nx1, nx2 = n["x"], n["x"] + n.get("width", 300)
            ny1, ny2 = n["y"], n["y"] + n.get("height", 88)
            if px + half_w >= nx1 and px - half_w <= nx2 and py + half_h >= ny1 and py - half_h <= ny2:
                return n
        return None

    placed_pills = []
    card_collisions = []
    pill_collisions = []

    for e in edges:
        lbl = e.get("label")
        if not lbl:
            continue
        pill_w = max(len(lbl) * 7.2 + 20, 52)
        p = e.get("svg_path", "")
        mC = re.match(r"M\s+([-\d.]+)\s+([-\d.]+)\s+C\s+([-\d.]+)\s+([-\d.]+),\s+([-\d.]+)\s+([-\d.]+),\s+([-\d.]+)\s+([-\d.]+)", p)
        mL = re.match(r"M\s+([-\d.]+)\s+([-\d.]+)\s+L\s+([-\d.]+)\s+([-\d.]+)", p)
        points = []
        if "fixed_x" in e and "fixed_y" in e:
            points.append({"x": e["fixed_x"], "y": e["fixed_y"]})
        elif mC:
            x1, y1 = float(mC.group(1)), float(mC.group(2))
            cx1, cy1 = float(mC.group(3)), float(mC.group(4))
            cx2, cy2 = float(mC.group(5)), float(mC.group(6))
            x2, y2 = float(mC.group(7)), float(mC.group(8))
            span = abs(x2 - x1)
            t = 0.20 if (span > 600 and e.get("type") == "branch_out") else 0.5
            bx, by = get_bezier_pt(t, x1, y1, cx1, cy1, cx2, cy2, x2, y2)
            c_wire = find_colliding_wire(bx, by, pill_w)
            if c_wire:
                prefer_up = (y2 >= y1)
                target_y = (c_wire["y"] - 34) if prefer_up else (c_wire["y"] + 34)
                if find_colliding_wire(bx, target_y, pill_w):
                    target_y = (c_wire["y"] + 34) if prefer_up else (c_wire["y"] - 34)
                best_t = t
                min_diff = float("inf")
                for st in range(10 if span > 600 else 15, (40 if span > 600 else 85) + 1):
                    cand_t = st / 100.0
                    ptx, pty = get_bezier_pt(cand_t, x1, y1, cx1, cy1, cx2, cy2, x2, y2)
                    diff = abs(pty - target_y)
                    if diff < min_diff:
                        min_diff = diff
                        best_t = cand_t
                bx, by = get_bezier_pt(best_t, x1, y1, cx1, cy1, cx2, cy2, x2, y2)
                if abs(by - c_wire["y"]) < 34:
                    by = (c_wire["y"] - 34) if (target_y < c_wire["y"]) else (c_wire["y"] + 34)
            points.append({"x": bx, "y": by})
        elif mL:
            x1, y1 = float(mL.group(1)), float(mL.group(2))
            x2, y2 = float(mL.group(3)), float(mL.group(4))
            points.append({"x": (x1 + x2) / 2, "y": (y1 + y2) / 2})

        for pt in points:
            cand_y = pt["y"]
            for _ in range(8):
                adj = False
                w = find_colliding_wire(pt["x"], cand_y, pill_w)
                if w:
                    cand_y += -34 if (cand_y <= w["y"]) else 34
                    adj = True
                hit_n = find_colliding_card(pt["x"], cand_y, pill_w, 24)
                if hit_n:
                    c_cy = hit_n["y"] + hit_n.get("height", 88) / 2
                    cand_y = (hit_n["y"] - 20) if (cand_y <= c_cy) else (hit_n["y"] + hit_n.get("height", 88) + 20)
                    adj = True
                col_p = next((p for p in placed_pills if abs(p["x"] - pt["x"]) < (p["w"] + pill_w) / 2 + 10 and abs(p["y"] - cand_y) < 22), None)
                if col_p:
                    ny = (col_p["y"] - 26) if (cand_y <= col_p["y"]) else (col_p["y"] + 26)
                    rc = find_colliding_card(pt["x"], ny, pill_w, 24)
                    if rc:
                        c_cy = rc["y"] + rc.get("height", 88) / 2
                        ny = (rc["y"] - 20) if (ny <= c_cy) else (rc["y"] + rc.get("height", 88) + 20)
                    cand_y = ny
                    adj = True
                if not adj:
                    break
            pt["y"] = cand_y

            final_card_hit = find_colliding_card(pt["x"], pt["y"], pill_w, 24)
            if final_card_hit:
                card_collisions.append({"pill": lbl, "card": final_card_hit["id"], "pt": (pt["x"], pt["y"]), "context": context})

            for pp in placed_pills:
                if abs(pp["x"] - pt["x"]) < (pp["w"] + pill_w) / 2 and abs(pp["y"] - pt["y"]) < 22:
                    pill_collisions.append({"pill1": lbl, "pill2": pp["label"], "pt1": (pt["x"], pt["y"]), "pt2": (pp["x"], pp["y"]), "context": context})

            placed_pills.append({"x": pt["x"], "y": pt["y"], "w": pill_w, "label": lbl})

    return card_collisions, pill_collisions


class TestAdversarialTopologies(unittest.TestCase):

    def run_generator_and_validate(self, repo_dir, is_dirty=False, is_detached=False):
        """Helper to run generate_dag.py on repo_dir, parse output, and run all verifications."""
        out_js = os.path.join(repo_dir, "out_test.js")
        cmd = [sys.executable, GENERATE_DAG_SCRIPT, repo_dir, "-o", out_js]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"generate_dag.py failed:\n{res.stderr}\n{res.stdout}")

        with open(out_js, "r", encoding="utf-8") as f:
            content = f.read()

        prefix = "/* Auto-generated Git DAG Data */\nwindow.GIT_DAG_DATA = "
        self.assertTrue(content.startswith(prefix), f"Output missing expected prefix header:\n{content[:200]}")
        raw_json = content[len(prefix):].rstrip(";\n ")
        data = json.loads(raw_json)

        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        # 1. Zero pairwise node collisions
        collisions = check_pairwise_collisions(nodes, context=repo_dir)
        self.assertEqual(len(collisions), 0, f"Node collisions detected ({len(collisions)}): {collisions}")

        # 2. Bézier curve monotonicity (no S-kinks)
        kinks = check_bezier_curves(edges, context=repo_dir)
        self.assertEqual(len(kinks), 0, f"Bézier kinks detected ({len(kinks)}): {kinks}")

        # 3. Cable pill clearance simulation (zero pill-to-node card and zero pill-to-pill collisions)
        card_colls, pill_colls = simulate_pill_placements(data, context=repo_dir)
        self.assertEqual(len(card_colls), 0, f"Pill-to-Card collisions detected: {card_colls}")
        self.assertEqual(len(pill_colls), 0, f"Pill-to-Pill collisions detected: {pill_colls}")

        # 4. WIP Node Verification if dirty
        node_ids = {n["id"]: n for n in nodes}
        if is_dirty:
            self.assertIn("active-wip", node_ids, "active-wip node missing when repo is dirty")
            wip_node = node_ids["active-wip"]
            self.assertTrue(wip_node.get("is_wip"), "active-wip node must have is_wip=True")
            self.assertFalse(wip_node.get("is_head"), "active-wip node must have is_head=False")
            self.assertEqual(wip_node.get("status"), "wip", "active-wip node status must be 'wip'")
            wip_edges = [e for e in edges if e.get("to") == "active-wip"]
            self.assertTrue(len(wip_edges) >= 1, "Missing edge leading to active-wip")
        else:
            self.assertNotIn("active-wip", node_ids, "active-wip node present when repo is clean")

        # 5. Detached HEAD verification
        if is_detached:
            head_nodes = [n for n in nodes if n.get("is_head")]
            self.assertEqual(len(head_nodes), 1, f"Expected exactly 1 is_head node in detached HEAD, got {len(head_nodes)}")
            head_commit_sha = run_git(["rev-parse", "HEAD"], cwd=repo_dir)
            self.assertEqual(head_nodes[0]["hash"], head_commit_sha, "is_head node does not match detached HEAD commit SHA")

        # 6. Schema Validator (tools/check_schema.py --strict)
        schema_cmd = [sys.executable, CHECK_SCHEMA_SCRIPT, out_js, "--strict"]
        schema_res = subprocess.run(schema_cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(schema_res.returncode, 0, f"check_schema.py --strict failed:\n{schema_res.stdout}\n{schema_res.stderr}")

        return data

    def test_a1_five_branches_forked_from_root(self):
        """Topological test: 5 branches forked from root commit (all open/active)."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("root")
            run_git(["add", "init.txt"], cwd=td)
            run_git(["commit", "-m", "Initial root commit"], cwd=td)

            for i in range(1, 6):
                b_name = f"feature/branch-{i}"
                run_git(["checkout", "-b", b_name, "main"], cwd=td)
                with open(os.path.join(td, f"file_{i}.txt"), "w") as f:
                    f.write(f"branch {i}")
                run_git(["add", f"file_{i}.txt"], cwd=td)
                run_git(["commit", "-m", f"Commit on branch {i}"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            data = self.run_generator_and_validate(td, is_dirty=False, is_detached=False)
            self.assertEqual(len(data["nodes"]), 6)
            lanes = {n["id"]: n["lane"] for n in data["nodes"]}
            self.assertEqual(lanes[data["nodes"][0]["id"]], 0)

    def test_a2_ten_branches_forked_from_root(self):
        """Topological test: 10 branches forked from root commit to stress lane allocator."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("root")
            run_git(["add", "init.txt"], cwd=td)
            run_git(["commit", "-m", "Initial root commit"], cwd=td)

            for i in range(1, 11):
                b_name = f"feat/sub-{i}"
                run_git(["checkout", "-b", b_name, "main"], cwd=td)
                with open(os.path.join(td, f"f_{i}.txt"), "w") as f:
                    f.write(f"sub {i}")
                run_git(["add", f"f_{i}.txt"], cwd=td)
                run_git(["commit", "-m", f"feat {i} commit"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            data = self.run_generator_and_validate(td, is_dirty=False, is_detached=False)
            self.assertEqual(len(data["nodes"]), 11)

    def test_a3_co_located_branches(self):
        """Topological test: 5 branches pointing to the EXACT same commit hash."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("root")
            run_git(["add", "init.txt"], cwd=td)
            run_git(["commit", "-m", "Root commit"], cwd=td)

            for b in ["alpha", "beta", "gamma", "delta", "epsilon"]:
                run_git(["branch", b, "main"], cwd=td)

            data = self.run_generator_and_validate(td, is_dirty=False, is_detached=False)
            self.assertEqual(len(data["nodes"]), 1)
            bundle_branches = {b["name"] for b in data["branches"]}
            for b in ["main", "alpha", "beta", "gamma", "delta", "epsilon"]:
                self.assertIn(b, bundle_branches)

    def test_b1_detached_head_tip_with_dirty_wip(self):
        """Topological test: Detached HEAD at commit tip with dirty working tree."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "file.txt"), "w") as f:
                f.write("v1")
            run_git(["add", "file.txt"], cwd=td)
            run_git(["commit", "-m", "Commit 1"], cwd=td)

            with open(os.path.join(td, "file.txt"), "w") as f:
                f.write("v2")
            run_git(["add", "file.txt"], cwd=td)
            run_git(["commit", "-m", "Commit 2"], cwd=td)

            run_git(["checkout", "--detach", "HEAD"], cwd=td)

            with open(os.path.join(td, "file.txt"), "w") as f:
                f.write("v2 modified unstaged")
            with open(os.path.join(td, "new_untracked.txt"), "w") as f:
                f.write("untracked")

            data = self.run_generator_and_validate(td, is_dirty=True, is_detached=True)
            self.assertEqual(len(data["nodes"]), 3)

    def test_b2_detached_head_mid_history_with_dirty_wip(self):
        """Topological test: Detached HEAD at an older commit in mid-history with dirty tree."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "c1.txt"), "w") as f:
                f.write("1")
            run_git(["add", "c1.txt"], cwd=td)
            run_git(["commit", "-m", "Root commit 1"], cwd=td)
            c1_hash = run_git(["rev-parse", "HEAD"], cwd=td)

            with open(os.path.join(td, "c2.txt"), "w") as f:
                f.write("2")
            run_git(["add", "c2.txt"], cwd=td)
            run_git(["commit", "-m", "Main commit 2"], cwd=td)

            with open(os.path.join(td, "c3.txt"), "w") as f:
                f.write("3")
            run_git(["add", "c3.txt"], cwd=td)
            run_git(["commit", "-m", "Main commit 3"], cwd=td)

            run_git(["checkout", "--detach", c1_hash], cwd=td)

            with open(os.path.join(td, "wip_at_c1.txt"), "w") as f:
                f.write("wip change")
            run_git(["add", "wip_at_c1.txt"], cwd=td)

            data = self.run_generator_and_validate(td, is_dirty=True, is_detached=True)
            self.assertEqual(len(data["nodes"]), 4)
            node_ids = {n["id"]: n for n in data["nodes"]}
            self.assertEqual(node_ids["active-wip"]["parents"], [c1_hash])

    def test_b3_single_commit_detached_with_dirty_wip(self):
        """Boundary test: Repository with exactly 1 commit, detached HEAD, and dirty WIP."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("only commit")
            run_git(["add", "init.txt"], cwd=td)
            run_git(["commit", "-m", "Single commit"], cwd=td)

            run_git(["checkout", "--detach", "HEAD"], cwd=td)

            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("modified single commit")

            data = self.run_generator_and_validate(td, is_dirty=True, is_detached=True)
            self.assertEqual(len(data["nodes"]), 2)  # 1 commit + active-wip

    def test_c1_octopus_merge_3_parents(self):
        """Topological test: Octopus merge with 3 parents."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "master"], cwd=td)
            with open(os.path.join(td, "base.txt"), "w") as f:
                f.write("base")
            run_git(["add", "base.txt"], cwd=td)
            run_git(["commit", "-m", "Base commit"], cwd=td)

            for b in ["feat-a", "feat-b", "feat-c"]:
                run_git(["checkout", "master"], cwd=td)
                run_git(["checkout", "-b", b], cwd=td)
                with open(os.path.join(td, f"{b}.txt"), "w") as f:
                    f.write(b)
                run_git(["add", f"{b}.txt"], cwd=td)
                run_git(["commit", "-m", f"Commit on {b}"], cwd=td)

            run_git(["checkout", "master"], cwd=td)
            with open(os.path.join(td, "master_update.txt"), "w") as f:
                f.write("master work")
            run_git(["add", "master_update.txt"], cwd=td)
            run_git(["commit", "-m", "Master commit"], cwd=td)

            run_git(["merge", "feat-a", "feat-b", "feat-c", "-m", "Octopus merge 3 branches"], cwd=td)

            data = self.run_generator_and_validate(td, is_dirty=False, is_detached=False)
            merge_nodes = [n for n in data["nodes"] if n.get("is_merge")]
            self.assertEqual(len(merge_nodes), 1)
            self.assertEqual(len(merge_nodes[0]["parents"]), 4)

            merge_edges = [e for e in data["edges"] if e.get("type") == "merge"]
            self.assertEqual(len(merge_edges), 3)
            labels = [e["label"] for e in merge_edges]
            self.assertTrue(any("feat-a" in l for l in labels))
            self.assertTrue(any("feat-b" in l for l in labels))
            self.assertTrue(any("feat-c" in l for l in labels))

    def test_c2_octopus_merge_4_parents_with_dirty_wip(self):
        """Topological test: Octopus merge with 4 parents + dirty WIP."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "base.txt"), "w") as f:
                f.write("base")
            run_git(["add", "base.txt"], cwd=td)
            run_git(["commit", "-m", "Base commit"], cwd=td)

            for b in ["mod-1", "mod-2", "mod-3", "mod-4"]:
                run_git(["checkout", "main"], cwd=td)
                run_git(["checkout", "-b", b], cwd=td)
                with open(os.path.join(td, f"{b}.txt"), "w") as f:
                    f.write(b)
                run_git(["add", f"{b}.txt"], cwd=td)
                run_git(["commit", "-m", f"Commit {b}"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            run_git(["merge", "mod-1", "mod-2", "mod-3", "mod-4", "-m", "Octopus 4 parents"], cwd=td)

            with open(os.path.join(td, "post_merge_wip.txt"), "w") as f:
                f.write("dirty wip")

            data = self.run_generator_and_validate(td, is_dirty=True, is_detached=False)
            self.assertIn("active-wip", [n["id"] for n in data["nodes"]])

    def test_d1_disjoint_orphan_branches(self):
        """Topological test: Multiple independent orphan roots (disjoint histories)."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "main_file.txt"), "w") as f:
                f.write("main")
            run_git(["add", "main_file.txt"], cwd=td)
            run_git(["commit", "-m", "Main root commit"], cwd=td)

            run_git(["checkout", "--orphan", "orphan-docs"], cwd=td)
            run_git(["rm", "-rf", "."], cwd=td)
            with open(os.path.join(td, "docs.txt"), "w") as f:
                f.write("documentation")
            run_git(["add", "docs.txt"], cwd=td)
            run_git(["commit", "-m", "Docs root commit"], cwd=td)

            with open(os.path.join(td, "guide.txt"), "w") as f:
                f.write("guide")
            run_git(["add", "guide.txt"], cwd=td)
            run_git(["commit", "-m", "Docs guide update"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            data = self.run_generator_and_validate(td, is_dirty=False, is_detached=False)
            self.assertEqual(len(data["nodes"]), 3)

    def test_d2_unrelated_histories_merge(self):
        """Topological test: Orphan branch merged into main via --allow-unrelated-histories."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "m.txt"), "w") as f:
                f.write("m")
            run_git(["add", "m.txt"], cwd=td)
            run_git(["commit", "-m", "Main root"], cwd=td)

            run_git(["checkout", "--orphan", "legacy-code"], cwd=td)
            run_git(["rm", "-rf", "."], cwd=td)
            with open(os.path.join(td, "legacy.txt"), "w") as f:
                f.write("legacy")
            run_git(["add", "legacy.txt"], cwd=td)
            run_git(["commit", "-m", "Legacy root commit"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            run_git(["merge", "--allow-unrelated-histories", "legacy-code", "-m", "Merge unrelated legacy"], cwd=td)

            data = self.run_generator_and_validate(td, is_dirty=False, is_detached=False)
            self.assertEqual(len(data["nodes"]), 3)

    def test_e1_extreme_composite_topology(self):
        """Adversarial stress test: Combines disjoint roots, 5 branches, octopus merge, detached HEAD, dirty WIP."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "r1.txt"), "w") as f:
                f.write("root 1")
            run_git(["add", "r1.txt"], cwd=td)
            run_git(["commit", "-m", "Root 1 commit"], cwd=td)

            for i in range(1, 6):
                run_git(["checkout", "main"], cwd=td)
                run_git(["checkout", "-b", f"service-{i}"], cwd=td)
                with open(os.path.join(td, f"svc_{i}.txt"), "w") as f:
                    f.write(f"svc {i}")
                run_git(["add", f"svc_{i}.txt"], cwd=td)
                run_git(["commit", "-m", f"Service {i} commit"], cwd=td)

            run_git(["checkout", "--orphan", "orphan-infra"], cwd=td)
            run_git(["rm", "-rf", "."], cwd=td)
            with open(os.path.join(td, "infra.txt"), "w") as f:
                f.write("infra")
            run_git(["add", "infra.txt"], cwd=td)
            run_git(["commit", "-m", "Infra independent root"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            with open(os.path.join(td, "m_up.txt"), "w") as f:
                f.write("main update")
            run_git(["add", "m_up.txt"], cwd=td)
            run_git(["commit", "-m", "Main update commit"], cwd=td)

            run_git(["merge", "service-1", "service-2", "service-3", "-m", "Octopus 3 services"], cwd=td)

            s4_hash = run_git(["rev-parse", "service-4"], cwd=td)
            run_git(["checkout", "--detach", s4_hash], cwd=td)

            with open(os.path.join(td, "svc_4.txt"), "w") as f:
                f.write("modified svc 4 unstaged")
            with open(os.path.join(td, "untracked_adversarial.txt"), "w") as f:
                f.write("untracked test")

            data = self.run_generator_and_validate(td, is_dirty=True, is_detached=True)
            node_ids = {n["id"]: n for n in data["nodes"]}
            self.assertIn("active-wip", node_ids)
            self.assertEqual(node_ids["active-wip"]["parents"], [s4_hash])
            self.assertTrue(node_ids[s4_hash]["is_head"])

    def test_f1_thai_and_unicode_metadata_with_wip(self):
        """Adversarial stress test: Non-ASCII UTF-8 branch names, Thai subjects, emojis, and dirty WIP."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w", encoding="utf-8") as f:
                f.write("เริ่มต้นโปรเจกต์")
            run_git(["add", "init.txt"], cwd=td)
            run_git(["commit", "-m", "คอมมิตแรกบนสายหลัก 🚀"], cwd=td, author_name="สมชาย พัฒนา", author_email="somchai@dev.th")

            # Thai branch names
            for b_name in ["feature/ระบบล็อกอิน-OAuth2", "feature/แก้บั๊ก-การคำนวณเงิน-💸"]:
                run_git(["checkout", "main"], cwd=td)
                run_git(["checkout", "-b", b_name], cwd=td)
                with open(os.path.join(td, "code.txt"), "w", encoding="utf-8") as f:
                    f.write(f"เนื้อหาสำหรับ {b_name}")
                run_git(["add", "code.txt"], cwd=td)
                run_git(["commit", "-m", f"ปรับปรุง {b_name} เรียบร้อย ✨"], cwd=td, author_name="สิทธิชัย โค้ดเดอร์", author_email="sitt@dev.th")

            run_git(["checkout", "main"], cwd=td)
            # Add dirty WIP with Thai characters
            with open(os.path.join(td, "wip_thai.txt"), "w", encoding="utf-8") as f:
                f.write("งานที่ยังทำไม่เสร็จ")

            data = self.run_generator_and_validate(td, is_dirty=True, is_detached=False)
            self.assertIn("active-wip", [n["id"] for n in data["nodes"]])

    def test_f2_criss_cross_merges(self):
        """Topological test: Criss-cross merges between two feature branches before merging to main."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            with open(os.path.join(td, "base.txt"), "w") as f:
                f.write("base")
            run_git(["add", "base.txt"], cwd=td)
            run_git(["commit", "-m", "Base commit"], cwd=td)

            run_git(["checkout", "-b", "feat-x", "main"], cwd=td)
            with open(os.path.join(td, "x1.txt"), "w") as f:
                f.write("x1")
            run_git(["add", "x1.txt"], cwd=td)
            run_git(["commit", "-m", "feat-x commit 1"], cwd=td)

            run_git(["checkout", "-b", "feat-y", "main"], cwd=td)
            with open(os.path.join(td, "y1.txt"), "w") as f:
                f.write("y1")
            run_git(["add", "y1.txt"], cwd=td)
            run_git(["commit", "-m", "feat-y commit 1"], cwd=td)

            # Criss-cross merge: feat-x merges feat-y
            run_git(["checkout", "feat-x"], cwd=td)
            run_git(["merge", "feat-y", "-m", "Merge feat-y into feat-x"], cwd=td)

            # feat-y advances and merges feat-x
            run_git(["checkout", "feat-y"], cwd=td)
            with open(os.path.join(td, "y2.txt"), "w") as f:
                f.write("y2")
            run_git(["add", "y2.txt"], cwd=td)
            run_git(["commit", "-m", "feat-y commit 2"], cwd=td)
            run_git(["merge", "feat-x", "-m", "Merge feat-x into feat-y"], cwd=td)

            # Merge feat-y into main with --no-ff to create true 7th merge commit
            run_git(["checkout", "main"], cwd=td)
            run_git(["merge", "--no-ff", "feat-y", "-m", "Merge feat-y into main"], cwd=td)

            data = self.run_generator_and_validate(td, is_dirty=False, is_detached=False)
            self.assertEqual(len(data["nodes"]), 7)


if __name__ == "__main__":
    unittest.main()
