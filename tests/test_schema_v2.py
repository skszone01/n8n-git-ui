#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification suite for Schema v2 & DAG generation robustness
"""

import os
import json
import subprocess
import sys

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def test_generation():
    test_output_js = os.path.join(REPO_DIR, "test_output.js")
    try:
        # 1. Test generate_dag.py execution with custom output
        cmd = [sys.executable, "generate_dag.py", REPO_DIR, "-o", test_output_js]
        res = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 0, f"generate_dag.py failed:\n{res.stderr}"

        # 2. Check test output existence and lack of leftover .tmp
        tmp_path = test_output_js + ".tmp"
        assert os.path.exists(test_output_js), "test_output.js was not created"
        assert not os.path.exists(tmp_path), "temporary file test_output.js.tmp was not cleaned up"

        # 3. Read and parse bundle
        with open(test_output_js, "r", encoding="utf-8") as f:
            content = f.read()

        prefix = "/* Auto-generated Git DAG Data */\nwindow.GIT_DAG_DATA = "
        assert content.startswith(prefix), "Invalid prefix header in git_data.js"
        json_str = content[len(prefix):].rstrip(";\n ")
        bundle = json.loads(json_str)

        # 4. Verify top-level bundle schema v2
        assert bundle.get("schema_version") == 2, f"Expected schema_version 2, got {bundle.get('schema_version')}"
        assert "primary_branch" in bundle, "Missing primary_branch in top-level bundle"
        assert bundle["primary_branch"] in ["main", "master"], f"Unexpected primary_branch: {bundle['primary_branch']}"

        # 5. Verify nodes schema
        nodes = bundle.get("nodes", [])
        assert len(nodes) > 0, "No nodes generated"

        has_commit = False
        has_wip = False

        for node in nodes:
            # Common required keys (both old and new)
            for key in ["id", "hash", "short_id", "short_hash", "title", "subject",
                        "author", "author_full", "date", "branches", "tags",
                        "parents", "lane", "lane_name", "lane_color",
                        "x", "y", "width", "height", "status", "is_head", "is_merge", "is_wip"]:
                assert key in node, f"Missing key '{key}' in node {node.get('id')}"

            if node["is_wip"]:
                has_wip = True
                assert node["short_id"] == "WIP"
                assert node["short_hash"] == "WIP"
                assert node["author"] == "Local Working Directory"
                assert node["author_full"] == "Local Working Tree <uncommitted>"
                assert node["title"].startswith("Working Tree (")
                assert node["is_head"] is False
                assert node["is_merge"] is False
                assert node["status"] == "wip"
            else:
                has_commit = True
                assert node["is_wip"] is False
                assert node["short_id"] == node["short_hash"]
                assert node["title"] == node["subject"]
                assert "<" in node["author_full"], f"author_full should include email, got {node['author_full']}"

        assert has_commit, "No regular commit nodes found"
        print(f"Verified {len(nodes)} nodes (has_wip={has_wip}). All schema v2 assertions PASSED!")

        # 6. Test --max-count / -n
        cmd_n = [sys.executable, "generate_dag.py", REPO_DIR, "-n", "2", "-o", test_output_js]
        res_n = subprocess.run(cmd_n, cwd=REPO_DIR, capture_output=True, text=True, encoding="utf-8")
        assert res_n.returncode == 0, f"generate_dag.py -n 2 failed:\n{res_n.stderr}"

        with open(test_output_js, "r", encoding="utf-8") as f:
            bundle_n = json.loads(f.read()[len(prefix):].rstrip(";\n "))

        commit_nodes_n = [n for n in bundle_n["nodes"] if not n["is_wip"]]
        assert len(commit_nodes_n) == 2, f"Expected 2 commit nodes with -n 2, got {len(commit_nodes_n)}"
        print(f"Verified --max-count: got exactly {len(commit_nodes_n)} commit nodes.")
    finally:
        if os.path.exists(test_output_js):
            os.remove(test_output_js)

if __name__ == "__main__":
    test_generation()
    print("ALL TESTS PASSED SUCCESSFULLY!")
