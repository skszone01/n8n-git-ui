#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification suite for Schema v2 & DAG generation robustness (Refactored)

Milestone M4 / Feature F17:
- Standard unittest.TestCase architecture discoverable via `python -m unittest discover tests`.
- Completely isolated Git operations using tempfile.TemporaryDirectory(); never modifies,
  stages, or creates files in the project working tree.
- Pairwise node collision freedom checks (|a.x - b.x| < 300 and |a.y - b.y| < 88).
- Strict schema validation using tools.check_schema (validate_schema and CLI --strict).
- Full coverage of clean working tree, dirty working tree (staged, unstaged, combined),
  and --max-count / -n flag semantics.
- Backward-compatible validation of demo_data.js and atomic file replacement.
"""

import os
import sys
import json
import subprocess
import tempfile
import unittest
from typing import Dict, Any, List, Tuple, Optional

# Dynamic discovery of project root (supports running from tests/ or agent subfolder)
_current_dir = os.path.abspath(os.path.dirname(__file__))
if os.path.exists(os.path.join(_current_dir, "..", "generate_dag.py")):
    PROJECT_ROOT = os.path.abspath(os.path.join(_current_dir, ".."))
elif os.path.exists(os.path.join(_current_dir, "..", "..", "..", "generate_dag.py")):
    PROJECT_ROOT = os.path.abspath(os.path.join(_current_dir, "..", "..", ".."))
else:
    PROJECT_ROOT = os.path.abspath(os.getcwd())

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.check_schema import validate_schema, parse_git_dag_js

GENERATE_DAG_SCRIPT = os.path.join(PROJECT_ROOT, "generate_dag.py")
CHECK_SCHEMA_SCRIPT = os.path.join(PROJECT_ROOT, "tools", "check_schema.py")
DEMO_DATA_JS = os.path.join(PROJECT_ROOT, "demo_data.js")

NODE_WIDTH = 300
NODE_HEIGHT = 88
JS_HEADER_PREFIX = "/* Auto-generated Git DAG Data */\nwindow.GIT_DAG_DATA = "

REQUIRED_NODE_KEYS = [
    "id", "hash", "short_id", "short_hash", "title", "subject",
    "author", "author_full", "date", "branches", "tags",
    "parents", "lane", "lane_name", "lane_color",
    "x", "y", "width", "height", "status", "is_head", "is_merge", "is_wip"
]


class BaseGitTempRepoTestCase(unittest.TestCase):
    """Base test fixture providing isolated temporary git repository lifecycle and assertions."""

    def setUp(self):
        try:
            self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            self._td = tempfile.TemporaryDirectory()
        self.repo_dir = os.path.abspath(self._td.name)

        # Isolated git author & committer environment
        self.git_env = os.environ.copy()
        self.git_env.update({
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "test.author@example.com",
            "GIT_COMMITTER_NAME": "Test Committer",
            "GIT_COMMITTER_EMAIL": "test.committer@example.com"
        })

    def tearDown(self):
        self._td.cleanup()

    def run_git(self, args: List[str], cwd: Optional[str] = None) -> str:
        """Execute a git command within the isolated repository."""
        target_dir = cwd or self.repo_dir
        res = subprocess.run(
            ["git"] + args,
            cwd=target_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.git_env
        )
        self.assertEqual(
            res.returncode, 0,
            f"git {' '.join(args)} failed in {target_dir}:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        )
        return res.stdout.strip()

    def init_repo(self, default_branch: str = "main") -> None:
        """Initialize an empty git repository with the given default branch name."""
        try:
            self.run_git(["init", "-b", default_branch])
        except AssertionError:
            self.run_git(["init"])
            self.run_git(["checkout", "-b", default_branch])

    def commit_file(self, filename: str, content: str, message: str) -> str:
        """Create or update a file, stage it, and commit it."""
        file_path = os.path.join(self.repo_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        self.run_git(["add", filename])
        self.run_git(["commit", "-m", message])
        commit_hash = self.run_git(["rev-parse", "HEAD"])
        return commit_hash

    def run_dag_generator(
        self,
        extra_args: Optional[List[str]] = None,
        output_filename: str = "test_output.js"
    ) -> Tuple[Dict[str, Any], str, str]:
        """
        Run generate_dag.py targeting self.repo_dir and writing to a temp output file.
        Returns: (parsed_data, raw_content, output_filepath)
        """
        out_path = os.path.join(self.repo_dir, output_filename)
        cmd = [sys.executable, GENERATE_DAG_SCRIPT, self.repo_dir, "-o", out_path]
        if extra_args:
            cmd.extend(extra_args)

        res = subprocess.run(
            cmd,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(
            res.returncode, 0,
            f"generate_dag.py execution failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        )
        self.assertTrue(os.path.exists(out_path), f"Output file was not created: {out_path}")

        # Atomic cleanup verification: ensure no lingering .tmp files
        tmp_pattern = out_path + ".tmp"
        self.assertFalse(os.path.exists(tmp_pattern), f"Residual temporary file found: {tmp_pattern}")
        for fname in os.listdir(self.repo_dir):
            if fname.startswith(".tmp-") and fname.endswith(".tmp"):
                self.fail(f"Residual atomic temp file detected: {fname}")

        with open(out_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        self.assertTrue(
            raw_content.startswith(JS_HEADER_PREFIX),
            f"Output file does not begin with expected JS header prefix:\n{raw_content[:200]}"
        )

        data, parse_err = parse_git_dag_js(out_path)
        self.assertIsNone(parse_err, f"Failed to parse generated JS payload: {parse_err}")
        self.assertIsInstance(data, dict, "Parsed payload must be a JSON dictionary")
        return data, raw_content, out_path

    def assert_no_pairwise_collisions(self, nodes: List[Dict[str, Any]]) -> None:
        """
        Verify that all node bounding boxes (width=300, height=88) have 0 pairwise overlaps.
        Formula: not (abs(a.x - b.x) < 300 and abs(a.y - b.y) < 88)
        """
        n = len(nodes)
        collisions = []
        for i in range(n):
            a = nodes[i]
            ax, ay = a.get("x", 0), a.get("y", 0)
            aid = a.get("id", f"node-{i}")
            for j in range(i + 1, n):
                b = nodes[j]
                bx, by = b.get("x", 0), b.get("y", 0)
                bid = b.get("id", f"node-{j}")

                dx = abs(ax - bx)
                dy = abs(ay - by)
                if dx < NODE_WIDTH and dy < NODE_HEIGHT:
                    collisions.append({
                        "node_a": aid,
                        "node_b": bid,
                        "a_pos": (ax, ay),
                        "b_pos": (bx, by),
                        "dx": dx,
                        "dy": dy
                    })

        self.assertEqual(
            len(collisions), 0,
            f"Detected {len(collisions)} pairwise node bounding box collisions:\n" +
            "\n".join(f"  Collision: {c['node_a']} vs {c['node_b']} (dx={c['dx']}, dy={c['dy']})" for c in collisions)
        )

    def assert_strict_schema_compliance(self, data: Dict[str, Any], file_path: str) -> None:
        """Validate payload using tools.check_schema in both Python library and CLI mode."""
        # 1. In-process validation
        report = validate_schema(data, file_path, strict=True)
        err_msg = "\n".join(str(e) for e in report.errors)
        self.assertTrue(
            report.is_valid,
            f"Strict schema validation failed with {len(report.errors)} errors:\n{err_msg}"
        )
        self.assertEqual(report.collision_count, 0, f"Validator reported collisions: {report.collision_count}")

        # 2. CLI subprocess validation
        cli_cmd = [sys.executable, CHECK_SCHEMA_SCRIPT, file_path, "--strict"]
        cli_res = subprocess.run(
            cli_cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(
            cli_res.returncode, 0,
            f"CLI check_schema.py --strict failed on {file_path}:\nSTDOUT: {cli_res.stdout}\nSTDERR: {cli_res.stderr}"
        )

    def assert_node_schema_v2(self, node: Dict[str, Any]) -> None:
        """Comprehensive verification of Schema v2 required node keys and semantics."""
        for key in REQUIRED_NODE_KEYS:
            self.assertIn(key, node, f"Missing required Schema v2 key '{key}' in node {node.get('id')}")

        self.assertEqual(node["width"], NODE_WIDTH, "Node width must be 300")
        self.assertEqual(node["height"], NODE_HEIGHT, "Node height must be 88")
        self.assertIsInstance(node["x"], (int, float), "Node x coordinate must be numeric")
        self.assertIsInstance(node["y"], (int, float), "Node y coordinate must be numeric")
        self.assertIsInstance(node["lane"], int, "Node lane must be an integer")
        self.assertIsInstance(node["branches"], list, "Node branches must be a list")
        self.assertIsInstance(node["tags"], list, "Node tags must be a list")
        self.assertIsInstance(node["parents"], list, "Node parents must be a list")

        if node["is_wip"]:
            self.assertEqual(node["id"], "active-wip", "WIP node id must be 'active-wip'")
            self.assertEqual(node["short_id"], "WIP", "WIP short_id must be 'WIP'")
            self.assertEqual(node["short_hash"], "WIP", "WIP short_hash must be 'WIP'")
            self.assertEqual(node["author"], "Local Working Directory")
            self.assertEqual(node["author_full"], "Local Working Tree <uncommitted>")
            self.assertTrue(node["title"].startswith("Working Tree ("), f"Unexpected WIP title: {node['title']}")
            self.assertFalse(node["is_head"], "WIP node must have is_head: False")
            self.assertFalse(node["is_merge"], "WIP node must have is_merge: False")
            self.assertEqual(node["status"], "wip", "WIP node status must be 'wip'")
        else:
            self.assertFalse(node["is_wip"], "Commit node must have is_wip: False")
            self.assertEqual(node["short_id"], node["short_hash"], "Commit node short_id must equal short_hash")
            self.assertEqual(node["title"], node["subject"], "Commit node title must equal subject")
            self.assertIn("<", node["author_full"], f"author_full should contain email: {node['author_full']}")


class TestCleanRepository(BaseGitTempRepoTestCase):
    """Test suite verifying DAG generation and Schema v2 compliance on a clean git working tree."""

    def test_clean_single_commit(self):
        """Single commit on main branch with a clean working tree."""
        self.init_repo(default_branch="main")
        root_hash = self.commit_file("README.md", "# Project\n", "Initial root commit")

        data, raw_content, out_path = self.run_dag_generator()

        # Top-level assertions
        self.assertEqual(data.get("schema_version"), 2)
        self.assertEqual(data.get("primary_branch"), "main")
        self.assertEqual(data.get("head_branch"), "main")
        self.assertEqual(data.get("head_commit"), root_hash)
        self.assertFalse(data["status"]["is_dirty"], "Clean repo must report is_dirty: False")
        self.assertEqual(data["status"]["dirty_count"], 0)

        # Nodes assertions
        nodes = data.get("nodes", [])
        self.assertEqual(len(nodes), 1, "Expected exactly 1 commit node")
        commit_node = nodes[0]
        self.assert_node_schema_v2(commit_node)
        self.assertTrue(commit_node["is_head"], "Single commit node must be marked is_head: True")
        self.assertEqual(commit_node["lane"], 0, "Trunk commit should be in Lane 0")
        self.assertEqual(commit_node["hash"], root_hash)

        # No WIP nodes
        self.assertFalse(any(n["is_wip"] for n in nodes), "Clean repo must not contain any WIP nodes")

        # Collision freedom and schema validation
        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)

    def test_clean_multi_commit_linear_history(self):
        """Linear chain of 4 commits on main branch."""
        self.init_repo(default_branch="main")
        hashes = []
        for i in range(4):
            h = self.commit_file(f"file_{i}.txt", f"Content {i}\n", f"Commit message {i}")
            hashes.append(h)

        data, raw_content, out_path = self.run_dag_generator()

        self.assertEqual(data.get("schema_version"), 2)
        self.assertFalse(data["status"]["is_dirty"])
        nodes = data.get("nodes", [])
        self.assertEqual(len(nodes), 4, "Expected exactly 4 commit nodes")

        for node in nodes:
            self.assert_node_schema_v2(node)
            self.assertEqual(node["lane"], 0, "All linear commits should be in trunk lane 0")

        # Head commit verification
        head_nodes = [n for n in nodes if n["is_head"]]
        self.assertEqual(len(head_nodes), 1)
        self.assertEqual(head_nodes[0]["hash"], hashes[-1])

        # Topological X-axis monotonicity check (parents have smaller X than children)
        hash_to_node = {n["hash"]: n for n in nodes}
        for node in nodes:
            for p_hash in node["parents"]:
                if p_hash in hash_to_node:
                    self.assertLess(
                        hash_to_node[p_hash]["x"],
                        node["x"],
                        f"Parent commit {p_hash} must appear before child commit {node['hash']} on X-axis"
                    )

        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)

    def test_clean_feature_branch_topology(self):
        """Clean repository with main trunk and a branched feature."""
        self.init_repo(default_branch="main")
        c1 = self.commit_file("main1.txt", "1", "Main commit 1")
        c2 = self.commit_file("main2.txt", "2", "Main commit 2")

        # Fork feature branch
        self.run_git(["checkout", "-b", "feature/alpha"])
        c_feat = self.commit_file("feat.txt", "feat", "Feature commit on alpha")

        # Advance main
        self.run_git(["checkout", "main"])
        c3 = self.commit_file("main3.txt", "3", "Main commit 3")

        data, raw_content, out_path = self.run_dag_generator()
        nodes = data.get("nodes", [])
        self.assertEqual(len(nodes), 4, "Expected 4 total commit nodes")

        for node in nodes:
            self.assert_node_schema_v2(node)

        # Check lane allocation: feature branch commit should be in a non-zero lane
        feat_node = next(n for n in nodes if n["hash"] == c_feat)
        self.assertNotEqual(feat_node["lane"], 0, "Feature branch commit should not be on trunk lane 0")

        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)


class TestDirtyRepository(BaseGitTempRepoTestCase):
    """Test suite verifying WIP node generation and Schema v2 compliance on dirty working trees."""

    def test_dirty_staged_changes(self):
        """Working tree with staged (indexed) uncommitted changes."""
        self.init_repo(default_branch="main")
        root_hash = self.commit_file("base.txt", "base", "Base commit")

        # Add a new staged file
        staged_file = os.path.join(self.repo_dir, "staged_new.txt")
        with open(staged_file, "w", encoding="utf-8") as f:
            f.write("staged content")
        self.run_git(["add", "staged_new.txt"])

        data, raw_content, out_path = self.run_dag_generator()

        self.assertTrue(data["status"]["is_dirty"], "Status must report is_dirty: True")
        self.assertGreaterEqual(data["status"]["dirty_count"], 1)

        nodes = data.get("nodes", [])
        self.assertEqual(len(nodes), 2, "Expected 1 commit node + 1 WIP node")

        # Verify active-wip node
        wip_nodes = [n for n in nodes if n["is_wip"]]
        self.assertEqual(len(wip_nodes), 1, "Must contain exactly 1 WIP node")
        wip_node = wip_nodes[0]
        self.assert_node_schema_v2(wip_node)
        self.assertEqual(wip_node["id"], "active-wip")
        self.assertFalse(wip_node["is_head"])
        self.assertEqual(wip_node["parents"], [root_hash])

        # Verify WIP node position is to the right of HEAD
        commit_node = next(n for n in nodes if not n["is_wip"])
        self.assertGreater(wip_node["x"], commit_node["x"], "WIP node X must be greater than HEAD X")

        # Verify connecting edge between head and WIP
        edges = data.get("edges", [])
        wip_edges = [
            e for e in edges
            if (e.get("from") == root_hash and e.get("to") == "active-wip") or
               (e.get("from") == "active-wip" and e.get("to") == root_hash)
        ]
        self.assertEqual(len(wip_edges), 1, "Must have an edge connecting head commit to active-wip")

        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)

    def test_dirty_unstaged_modification(self):
        """Working tree with unstaged modifications to a tracked file."""
        self.init_repo(default_branch="main")
        root_hash = self.commit_file("tracked.txt", "initial\n", "Initial commit")

        # Modify tracked file without git add
        with open(os.path.join(self.repo_dir, "tracked.txt"), "a", encoding="utf-8") as f:
            f.write("unstaged modification line\n")

        data, raw_content, out_path = self.run_dag_generator()

        self.assertTrue(data["status"]["is_dirty"])
        nodes = data.get("nodes", [])
        self.assertEqual(len(nodes), 2)

        wip_node = next(n for n in nodes if n["is_wip"])
        self.assert_node_schema_v2(wip_node)

        # Verify diff payload exists for active-wip
        diffs = data.get("diffs", {})
        self.assertIn("active-wip", diffs, "Diffs dictionary must have 'active-wip' entry")
        self.assertTrue(any(f["path"] == "tracked.txt" for f in diffs["active-wip"].get("files", [])))

        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)

    def test_dirty_untracked_files(self):
        """Working tree containing newly created untracked files."""
        self.init_repo(default_branch="main")
        self.commit_file("init.txt", "init", "Initial commit")

        # Create an untracked file
        with open(os.path.join(self.repo_dir, "untracked.py"), "w", encoding="utf-8") as f:
            f.write("# untracked script\n")

        data, raw_content, out_path = self.run_dag_generator()

        self.assertTrue(data["status"]["is_dirty"])
        nodes = data.get("nodes", [])
        self.assertTrue(any(n["is_wip"] for n in nodes))

        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)

    def test_dirty_staged_and_unstaged_combined(self):
        """Working tree containing both staged and unstaged modifications simultaneously."""
        self.init_repo(default_branch="main")
        self.commit_file("file_a.txt", "A\n", "Add A")
        self.commit_file("file_b.txt", "B\n", "Add B")

        # Staged change
        with open(os.path.join(self.repo_dir, "file_a.txt"), "w", encoding="utf-8") as f:
            f.write("A modified staged\n")
        self.run_git(["add", "file_a.txt"])

        # Unstaged modification
        with open(os.path.join(self.repo_dir, "file_b.txt"), "w", encoding="utf-8") as f:
            f.write("B modified unstaged\n")

        # Untracked file
        with open(os.path.join(self.repo_dir, "untracked.txt"), "w", encoding="utf-8") as f:
            f.write("untracked\n")

        data, raw_content, out_path = self.run_dag_generator()

        self.assertTrue(data["status"]["is_dirty"])
        self.assertGreaterEqual(data["status"]["dirty_count"], 3)
        nodes = data.get("nodes", [])

        wip_node = next(n for n in nodes if n["is_wip"])
        self.assert_node_schema_v2(wip_node)
        self.assertIn("uncommitted changes", wip_node["title"])

        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)


class TestMaxCountFlag(BaseGitTempRepoTestCase):
    """Test suite verifying commit limiting behavior (-n / --max-count)."""

    def setUp(self):
        super().setUp()
        self.init_repo(default_branch="main")
        self.commit_hashes = []
        for i in range(5):
            h = self.commit_file(f"file_{i}.txt", f"data {i}\n", f"Sequential commit {i}")
            self.commit_hashes.append(h)

    def test_max_count_short_flag(self):
        """Test `-n 2` limits output to the 2 most recent commits."""
        data, _, out_path = self.run_dag_generator(extra_args=["-n", "2"])
        commit_nodes = [n for n in data.get("nodes", []) if not n["is_wip"]]
        self.assertEqual(len(commit_nodes), 2, f"Expected 2 commit nodes with -n 2, got {len(commit_nodes)}")

        expected_shas = {self.commit_hashes[-1], self.commit_hashes[-2]}
        actual_shas = {n["hash"] for n in commit_nodes}
        self.assertEqual(actual_shas, expected_shas, "Nodes should match the 2 most recent commits")

        self.assert_no_pairwise_collisions(data["nodes"])
        self.assert_strict_schema_compliance(data, out_path)

    def test_max_count_long_flag(self):
        """Test `--max-count 3` limits output to 3 commits."""
        data, _, out_path = self.run_dag_generator(extra_args=["--max-count", "3"])
        commit_nodes = [n for n in data.get("nodes", []) if not n["is_wip"]]
        self.assertEqual(len(commit_nodes), 3, f"Expected 3 commit nodes with --max-count 3, got {len(commit_nodes)}")

        self.assert_no_pairwise_collisions(data["nodes"])
        self.assert_strict_schema_compliance(data, out_path)

    def test_max_count_with_dirty_wip(self):
        """Test `-n 2` on a dirty working tree includes 2 commits PLUS the WIP node."""
        with open(os.path.join(self.repo_dir, "dirty.txt"), "w", encoding="utf-8") as f:
            f.write("dirty working tree")

        data, _, out_path = self.run_dag_generator(extra_args=["-n", "2"])
        nodes = data.get("nodes", [])

        commit_nodes = [n for n in nodes if not n["is_wip"]]
        wip_nodes = [n for n in nodes if n["is_wip"]]

        self.assertEqual(len(commit_nodes), 2, "Expected 2 commit nodes")
        self.assertEqual(len(wip_nodes), 1, "Expected 1 WIP node")
        self.assertEqual(len(nodes), 3, "Expected 3 total nodes (2 commits + 1 WIP)")

        self.assert_no_pairwise_collisions(nodes)
        self.assert_strict_schema_compliance(data, out_path)


class TestStaticDemoDataAndAtomicWrite(unittest.TestCase):
    """Test suite verifying demo_data.js compliance and atomic file writing semantics."""

    def test_demo_data_compliance(self):
        """Ensure demo_data.js is strictly Schema v2 compliant and collision-free."""
        self.assertTrue(os.path.exists(DEMO_DATA_JS), f"demo_data.js not found at {DEMO_DATA_JS}")
        data, err = parse_git_dag_js(DEMO_DATA_JS)
        self.assertIsNone(err, f"Failed to parse demo_data.js: {err}")
        self.assertIsInstance(data, dict)

        report = validate_schema(data, DEMO_DATA_JS, strict=True)
        self.assertTrue(
            report.is_valid,
            f"demo_data.js failed strict schema validation:\n" + "\n".join(str(e) for e in report.errors)
        )
        self.assertEqual(report.collision_count, 0, "demo_data.js has node collisions")

    def test_atomic_tempfile_cleanup(self):
        """Verify that temporary files during atomic write never leak into target directory."""
        try:
            td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            td = tempfile.TemporaryDirectory()

        try:
            target_out = os.path.join(td.name, "subdir", "generated.js")
            # Invoke generate_dag on a mock clean git repo
            git_env = os.environ.copy()
            git_env.update({
                "GIT_AUTHOR_NAME": "Author",
                "GIT_AUTHOR_EMAIL": "a@ex.com",
                "GIT_COMMITTER_NAME": "Committer",
                "GIT_COMMITTER_EMAIL": "c@ex.com"
            })
            subprocess.run(["git", "init", "-b", "main"], cwd=td.name, check=True, env=git_env)
            with open(os.path.join(td.name, "init.txt"), "w") as f:
                f.write("init")
            subprocess.run(["git", "add", "init.txt"], cwd=td.name, check=True, env=git_env)
            subprocess.run(["git", "commit", "-m", "init"], cwd=td.name, check=True, env=git_env)

            cmd = [sys.executable, GENERATE_DAG_SCRIPT, td.name, "-o", target_out]
            res = subprocess.run(cmd, cwd=td.name, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertTrue(os.path.exists(target_out))

            out_dir = os.path.dirname(target_out)
            files = os.listdir(out_dir)
            self.assertIn("generated.js", files)
            for f in files:
                self.assertFalse(f.endswith(".tmp"), f"Uncleaned temporary file found: {f}")
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
