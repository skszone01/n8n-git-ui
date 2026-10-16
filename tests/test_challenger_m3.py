#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adversarial Stress Test Suite for Milestone M3
Author: Challenger 1 (teamwork_preview_challenger_m3_1)

Tests:
1. Pairwise Node Collision Boundary Conditions (dx=299/300, dy=87/88, dx=0 dy=0, negative, large, float)
2. Relational Integrity Edge Cases under --strict (dirty without WIP, clean with WIP, missing head_commit, dangling edges, missing primary_branch, schema_version != 2)
3. Non-strict mode behavior
4. Pre-commit leak guard (scripts/verify_no_leak.py) and .gitignore active enforcement
"""

import os
import sys
import json
import copy
import tempfile
import subprocess
import unittest
from typing import Dict, Any, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHECK_SCHEMA_PY = os.path.join(REPO_ROOT, "tools", "check_schema.py")
VERIFY_NO_LEAK_PY = os.path.join(REPO_ROOT, "scripts", "verify_no_leak.py")

BASE_VALID_DATA: Dict[str, Any] = {
    "repo": "adversarial-test-repo",
    "primary_branch": "main",
    "head_branch": "main",
    "head_commit": "node-1",
    "schema_version": 2,
    "status": {
        "is_dirty": False,
        "dirty_count": 0
    },
    "branches": [
        {
            "name": "main",
            "commit": "node-1",
            "color": "#4a90e2",
            "lane": 0
        }
    ],
    "nodes": [
        {
            "id": "node-1",
            "short_hash": "a1b2c3d",
            "title": "Root commit",
            "author": "Alice <alice@example.com>",
            "date": "2026-10-17 00:00:00",
            "branches": ["main"],
            "parents": [],
            "lane": 0,
            "x": 0,
            "y": 0,
            "width": 300,
            "height": 88,
            "is_head": True,
            "is_merge": False,
            "is_wip": False
        }
    ],
    "edges": []
}


def run_check_schema(data: Dict[str, Any], strict: bool = True) -> Tuple[int, str, str]:
    """Write data to a temp JS file and execute check_schema.py."""
    js_content = f"window.GIT_DAG_DATA = {json.dumps(data, indent=2)};\n"
    with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as f:
        f.write(js_content)
        temp_path = f.name

    try:
        cmd = [sys.executable, CHECK_SCHEMA_PY, temp_path]
        if strict:
            cmd.append("--strict")
        res = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode, res.stdout, res.stderr
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


class TestCollisionBoundaries(unittest.TestCase):
    """Test geometric collision boundary conditions on check_schema.py."""

    def _create_two_nodes(self, x1: float, y1: float, x2: float, y2: float) -> Dict[str, Any]:
        data = copy.deepcopy(BASE_VALID_DATA)
        data["nodes"][0]["x"] = x1
        data["nodes"][0]["y"] = y1

        second_node = copy.deepcopy(data["nodes"][0])
        second_node["id"] = "node-2"
        second_node["short_hash"] = "e5f6a7b"
        second_node["is_head"] = False
        second_node["branches"] = []
        second_node["parents"] = ["node-1"]
        second_node["x"] = x2
        second_node["y"] = y2
        second_node["lane"] = 1

        data["nodes"].append(second_node)
        data["edges"].append({
            "id": "e1-2",
            "from": "node-1",
            "to": "node-2",
            "svg_path": "M 0 0 L 100 100",
            "color": "#4a90e2"
        })
        return data

    def test_boundary_dx299_dy87_must_fail(self):
        """dx=299 (<300), dy=87 (<88) -> Inside bounding box, MUST fail with COLLISION_ERROR."""
        data = self._create_two_nodes(0, 0, 299, 87)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 1, f"Expected exit code 1, got {code}. Stdout: {stdout}")
        self.assertIn("COLLISION_ERROR", stdout)
        self.assertIn("dx=299", stdout)
        self.assertIn("dy=87", stdout)

    def test_boundary_dx300_dy87_must_pass(self):
        """dx=300 (>=300), dy=87 (<88) -> Exact X boundary edge-to-edge, MUST pass."""
        data = self._create_two_nodes(0, 0, 300, 87)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 0, f"Expected exit code 0 on dx=300 boundary, got {code}. Stdout: {stdout}")
        self.assertIn("Collisions:      0", stdout)
        self.assertIn("RESULT: SUCCESS", stdout)

    def test_boundary_dx299_dy88_must_pass(self):
        """dx=299 (<300), dy=88 (>=88) -> Exact Y boundary edge-to-edge, MUST pass."""
        data = self._create_two_nodes(0, 0, 299, 88)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 0, f"Expected exit code 0 on dy=88 boundary, got {code}. Stdout: {stdout}")
        self.assertIn("Collisions:      0", stdout)
        self.assertIn("RESULT: SUCCESS", stdout)

    def test_boundary_dx300_dy88_must_pass(self):
        """dx=300 (>=300), dy=88 (>=88) -> Both boundaries met, MUST pass."""
        data = self._create_two_nodes(0, 0, 300, 88)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 0, f"Expected exit code 0 on dx=300, dy=88, got {code}. Stdout: {stdout}")
        self.assertIn("Collisions:      0", stdout)
        self.assertIn("RESULT: SUCCESS", stdout)

    def test_identical_coordinates_must_fail(self):
        """Identical coordinates (dx=0, dy=0) between distinct nodes -> MUST fail."""
        data = self._create_two_nodes(100, 200, 100, 200)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 1, f"Expected exit code 1 for identical coords, got {code}. Stdout: {stdout}")
        self.assertIn("COLLISION_ERROR", stdout)
        self.assertIn("dx=0", stdout)
        self.assertIn("dy=0", stdout)

    def test_negative_coordinates_collision_must_fail(self):
        """Overlapping nodes in negative coordinate space -> MUST fail."""
        # Node 1 at (-200, -100), Node 2 at (-50, -30) -> dx=150 (<300), dy=70 (<88)
        data = self._create_two_nodes(-200, -100, -50, -30)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 1, f"Expected exit code 1 for negative coords collision, got {code}")
        self.assertIn("COLLISION_ERROR", stdout)
        self.assertIn("dx=150", stdout)
        self.assertIn("dy=70", stdout)

    def test_negative_coordinates_non_overlapping_must_pass(self):
        """Non-overlapping nodes in negative coordinate space -> MUST pass."""
        # Node 1 at (-1000, -500), Node 2 at (-600, -200) -> dx=400 (>=300), dy=300 (>=88)
        data = self._create_two_nodes(-1000, -500, -600, -200)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 0, f"Expected exit code 0 for negative non-overlapping, got {code}. Stdout: {stdout}")
        self.assertIn("Collisions:      0", stdout)

    def test_large_coordinates_collision_must_fail(self):
        """Overlapping nodes at very large coordinates -> MUST fail."""
        # Node 1 at (1000000, 500000), Node 2 at (1000200, 500050) -> dx=200, dy=50
        data = self._create_two_nodes(1000000, 500000, 1000200, 500050)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 1, f"Expected exit code 1 for large coords collision, got {code}")
        self.assertIn("COLLISION_ERROR", stdout)
        self.assertIn("dx=200", stdout)
        self.assertIn("dy=50", stdout)

    def test_large_coordinates_non_overlapping_must_pass(self):
        """Non-overlapping nodes at large coordinates -> MUST pass."""
        # Node 1 at (1000000, 500000), Node 2 at (1000500, 500200) -> dx=500, dy=200
        data = self._create_two_nodes(1000000, 500000, 1000500, 500200)
        code, stdout, stderr = run_check_schema(data, strict=True)
        self.assertEqual(code, 0, f"Expected exit code 0 for large non-overlapping, got {code}. Stdout: {stdout}")
        self.assertIn("Collisions:      0", stdout)

    def test_float_coordinates_boundary_precision(self):
        """dx=299.9, dy=87.9 (collision) vs dx=300.0, dy=87.9 (no collision)."""
        # Case A: dx=299.9, dy=87.9 -> collision
        data_coll = self._create_two_nodes(0, 0, 299.9, 87.9)
        code, stdout, _ = run_check_schema(data_coll, strict=True)
        self.assertEqual(code, 1)
        self.assertIn("COLLISION_ERROR", stdout)

        # Case B: dx=300.0, dy=87.9 -> no collision
        data_pass = self._create_two_nodes(0, 0, 300.0, 87.9)
        code, stdout, _ = run_check_schema(data_pass, strict=True)
        self.assertEqual(code, 0)
        self.assertIn("Collisions:      0", stdout)

        # Case C: dx=299.9, dy=88.0 -> no collision
        data_pass2 = self._create_two_nodes(0, 0, 299.9, 88.0)
        code, stdout, _ = run_check_schema(data_pass2, strict=True)
        self.assertEqual(code, 0)
        self.assertIn("Collisions:      0", stdout)

    def test_collision_in_non_strict_mode_still_fails(self):
        """Pairwise collisions must fail validation (exit 1) even without --strict."""
        data = self._create_two_nodes(0, 0, 100, 50)
        code, stdout, _ = run_check_schema(data, strict=False)
        self.assertEqual(code, 1, "Collisions must cause failure even in non-strict mode")
        self.assertIn("COLLISION_ERROR", stdout)

    def test_multi_node_pairwise_collision_count(self):
        """Three mutually colliding nodes should report exactly 3 collision pairs."""
        data = self._create_two_nodes(0, 0, 10, 10)
        third_node = copy.deepcopy(data["nodes"][1])
        third_node["id"] = "node-3"
        third_node["short_hash"] = "c3c3c3c"
        third_node["x"] = 20
        third_node["y"] = 20
        data["nodes"].append(third_node)
        data["edges"].append({
            "id": "e2-3",
            "from": "node-2",
            "to": "node-3",
            "svg_path": "M 10 10 L 20 20",
            "color": "#4a90e2"
        })
        code, stdout, _ = run_check_schema(data, strict=True)
        self.assertEqual(code, 1)
        self.assertIn("Collisions:      3", stdout)

    def test_invalid_coordinate_types_rejected(self):
        """Non-numeric coordinates (bool, str, None, inf, nan) must be rejected."""
        invalid_values = [True, False, "100", None]
        for val in invalid_values:
            data = copy.deepcopy(BASE_VALID_DATA)
            data["nodes"][0]["x"] = val
            code, stdout, _ = run_check_schema(data, strict=True)
            self.assertEqual(code, 1, f"Failed to reject invalid coord value: {val!r}")
            self.assertIn("INVALID_COORD", stdout)


class TestRelationalIntegrity(unittest.TestCase):
    """Test relational integrity edge cases under --strict mode."""


    def test_dirty_tree_without_wip_node_must_fail(self):
        """Dirty working tree (status.is_dirty=True) without WIP node -> MUST fail."""
        data = copy.deepcopy(BASE_VALID_DATA)
        data["status"]["is_dirty"] = True
        data["status"]["dirty_count"] = 3
        # No WIP node present in nodes list
        code, stdout, _ = run_check_schema(data, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for dirty tree without WIP, got {code}. Stdout: {stdout}")
        self.assertIn("INTEGRITY", stdout)
        self.assertIn("no node has 'is_wip': True", stdout)

    def test_dirty_tree_with_wip_node_but_wrong_id_must_fail(self):
        """Dirty tree with is_wip=True but id != 'active-wip' -> MUST fail."""
        data = copy.deepcopy(BASE_VALID_DATA)
        data["status"]["is_dirty"] = True
        data["status"]["dirty_count"] = 1
        wip_node = copy.deepcopy(data["nodes"][0])
        wip_node["id"] = "some-other-wip-id"
        wip_node["is_wip"] = True
        wip_node["is_head"] = False
        wip_node["x"] = 500
        wip_node["y"] = 0
        data["nodes"].append(wip_node)
        data["edges"].append({
            "id": "e-wip",
            "from": "node-1",
            "to": "some-other-wip-id",
            "svg_path": "M 0 0 L 500 0",
            "color": "#e06c75"
        })
        code, stdout, _ = run_check_schema(data, strict=True)
        self.assertEqual(code, 1)
        self.assertIn("INTEGRITY", stdout)
        self.assertIn("no active-wip node exists", stdout)

    def test_dirty_tree_with_unconnected_wip_node_must_fail(self):
        """Dirty tree with active-wip node but no connecting edge to head_commit -> MUST fail."""
        data = copy.deepcopy(BASE_VALID_DATA)
        data["status"]["is_dirty"] = True
        data["status"]["dirty_count"] = 1
        wip_node = copy.deepcopy(data["nodes"][0])
        wip_node["id"] = "active-wip"
        wip_node["is_wip"] = True
        wip_node["is_head"] = False
        wip_node["x"] = 500
        wip_node["y"] = 0
        data["nodes"].append(wip_node)
        # Omit edge from active-wip to head_commit
        code, stdout, _ = run_check_schema(data, strict=True)
        self.assertEqual(code, 1)
        self.assertIn("INTEGRITY", stdout)
        self.assertIn("no edge connects WIP node", stdout)

    def test_dirty_tree_with_proper_active_wip_must_pass(self):
        """Dirty tree with properly placed and connected active-wip node -> MUST pass."""
        data = copy.deepcopy(BASE_VALID_DATA)
        data["status"]["is_dirty"] = True
        data["status"]["dirty_count"] = 2
        wip_node = copy.deepcopy(data["nodes"][0])
        wip_node["id"] = "active-wip"
        wip_node["is_wip"] = True
        wip_node["is_head"] = False
        wip_node["x"] = 400
        wip_node["y"] = 0
        data["nodes"].append(wip_node)
        data["edges"].append({
            "id": "e-wip",
            "from": "node-1",
            "to": "active-wip",
            "svg_path": "M 0 0 L 400 0",
            "color": "#e06c75"
        })
        code, stdout, _ = run_check_schema(data, strict=True)
        self.assertEqual(code, 0, f"Expected exit 0 for valid dirty tree with WIP, got {code}. Stdout: {stdout}")
        self.assertIn("RESULT: SUCCESS", stdout)

    def test_clean_tree_with_wip_node_must_fail(self):
        """Clean tree (status.is_dirty=False) containing a node with is_wip=True -> MUST fail."""
        data = copy.deepcopy(BASE_VALID_DATA)
        data["status"]["is_dirty"] = False
        wip_node = copy.deepcopy(data["nodes"][0])
        wip_node["id"] = "active-wip"
        wip_node["is_wip"] = True
        wip_node["is_head"] = False
        wip_node["x"] = 400
        wip_node["y"] = 0
        data["nodes"].append(wip_node)
        data["edges"].append({
            "id": "e-wip",
            "from": "node-1",
            "to": "active-wip",
            "svg_path": "M 0 0 L 400 0",
            "color": "#e06c75"
        })
        code, stdout, _ = run_check_schema(data, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for clean tree with WIP, got {code}")
        self.assertIn("INTEGRITY", stdout)
        self.assertIn("Working tree is clean ('status.is_dirty': False), but graph contains WIP node(s)", stdout)

    def test_missing_head_commit_in_node_ids_must_fail(self):
        """Missing head_commit in node_ids -> MUST fail with exit code 1 under --strict."""
        data = copy.deepcopy(BASE_VALID_DATA)
        data["head_commit"] = "nonexistent-sha-999"
        code, stdout, _ = run_check_schema(data, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for missing head_commit in nodes, got {code}")
        self.assertIn("INTEGRITY", stdout)
        self.assertIn("does not exist in nodes list", stdout)

    def test_dangling_edge_endpoints_must_fail(self):
        """Dangling edge endpoints (from or to pointing to nonexistent node) -> MUST fail under --strict."""
        # Test dangling 'from'
        data_dangling_from = copy.deepcopy(BASE_VALID_DATA)
        data_dangling_from["edges"].append({
            "id": "e-broken-from",
            "from": "ghost-node",
            "to": "node-1",
            "svg_path": "M 0 0 L 100 100",
            "color": "#4a90e2"
        })
        code, stdout, _ = run_check_schema(data_dangling_from, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for dangling edge 'from', got {code}")
        self.assertIn("INTEGRITY", stdout)
        self.assertIn("'from' node 'ghost-node' does not exist in nodes list", stdout)

        # Test dangling 'to'
        data_dangling_to = copy.deepcopy(BASE_VALID_DATA)
        data_dangling_to["edges"].append({
            "id": "e-broken-to",
            "from": "node-1",
            "to": "ghost-node-dest",
            "svg_path": "M 0 0 L 100 100",
            "color": "#4a90e2"
        })
        code, stdout, _ = run_check_schema(data_dangling_to, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for dangling edge 'to', got {code}")
        self.assertIn("INTEGRITY", stdout)
        self.assertIn("'to' node 'ghost-node-dest' does not exist in nodes list", stdout)

    def test_missing_primary_branch_must_fail(self):
        """Missing or empty primary_branch -> MUST fail under --strict."""
        # Case A: Missing key
        data_missing = copy.deepcopy(BASE_VALID_DATA)
        del data_missing["primary_branch"]
        code, stdout, _ = run_check_schema(data_missing, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for missing primary_branch, got {code}")
        self.assertIn("MISSING_KEY", stdout)
        self.assertIn("primary_branch", stdout)

        # Case B: Empty string
        data_empty = copy.deepcopy(BASE_VALID_DATA)
        data_empty["primary_branch"] = ""
        code, stdout, _ = run_check_schema(data_empty, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for empty primary_branch, got {code}")
        self.assertIn("TYPE_MISMATCH", stdout)
        self.assertIn("primary_branch", stdout)

        # Case C: Non-string type
        data_non_str = copy.deepcopy(BASE_VALID_DATA)
        data_non_str["primary_branch"] = 12345
        code, stdout, _ = run_check_schema(data_non_str, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for integer primary_branch, got {code}")
        self.assertIn("TYPE_MISMATCH", stdout)

    def test_schema_version_not_2_must_fail(self):
        """Schema version != 2 (missing, v1, v3, string '2') -> MUST fail under --strict."""
        # Case A: Missing schema_version
        data_missing = copy.deepcopy(BASE_VALID_DATA)
        del data_missing["schema_version"]
        code, stdout, _ = run_check_schema(data_missing, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for missing schema_version, got {code}")
        self.assertIn("MISSING_KEY", stdout)

        # Case B: schema_version = 1
        data_v1 = copy.deepcopy(BASE_VALID_DATA)
        data_v1["schema_version"] = 1
        code, stdout, _ = run_check_schema(data_v1, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for schema_version=1, got {code}")
        self.assertIn("TYPE_MISMATCH", stdout)
        self.assertIn("schema_version", stdout)

        # Case C: schema_version = 3
        data_v3 = copy.deepcopy(BASE_VALID_DATA)
        data_v3["schema_version"] = 3
        code, stdout, _ = run_check_schema(data_v3, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for schema_version=3, got {code}")
        self.assertIn("TYPE_MISMATCH", stdout)

        # Case D: schema_version = "2" (string instead of int)
        data_str2 = copy.deepcopy(BASE_VALID_DATA)
        data_str2["schema_version"] = "2"
        code, stdout, _ = run_check_schema(data_str2, strict=True)
        self.assertEqual(code, 1, f"Expected exit 1 for schema_version='2', got {code}")
        self.assertIn("TYPE_MISMATCH", stdout)


class TestRepositoryDatasetsAndLeakGuard(unittest.TestCase):
    """Verify live repository datasets and leak guard."""

    def test_demo_data_js_under_strict(self):
        demo_path = os.path.join(REPO_ROOT, "demo_data.js")
        self.assertTrue(os.path.isfile(demo_path))
        res = subprocess.run(
            [sys.executable, CHECK_SCHEMA_PY, demo_path, "--strict"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT
        )
        self.assertEqual(res.returncode, 0, f"demo_data.js failed check_schema: {res.stdout}")
        self.assertIn("RESULT: SUCCESS", res.stdout)
        self.assertIn("Collisions:      0", res.stdout)

    def test_git_data_js_under_strict_if_exists(self):
        git_data_path = os.path.join(REPO_ROOT, "git_data.js")
        if os.path.isfile(git_data_path):
            res = subprocess.run(
                [sys.executable, CHECK_SCHEMA_PY, git_data_path, "--strict"],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT
            )
            self.assertEqual(res.returncode, 0, f"git_data.js failed check_schema: {res.stdout}")
            self.assertIn("RESULT: SUCCESS", res.stdout)
            self.assertIn("Collisions:      0", res.stdout)

    def test_verify_no_leak_script_passes(self):
        res = subprocess.run(
            [sys.executable, VERIFY_NO_LEAK_PY],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT
        )
        self.assertEqual(res.returncode, 0, f"verify_no_leak.py failed: {res.stdout}\n{res.stderr}")
        self.assertIn("[SECURITY CHECK PASSED]", res.stdout)

    def test_verify_no_leak_active_gitignore_enforcement(self):
        """Test verify_no_leak.py in a sandbox git repo without git_data.js ignored."""
        with tempfile.TemporaryDirectory() as sandbox:
            subprocess.run(["git", "init"], cwd=sandbox, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=sandbox, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=sandbox, check=True)

            # Commit an initial file without git_data.js ignored
            dummy_file = os.path.join(sandbox, "README.md")
            with open(dummy_file, "w") as f:
                f.write("# Sandbox\n")
            subprocess.run(["git", "add", "README.md"], cwd=sandbox, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=sandbox, check=True)

            # Run verify_no_leak on sandbox
            res = subprocess.run(
                [sys.executable, VERIFY_NO_LEAK_PY, sandbox],
                capture_output=True,
                text=True
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("Active .gitignore check failed", res.stderr)

    def test_verify_no_leak_staged_prohibited_artifacts(self):
        """Test verify_no_leak.py detects various staged prohibited artifacts."""
        prohibited_names = [
            "git_data.js",
            "test_output.js",
            "test_run.js",
            "test_m2_out.js",
            "git_data_dump.json",
        ]
        for name in prohibited_names:
            with tempfile.TemporaryDirectory() as sandbox:
                subprocess.run(["git", "init"], cwd=sandbox, check=True, capture_output=True)
                subprocess.run(["git", "config", "user.name", "Test"], cwd=sandbox, check=True)
                subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=sandbox, check=True)

                # Add .gitignore with git_data.js to satisfy rule 1
                with open(os.path.join(sandbox, ".gitignore"), "w") as f:
                    f.write("git_data.js\n")
                subprocess.run(["git", "add", ".gitignore"], cwd=sandbox, check=True)
                subprocess.run(["git", "commit", "-m", "add gitignore"], cwd=sandbox, check=True)

                # Force stage a prohibited artifact
                target = os.path.join(sandbox, name)
                with open(target, "w") as f:
                    f.write("// confidential data\n")
                subprocess.run(["git", "add", "-f", name], cwd=sandbox, check=True)

                res = subprocess.run(
                    [sys.executable, VERIFY_NO_LEAK_PY, sandbox],
                    capture_output=True,
                    text=True
                )
                self.assertEqual(res.returncode, 1, f"Expected verify_no_leak to fail on staged {name}")
                self.assertIn("SECURITY VIOLATION", res.stderr)

    def test_verify_no_leak_committed_prohibited_artifact(self):
        """Test verify_no_leak.py detects prohibited artifacts in recent commit history."""
        with tempfile.TemporaryDirectory() as sandbox:
            subprocess.run(["git", "init"], cwd=sandbox, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=sandbox, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=sandbox, check=True)

            with open(os.path.join(sandbox, ".gitignore"), "w") as f:
                f.write("git_data.js\n")
            subprocess.run(["git", "add", ".gitignore"], cwd=sandbox, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=sandbox, check=True)

            # Commit a prohibited file with -f
            with open(os.path.join(sandbox, "test_output.js"), "w") as f:
                f.write("test leak\n")
            subprocess.run(["git", "add", "-f", "test_output.js"], cwd=sandbox, check=True)
            subprocess.run(["git", "commit", "-m", "leak commit"], cwd=sandbox, check=True)

            res = subprocess.run(
                [sys.executable, VERIFY_NO_LEAK_PY, sandbox],
                capture_output=True,
                text=True
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("SECURITY VIOLATION", res.stderr)
            self.assertIn("was committed in recent commit", res.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

