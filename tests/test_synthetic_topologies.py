#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthetic Topologies Automated Regression Suite (Milestone M4 - Feature F18)

Comprehensive unittest.TestCase suite verifying Git DAG generation across
all synthetic topologies and boundary conditions:
1. Multiple branches forking from the same commit (root and mid-branch, co-located refs).
2. Detached HEAD with uncommitted changes (tip, mid-history, root, clean/dirty transitions).
3. Octopus merges with 3+ parents and multi-depth branches.
4. Orphan / multiple root commits and unrelated histories merge.
5. Clean working tree vs dirty working tree (staged, unstaged, untracked, side-branch WIP).
6. Linear fast-forward sequences, criss-cross merges, and deep linear histories.
7. Extreme composite stress topology.

Automated Assertions per Topology:
- generate_dag.py runs and exits with code 0.
- Pairwise node bounding box collision check: abs(dx) < 300 and abs(dy) < 88 == 0.
- tools/check_schema.py --strict exits with code 0.
- Bezier curve control point monotonicity: CP1_x <= CP2_x (no S-kinks).
- Frontend pill placement relaxation simulation (zero pill-card, zero pill-pill overlaps).
- Relational integrity: WIP node placement, head commit connectivity, detached HEAD tracking.
- Hermetic isolation using tempfile.TemporaryDirectory().
"""

import os
import sys
import json
import re
import tempfile
import subprocess
import unittest
from typing import Dict, Any, List, Tuple, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATE_DAG_SCRIPT = os.path.join(REPO_ROOT, "generate_dag.py")
CHECK_SCHEMA_SCRIPT = os.path.join(REPO_ROOT, "tools", "check_schema.py")


def run_git(args: List[str], cwd: str, author_name: str = "Test Dev", author_email: str = "dev@example.com") -> str:
    """Execute git command in cwd with isolated identity and configuration."""
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = author_name
    env["GIT_AUTHOR_EMAIL"] = author_email
    env["GIT_COMMITTER_NAME"] = author_name
    env["GIT_COMMITTER_EMAIL"] = author_email
    env["GIT_CONFIG_GLOBAL"] = ""
    env["GIT_CONFIG_SYSTEM"] = ""

    cmd = ["git"] + args
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
    return res.stdout.strip()


def check_pairwise_collisions(nodes: List[Dict[str, Any]], context: str = "") -> List[Dict[str, Any]]:
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


def check_bezier_curves(edges: List[Dict[str, Any]], context: str = "") -> List[Dict[str, Any]]:
    """Verify that Bézier curves do not have horizontal reversal bulges (CP1_x <= CP2_x)."""
    kinks = []
    bezier_re = re.compile(r"C\s+([\d\.\-]+)\s+([\d\.\-]+),\s+([\d\.\-]+)\s+([\d\.\-]+),\s+([\d\.\-]+)\s+([\d\.\-]+)")
    for edge in edges:
        path = edge.get("svg_path", "")
        for m in bezier_re.finditer(path):
            cp1_x = float(m.group(1))
            cp2_x = float(m.group(3))
            if cp1_x > cp2_x + 1e-4:
                kinks.append({
                    "edge_id": edge.get("id"),
                    "cp1_x": cp1_x,
                    "cp2_x": cp2_x,
                    "path": path,
                    "context": context
                })
    return kinks


def simulate_pill_placements(data: Dict[str, Any], context: str = "") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Simulate frontend 8-iteration relaxation solver to detect card and pill collisions."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    def get_bezier_pt(t, x1, y1, cx1, cy1, cx2, cy2, x2, y2):
        u = 1 - t
        return (
            u**3 * x1 + 3 * u**2 * t * cx1 + 3 * u * t**2 * cx2 + t**3 * x2,
            u**3 * y1 + 3 * u**2 * t * cy1 + 3 * u * t**2 * cy2 + t**3 * y2
        )

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


class TestSyntheticTopologies(unittest.TestCase):
    """Permanent automated test suite for synthetic Git topologies."""

    def _run_and_validate(
        self,
        repo_dir: str,
        is_dirty: bool = False,
        is_detached: bool = False,
        expected_nodes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run generate_dag.py on repo_dir, parse output, and execute all automated assertions."""
        out_js = os.path.join(repo_dir, "out_test.js")
        cmd = [sys.executable, GENERATE_DAG_SCRIPT, repo_dir, "-o", out_js]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"generate_dag.py failed:\n{res.stderr}\n{res.stdout}")
        self.assertTrue(os.path.exists(out_js), "out_test.js was not created")

        # Verify no temporary files remain
        tmp_files = [f for f in os.listdir(repo_dir) if f.startswith(".tmp-") or f.endswith(".tmp")]
        self.assertEqual(len(tmp_files), 0, f"Lingering temporary files found: {tmp_files}")

        with open(out_js, "r", encoding="utf-8") as f:
            content = f.read()

        prefix = "/* Auto-generated Git DAG Data */\nwindow.GIT_DAG_DATA = "
        self.assertTrue(content.startswith(prefix), f"Output missing expected prefix header:\n{content[:200]}")
        raw_json = content[len(prefix):].rstrip(";\n ")
        data = json.loads(raw_json)

        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        if expected_nodes is not None:
            self.assertEqual(len(nodes), expected_nodes, f"Expected {expected_nodes} nodes, got {len(nodes)}")

        # 1. Zero pairwise node bounding box overlaps (dx < 300 and dy < 88)
        collisions = check_pairwise_collisions(nodes, context=repo_dir)
        self.assertEqual(len(collisions), 0, f"Pairwise node collisions detected ({len(collisions)}): {collisions}")

        # 2. Bézier curve monotonicity (CP1_x <= CP2_x)
        kinks = check_bezier_curves(edges, context=repo_dir)
        self.assertEqual(len(kinks), 0, f"Bézier kinks detected ({len(kinks)}): {kinks}")

        # 3. Cable pill clearance simulation (zero card and zero pill-pill collisions)
        card_colls, pill_colls = simulate_pill_placements(data, context=repo_dir)
        self.assertEqual(len(card_colls), 0, f"Pill-to-Card collisions detected: {card_colls}")
        self.assertEqual(len(pill_colls), 0, f"Pill-to-Pill collisions detected: {pill_colls}")

        # 4. WIP Node relational integrity
        node_ids = {n["id"]: n for n in nodes}
        if is_dirty:
            self.assertIn("active-wip", node_ids, "active-wip node missing when repository is dirty")
            wip_node = node_ids["active-wip"]
            self.assertTrue(wip_node.get("is_wip"), "active-wip node must have is_wip=True")
            self.assertFalse(wip_node.get("is_head"), "active-wip node must have is_head=False")
            self.assertEqual(wip_node.get("status"), "wip", "active-wip node status must be 'wip'")
            wip_edges = [e for e in edges if e.get("to") == "active-wip"]
            self.assertTrue(len(wip_edges) >= 1, "Missing edge leading to active-wip")
            self.assertTrue(data.get("status", {}).get("is_dirty"), "status.is_dirty must be True when dirty")
        else:
            self.assertNotIn("active-wip", node_ids, "active-wip node must NOT be present when repository is clean")
            wip_nodes = [n for n in nodes if n.get("is_wip")]
            self.assertEqual(len(wip_nodes), 0, "No node may declare is_wip=True when repository is clean")
            self.assertFalse(data.get("status", {}).get("is_dirty"), "status.is_dirty must be False when clean")

        # 5. Detached HEAD relational integrity
        if is_detached:
            head_nodes = [n for n in nodes if n.get("is_head")]
            self.assertEqual(len(head_nodes), 1, f"Expected exactly 1 is_head node in detached HEAD, got {len(head_nodes)}")
            head_sha = run_git(["rev-parse", "HEAD"], cwd=repo_dir)
            self.assertEqual(head_nodes[0]["hash"], head_sha, "is_head node hash does not match detached HEAD commit SHA")
            self.assertEqual(data.get("head_branch"), "DETACHED", "head_branch must be 'DETACHED'")

        # 6. Schema strict compliance (tools/check_schema.py --strict)
        schema_cmd = [sys.executable, CHECK_SCHEMA_SCRIPT, out_js, "--strict"]
        schema_res = subprocess.run(schema_cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(schema_res.returncode, 0, f"check_schema.py --strict failed:\n{schema_res.stdout}\n{schema_res.stderr}")

        return data

    # =========================================================================
    # Category 1: Multiple branches forking from the same commit
    # =========================================================================

    def test_01_forking_5_branches_from_root(self):
        """Topology 1.1: 5 feature branches forked from root commit (all active/open)."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
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
            data = self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=6)
            lanes = [n["lane"] for n in data["nodes"]]
            self.assertEqual(len(set(lanes)), 6, "Every open branch should receive an independent collision-free lane")

    def test_02_forking_5_branches_from_mid_branch(self):
        """Topology 1.2: 5 feature branches forked from a mid-history commit on trunk."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "f0.txt"), "w") as f:
                f.write("0")
            run_git(["add", "f0.txt"], cwd=td)
            run_git(["commit", "-m", "C0 root"], cwd=td)

            with open(os.path.join(td, "f1.txt"), "w") as f:
                f.write("1")
            run_git(["add", "f1.txt"], cwd=td)
            run_git(["commit", "-m", "C1 mid"], cwd=td)
            c1_hash = run_git(["rev-parse", "HEAD"], cwd=td)

            with open(os.path.join(td, "f2.txt"), "w") as f:
                f.write("2")
            run_git(["add", "f2.txt"], cwd=td)
            run_git(["commit", "-m", "C2 tip"], cwd=td)

            for i in range(1, 6):
                b_name = f"mid-feat-{i}"
                run_git(["checkout", "-b", b_name, c1_hash], cwd=td)
                with open(os.path.join(td, f"mf_{i}.txt"), "w") as f:
                    f.write(str(i))
                run_git(["add", f"mf_{i}.txt"], cwd=td)
                run_git(["commit", "-m", f"mid feat {i}"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            # 3 trunk commits + 5 mid branches = 8 nodes
            self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=8)

    def test_03_co_located_branches_same_commit(self):
        """Topology 1.3: 5 branch refs pointing to the exact same commit hash."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("root")
            run_git(["add", "init.txt"], cwd=td)
            run_git(["commit", "-m", "Root commit"], cwd=td)

            for b in ["alpha", "beta", "gamma", "delta", "epsilon"]:
                run_git(["branch", b, "main"], cwd=td)

            data = self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=1)
            b_names = {b["name"] for b in data["branches"]}
            for b in ["main", "alpha", "beta", "gamma", "delta", "epsilon"]:
                self.assertIn(b, b_names)

    # =========================================================================
    # Category 2: Detached HEAD with uncommitted changes (WIP)
    # =========================================================================

    def test_04_detached_head_at_tip_with_dirty_wip(self):
        """Topology 2.1: Detached HEAD at commit tip with unstaged and untracked changes."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "f.txt"), "w") as f:
                f.write("v1")
            run_git(["add", "f.txt"], cwd=td)
            run_git(["commit", "-m", "Commit 1"], cwd=td)

            with open(os.path.join(td, "f.txt"), "w") as f:
                f.write("v2")
            run_git(["add", "f.txt"], cwd=td)
            run_git(["commit", "-m", "Commit 2"], cwd=td)

            run_git(["checkout", "--detach", "HEAD"], cwd=td)

            with open(os.path.join(td, "f.txt"), "w") as f:
                f.write("v2 modified unstaged")
            with open(os.path.join(td, "untracked.txt"), "w") as f:
                f.write("untracked")

            # 2 commits + active-wip = 3 nodes
            self._run_and_validate(td, is_dirty=True, is_detached=True, expected_nodes=3)

    def test_05_detached_head_mid_history_with_dirty_wip(self):
        """Topology 2.2: Detached HEAD at older commit in mid-history with dirty working tree."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
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

            # 3 commits + active-wip = 4 nodes
            data = self._run_and_validate(td, is_dirty=True, is_detached=True, expected_nodes=4)
            node_ids = {n["id"]: n for n in data["nodes"]}
            self.assertEqual(node_ids["active-wip"]["parents"], [c1_hash])

    def test_06_detached_head_at_root_commit_with_dirty_wip(self):
        """Topology 2.3: Repository with exactly 1 commit, detached HEAD, and dirty WIP."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("only")
            run_git(["add", "init.txt"], cwd=td)
            run_git(["commit", "-m", "Single commit"], cwd=td)

            run_git(["checkout", "--detach", "HEAD"], cwd=td)
            with open(os.path.join(td, "init.txt"), "w") as f:
                f.write("modified single commit")

            self._run_and_validate(td, is_dirty=True, is_detached=True, expected_nodes=2)

    def test_07_detached_head_clean_vs_dirty_transition(self):
        """Topology 2.4: Clean detached HEAD state followed by dirty transition."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "f.txt"), "w") as f:
                f.write("init")
            run_git(["add", "f.txt"], cwd=td)
            run_git(["commit", "-m", "Init"], cwd=td)

            run_git(["checkout", "--detach", "HEAD"], cwd=td)
            # Step A: Clean detached HEAD
            self._run_and_validate(td, is_dirty=False, is_detached=True, expected_nodes=1)

            # Step B: Transition to dirty
            with open(os.path.join(td, "new_file.txt"), "w") as f:
                f.write("dirty")
            self._run_and_validate(td, is_dirty=True, is_detached=True, expected_nodes=2)

    # =========================================================================
    # Category 3: Octopus merges with 3+ parents
    # =========================================================================

    def test_08_octopus_merge_3_parents_clean(self):
        """Topology 3.1: Clean octopus merge combining 3 distinct parent branches into master."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "master"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
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
            with open(os.path.join(td, "m_up.txt"), "w") as f:
                f.write("master update")
            run_git(["add", "m_up.txt"], cwd=td)
            run_git(["commit", "-m", "Master commit"], cwd=td)

            run_git(["merge", "feat-a", "feat-b", "feat-c", "-m", "Octopus merge 3 branches"], cwd=td)

            data = self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=6)
            merge_nodes = [n for n in data["nodes"] if n.get("is_merge")]
            self.assertEqual(len(merge_nodes), 1)
            self.assertEqual(len(merge_nodes[0]["parents"]), 4)

    def test_09_octopus_merge_4_parents_with_dirty_wip(self):
        """Topology 3.2: Octopus merge with 4 parents and active uncommitted WIP."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
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

            self._run_and_validate(td, is_dirty=True, is_detached=False, expected_nodes=7)

    def test_10_octopus_merge_multi_lane_depths(self):
        """Topology 3.3: Octopus merge with branches of unequal commit depths (1, 2, and 3 commits)."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "base.txt"), "w") as f:
                f.write("base")
            run_git(["add", "base.txt"], cwd=td)
            run_git(["commit", "-m", "Base commit"], cwd=td)

            for depth in [1, 2, 3]:
                b_name = f"depth-{depth}"
                run_git(["checkout", "-b", b_name, "main"], cwd=td)
                for step in range(depth):
                    with open(os.path.join(td, f"d{depth}_{step}.txt"), "w") as f:
                        f.write(f"d{depth}_{step}")
                    run_git(["add", f"d{depth}_{step}.txt"], cwd=td)
                    run_git(["commit", "-m", f"Commit {b_name} step {step}"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            run_git(["merge", "depth-1", "depth-2", "depth-3", "-m", "Octopus multi-depth merge"], cwd=td)

            # 1 base + (1 + 2 + 3) branch commits + 1 merge = 8 nodes
            self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=8)

    # =========================================================================
    # Category 4: Orphan / multiple root commits
    # =========================================================================

    def test_11_orphan_disjoint_two_unrelated_histories(self):
        """Topology 4.1: Two disjoint orphan histories with independent root commits."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "main.txt"), "w") as f:
                f.write("main")
            run_git(["add", "main.txt"], cwd=td)
            run_git(["commit", "-m", "Main root commit"], cwd=td)

            run_git(["checkout", "--orphan", "orphan-docs"], cwd=td)
            run_git(["rm", "-rf", "."], cwd=td)
            with open(os.path.join(td, "docs.txt"), "w") as f:
                f.write("docs 1")
            run_git(["add", "docs.txt"], cwd=td)
            run_git(["commit", "-m", "Docs root commit"], cwd=td)

            with open(os.path.join(td, "docs.txt"), "w") as f:
                f.write("docs 2")
            run_git(["add", "docs.txt"], cwd=td)
            run_git(["commit", "-m", "Docs update commit"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=3)

    def test_12_orphan_three_independent_root_histories(self):
        """Topology 4.2: Three independent root histories coexisting in one repository."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "m.txt"), "w") as f:
                f.write("m")
            run_git(["add", "m.txt"], cwd=td)
            run_git(["commit", "-m", "Main root"], cwd=td)

            run_git(["checkout", "--orphan", "orphan-docs"], cwd=td)
            run_git(["rm", "-rf", "."], cwd=td)
            with open(os.path.join(td, "d.txt"), "w") as f:
                f.write("d")
            run_git(["add", "d.txt"], cwd=td)
            run_git(["commit", "-m", "Docs root"], cwd=td)

            run_git(["checkout", "--orphan", "orphan-tools"], cwd=td)
            run_git(["rm", "-rf", "."], cwd=td)
            with open(os.path.join(td, "t.txt"), "w") as f:
                f.write("t")
            run_git(["add", "t.txt"], cwd=td)
            run_git(["commit", "-m", "Tools root"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=3)

    def test_13_orphan_merge_with_allow_unrelated_histories(self):
        """Topology 4.3: Merging an orphan history into main via --allow-unrelated-histories."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "m.txt"), "w") as f:
                f.write("m")
            run_git(["add", "m.txt"], cwd=td)
            run_git(["commit", "-m", "Main root"], cwd=td)

            run_git(["checkout", "--orphan", "legacy"], cwd=td)
            run_git(["rm", "-rf", "."], cwd=td)
            with open(os.path.join(td, "leg.txt"), "w") as f:
                f.write("leg")
            run_git(["add", "leg.txt"], cwd=td)
            run_git(["commit", "-m", "Legacy root"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            run_git(["merge", "--allow-unrelated-histories", "legacy", "-m", "Merge unrelated legacy"], cwd=td)

            self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=3)

    # =========================================================================
    # Category 5: Clean working tree vs dirty working tree
    # =========================================================================

    def test_14_clean_working_tree_no_wip_node(self):
        """Topology 5.1: Clean linear repository ensuring zero WIP nodes and status.is_dirty=False."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            for i in range(3):
                with open(os.path.join(td, f"c_{i}.txt"), "w") as f:
                    f.write(str(i))
                run_git(["add", f"c_{i}.txt"], cwd=td)
                run_git(["commit", "-m", f"Clean commit {i}"], cwd=td)

            self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=3)

    def test_15_dirty_working_tree_staged_unstaged_untracked(self):
        """Topology 5.2: Dirty working tree with staged, unstaged, and untracked changes."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "staged.txt"), "w") as f:
                f.write("initial staged")
            with open(os.path.join(td, "unstaged.txt"), "w") as f:
                f.write("initial unstaged")
            run_git(["add", "."], cwd=td)
            run_git(["commit", "-m", "Base commit"], cwd=td)

            # Staged modification
            with open(os.path.join(td, "staged.txt"), "w") as f:
                f.write("modified staged")
            run_git(["add", "staged.txt"], cwd=td)

            # Unstaged modification
            with open(os.path.join(td, "unstaged.txt"), "w") as f:
                f.write("modified unstaged")

            # Untracked file
            with open(os.path.join(td, "untracked.txt"), "w") as f:
                f.write("new untracked file")

            data = self._run_and_validate(td, is_dirty=True, is_detached=False, expected_nodes=2)
            self.assertTrue(data["status"]["dirty_count"] >= 3)

    def test_16_dirty_working_tree_on_side_branch(self):
        """Topology 5.3: Dirty working tree located on an active side feature branch."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "main.txt"), "w") as f:
                f.write("main")
            run_git(["add", "main.txt"], cwd=td)
            run_git(["commit", "-m", "Main commit"], cwd=td)

            run_git(["checkout", "-b", "feature/auth", "main"], cwd=td)
            with open(os.path.join(td, "auth.txt"), "w") as f:
                f.write("auth code")
            run_git(["add", "auth.txt"], cwd=td)
            run_git(["commit", "-m", "Feature auth commit"], cwd=td)

            with open(os.path.join(td, "auth_wip.txt"), "w") as f:
                f.write("uncommitted work on auth branch")

            data = self._run_and_validate(td, is_dirty=True, is_detached=False, expected_nodes=3)
            self.assertEqual(data.get("head_branch"), "feature/auth")

    # =========================================================================
    # Category 6: Linear fast-forward sequences and criss-cross merges
    # =========================================================================

    def test_17_linear_fast_forward_sequence(self):
        """Topology 6.1: Linear fast-forward merge preserving single trunk Lane 0 continuity."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            with open(os.path.join(td, "f.txt"), "w") as f:
                f.write("0")
            run_git(["add", "f.txt"], cwd=td)
            run_git(["commit", "-m", "C0"], cwd=td)

            run_git(["checkout", "-b", "feat/fast", "main"], cwd=td)
            with open(os.path.join(td, "f.txt"), "w") as f:
                f.write("1")
            run_git(["add", "f.txt"], cwd=td)
            run_git(["commit", "-m", "C1"], cwd=td)

            with open(os.path.join(td, "f.txt"), "w") as f:
                f.write("2")
            run_git(["add", "f.txt"], cwd=td)
            run_git(["commit", "-m", "C2"], cwd=td)

            run_git(["checkout", "main"], cwd=td)
            run_git(["merge", "feat/fast"], cwd=td)

            data = self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=3)
            for node in data["nodes"]:
                self.assertEqual(node["lane"], 0, f"Fast-forward commit {node['id']} should remain on Lane 0")

    def test_18_criss_cross_merges_two_feature_branches(self):
        """Topology 6.2: Criss-cross merges between two concurrent branches before merging to main."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
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

            # Criss-cross step 1: feat-x merges feat-y
            run_git(["checkout", "feat-x"], cwd=td)
            run_git(["merge", "feat-y", "-m", "Merge feat-y into feat-x"], cwd=td)

            # Criss-cross step 2: feat-y advances and merges feat-x
            run_git(["checkout", "feat-y"], cwd=td)
            with open(os.path.join(td, "y2.txt"), "w") as f:
                f.write("y2")
            run_git(["add", "y2.txt"], cwd=td)
            run_git(["commit", "-m", "feat-y commit 2"], cwd=td)
            run_git(["merge", "feat-x", "-m", "Merge feat-x into feat-y"], cwd=td)

            # Merge into main
            run_git(["checkout", "main"], cwd=td)
            run_git(["merge", "--no-ff", "feat-y", "-m", "Merge feat-y into main"], cwd=td)

            self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=7)

    def test_19_deep_linear_history_lane0_continuity(self):
        """Topology 6.3: Deep linear sequence (25 commits) testing X-coordinate progression."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
            for i in range(25):
                with open(os.path.join(td, "f.txt"), "w") as f:
                    f.write(str(i))
                run_git(["add", "f.txt"], cwd=td)
                run_git(["commit", "-m", f"commit {i}"], cwd=td)

            data = self._run_and_validate(td, is_dirty=False, is_detached=False, expected_nodes=25)
            # Verify X-coordinate strictly increases
            x_coords = [n["x"] for n in data["nodes"]]
            for k in range(len(x_coords) - 1):
                self.assertLess(x_coords[k], x_coords[k + 1], "X-coordinates must be strictly monotonic")

    # =========================================================================
    # Category 7: Extreme composite topology
    # =========================================================================

    def test_20_extreme_composite_topology(self):
        """Topology 7.1: Combines disjoint roots, 5 branches, octopus merge, detached HEAD, dirty WIP."""
        with tempfile.TemporaryDirectory() as td:
            run_git(["init", "-b", "main"], cwd=td)
            run_git(["config", "core.autocrlf", "false"], cwd=td)
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

            data = self._run_and_validate(td, is_dirty=True, is_detached=True)
            node_ids = {n["id"]: n for n in data["nodes"]}
            self.assertIn("active-wip", node_ids)
            self.assertEqual(node_ids["active-wip"]["parents"], [s4_hash])
            self.assertTrue(node_ids[s4_hash]["is_head"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
