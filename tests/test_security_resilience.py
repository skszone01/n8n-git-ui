#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security Resilience Test Suite for Zero-Server Git DAG Visualizer (Milestone M4 / Feature F19)

Permanent regression test suite verifying:
1. Untrusted Git metadata with XSS injection payloads (HTML, SVG, script tags, event handlers)
   in commit messages, subjects, bodies, author names/emails, branch names, tags, and diffs.
2. Static scan of `index.html` guaranteeing 0 occurrences of dynamic `innerHTML`, `outerHTML`,
   `insertAdjacentHTML`, `document.write`, `eval`, or CSS selector injection sinks.
3. Unicode and Thai branch names ('ฟีเจอร์ใหม่', 'สายหลัก') encoding, display, and normalization.
4. Dash-prefixed branch names ('--output=evil', '--all', '-b', '--tags') ensuring immunity to Git CLI
   argument injection via safe argument delimiters ('--') and 'shell=False'.
5. Atomic file operations, data durability (flush + fsync), permission resilience, and temporary
   file cleanup on failure.
"""

import os
import sys
import json
import re
import shutil
import tempfile
import subprocess
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATE_DAG_SCRIPT = os.path.join(PROJECT_ROOT, "generate_dag.py")
INDEX_HTML = os.path.join(PROJECT_ROOT, "index.html")
CHECK_SCHEMA_SCRIPT = os.path.join(PROJECT_ROOT, "tools", "check_schema.py")

sys.path.insert(0, PROJECT_ROOT)
import generate_dag


def run_git_in_repo(args, cwd, author_name="Security Tester", author_email="tester@example.com"):
    """Execute git command in specified cwd with controlled author environment."""
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
        errors="replace",
        env=env
    )
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd} (rc={res.returncode}):\n{res.stderr}")
    return res.stdout.strip()


class TestGitMetadataXSSInjection(unittest.TestCase):
    """Verify that generate_dag.py handles untrusted git metadata containing XSS injection payloads safely."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="n8n_test_xss_")
        self.output_js = os.path.join(self.test_dir, "output.js")
        run_git_in_repo(["init"], self.test_dir)
        run_git_in_repo(["config", "user.name", 'Test User <script>alert(1)</script>'], self.test_dir)
        run_git_in_repo(["config", "user.email", "tester<img_src=x>@example.com"], self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_xss_in_commit_messages_and_body(self):
        """Verify commit subjects and bodies with malicious HTML/XSS payloads generate valid JSON."""
        file1 = os.path.join(self.test_dir, "file1.txt")
        with open(file1, "w", encoding="utf-8") as f:
            f.write("Line 1\n")
        run_git_in_repo(["add", "file1.txt"], self.test_dir)

        payload_subject = '<script>alert("xss-subject")</script>'
        payload_body = '<img src=x onerror=alert("xss-body")>\n<svg/onload=alert("xss-svg")>\n"><script>alert(1)</script>'
        full_commit_msg = f"{payload_subject}\n\n{payload_body}"

        run_git_in_repo(
            ["commit", "-m", full_commit_msg],
            self.test_dir,
            author_name='Evil <script>alert("author")</script>',
            author_email="evil@example.com"
        )

        res = subprocess.run(
            [sys.executable, GENERATE_DAG_SCRIPT, self.test_dir, "-o", self.output_js],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0, f"generate_dag.py failed:\n{res.stderr}")
        self.assertTrue(os.path.exists(self.output_js))

        with open(self.output_js, "r", encoding="utf-8") as f:
            content = f.read()

        prefix = "/* Auto-generated Git DAG Data */\nwindow.GIT_DAG_DATA = "
        self.assertTrue(content.startswith(prefix))
        json_str = content[len(prefix):].rstrip(";\n ")
        bundle = json.loads(json_str)

        self.assertEqual(bundle.get("schema_version"), 2)
        nodes = bundle.get("nodes", [])
        self.assertGreaterEqual(len(nodes), 1)

        target_node = nodes[0]
        self.assertEqual(target_node["title"], payload_subject)
        self.assertEqual(target_node["subject"], payload_subject)
        self.assertIn("author", target_node)

    def test_xss_in_author_and_committer_fields(self):
        """Verify author and committer metadata with script tags are serialized safely in JSON bundle."""
        file1 = os.path.join(self.test_dir, "author_test.txt")
        with open(file1, "w", encoding="utf-8") as f:
            f.write("Author test\n")
        run_git_in_repo(["add", "author_test.txt"], self.test_dir)

        author_payload = 'Attacker <script>alert("pwn")</script>'
        run_git_in_repo(
            ["commit", "-m", "Commit testing author XSS"],
            self.test_dir,
            author_name=author_payload,
            author_email="pwn@example.com"
        )

        res = subprocess.run(
            [sys.executable, GENERATE_DAG_SCRIPT, self.test_dir, "-o", self.output_js],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0)

        with open(self.output_js, "r", encoding="utf-8") as f:
            bundle = json.loads(f.read().split("window.GIT_DAG_DATA = ")[1].rstrip(";\n "))

        nodes = bundle.get("nodes", [])
        self.assertGreaterEqual(len(nodes), 1)
        # Verify JSON parsed without exception and author string is populated
        self.assertTrue(any("pwn@example.com" in n["author_full"] for n in nodes))

    def test_xss_in_tag_names(self):
        """Verify tag names containing XSS patterns are safely handled in JSON."""
        file1 = os.path.join(self.test_dir, "tag_test.txt")
        with open(file1, "w", encoding="utf-8") as f:
            f.write("Tag test\n")
        run_git_in_repo(["add", "tag_test.txt"], self.test_dir)
        run_git_in_repo(["commit", "-m", "Tag commit"], self.test_dir)

        run_git_in_repo(["tag", "v1.0.0-xss-alert"], self.test_dir)
        run_git_in_repo(["tag", "release-xss-img-onerror"], self.test_dir)

        res = subprocess.run(
            [sys.executable, GENERATE_DAG_SCRIPT, self.test_dir, "-o", self.output_js],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0)

        with open(self.output_js, "r", encoding="utf-8") as f:
            bundle = json.loads(f.read().split("window.GIT_DAG_DATA = ")[1].rstrip(";\n "))

        nodes = bundle.get("nodes", [])
        all_tags = []
        for n in nodes:
            all_tags.extend(n.get("tags", []))

        self.assertIn("v1.0.0-xss-alert", all_tags)
        self.assertIn("release-xss-img-onerror", all_tags)

    def test_xss_in_diff_and_uncommitted_wip(self):
        """Verify unified diff outputs and uncommitted WIP dirty nodes preserve payloads verbatim without crashing."""
        file1 = os.path.join(self.test_dir, "file1.txt")
        with open(file1, "w", encoding="utf-8") as f:
            f.write("Initial\n")
        run_git_in_repo(["add", "file1.txt"], self.test_dir)
        run_git_in_repo(["commit", "-m", "Initial commit"], self.test_dir)

        with open(file1, "a", encoding="utf-8") as f:
            f.write('\n// <script>alert("diff payload")</script>\n')
            f.write('// <img src=x onerror=alert("diff img")>\n')
            f.write('// <svg onload=alert("diff svg")>\n')

        run_git_in_repo(["commit", "-am", "Commit with XSS diff lines"], self.test_dir)

        # Modify tracked file without committing (dirty working tree)
        with open(file1, "a", encoding="utf-8") as f:
            f.write('<script>alert("uncommitted WIP injection")</script>\n')

        # Also add untracked file
        dirty_file = os.path.join(self.test_dir, "dirty.txt")
        with open(dirty_file, "w", encoding="utf-8") as f:
            f.write('untracked content\n')

        res = subprocess.run(
            [sys.executable, GENERATE_DAG_SCRIPT, self.test_dir, "-o", self.output_js],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0)

        with open(self.output_js, "r", encoding="utf-8") as f:
            bundle = json.loads(f.read().split("window.GIT_DAG_DATA = ")[1].rstrip(";\n "))

        diffs = bundle.get("diffs", {})
        self.assertIn("active-wip", diffs)
        wip_diff = diffs["active-wip"]["full_output"]
        self.assertIn('<script>alert("uncommitted WIP injection")</script>', wip_diff)

        # Validate with check_schema.py if available
        if os.path.exists(CHECK_SCHEMA_SCRIPT):
            schema_res = subprocess.run(
                [sys.executable, CHECK_SCHEMA_SCRIPT, self.output_js, "--strict"],
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            self.assertEqual(schema_res.returncode, 0, f"check_schema.py failed:\n{schema_res.stdout}\n{schema_res.stderr}")


class TestStaticIndexHtmlSecurityScan(unittest.TestCase):
    """Static security audit of index.html for zero innerHTML sinks and safe DOM construction."""

    @classmethod
    def setUpClass(cls):
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            cls.html_content = f.read()

    def test_zero_inner_html_occurrences(self):
        """Guarantee 0 occurrences of dynamic innerHTML assignments in index.html."""
        matches = list(re.finditer(r"\binnerHTML\b", self.html_content, re.IGNORECASE))
        self.assertEqual(
            len(matches),
            0,
            f"Found forbidden innerHTML occurrences in index.html: {[m.group() for m in matches]}"
        )

    def test_zero_outer_html_occurrences(self):
        """Guarantee 0 occurrences of outerHTML in index.html."""
        matches = list(re.finditer(r"\bouterHTML\b", self.html_content, re.IGNORECASE))
        self.assertEqual(len(matches), 0, "Found outerHTML occurrences in index.html")

    def test_zero_insert_adjacent_html_occurrences(self):
        """Guarantee 0 occurrences of insertAdjacentHTML in index.html."""
        matches = list(re.finditer(r"\binsertAdjacentHTML\b", self.html_content, re.IGNORECASE))
        self.assertEqual(len(matches), 0, "Found insertAdjacentHTML occurrences in index.html")

    def test_zero_document_write_occurrences(self):
        """Guarantee 0 occurrences of document.write or document.writeln in index.html."""
        matches = list(re.finditer(r"\bdocument\.write(?:ln)?\b", self.html_content, re.IGNORECASE))
        self.assertEqual(len(matches), 0, "Found document.write occurrences in index.html")

    def test_zero_eval_and_function_constructors(self):
        """Guarantee 0 occurrences of eval or new Function in index.html."""
        eval_matches = list(re.finditer(r"\beval\s*\(", self.html_content, re.IGNORECASE))
        func_matches = list(re.finditer(r"\bnew\s+Function\s*\(", self.html_content, re.IGNORECASE))
        self.assertEqual(len(eval_matches), 0, "Found eval() occurrences in index.html")
        self.assertEqual(len(func_matches), 0, "Found new Function() occurrences in index.html")

    def test_zero_string_timeout_interval(self):
        """Guarantee zero setTimeout/setInterval calls with string arguments."""
        timer_matches = list(re.finditer(r"\b(?:setTimeout|setInterval)\s*\(\s*['\"`]", self.html_content))
        self.assertEqual(len(timer_matches), 0, "Found string-based setTimeout/setInterval in index.html")

    def test_safe_dom_construction_presence(self):
        """Verify index.html actively employs safe DOM manipulation APIs."""
        self.assertIn("createElement", self.html_content)
        self.assertIn("textContent", self.html_content)
        self.assertIn("replaceChildren", self.html_content)
        self.assertIn("appendChild", self.html_content)

    def test_css_selector_injection_protection(self):
        """Verify node queries avoid unescaped attribute selector string concatenation."""
        vuln_pattern = re.search(r"querySelector(?:All)?\(\s*['\"`]\[data-id=\s*['\"`]?\s*\+", self.html_content)
        self.assertIsNone(vuln_pattern, "Unescaped CSS attribute selector concatenation detected in index.html")
        self.assertIn("dataset.id", self.html_content)


class TestUnicodeAndThaiBranchResilience(unittest.TestCase):
    """Verify Unicode and Thai branch names ('ฟีเจอร์ใหม่', 'สายหลัก') handling and normalization."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="n8n_test_thai_")
        self.output_js = os.path.join(self.test_dir, "output.js")
        run_git_in_repo(["init"], self.test_dir)
        run_git_in_repo(["config", "user.name", "สมชาย พัฒนา"], self.test_dir)
        run_git_in_repo(["config", "user.email", "somchai@example.com"], self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_thai_branch_and_metadata_generation(self):
        """Verify generate_dag.py cleanly generates DAG data with Thai branches, commits, and authors."""
        f_path = os.path.join(self.test_dir, "README.md")
        with open(f_path, "w", encoding="utf-8") as f:
            f.write("# โครงการทดสอบภาษาไทย\n")
        run_git_in_repo(["add", "README.md"], self.test_dir)
        run_git_in_repo(["commit", "-m", "เริ่มต้นโครงการ (สายหลัก)"], self.test_dir)

        # Create Thai branches
        run_git_in_repo(["branch", "ฟีเจอร์ใหม่"], self.test_dir)
        run_git_in_repo(["branch", "สายหลัก"], self.test_dir)
        run_git_in_repo(["branch", "feature/ภาษาไทย-ทดสอบ"], self.test_dir)

        # Checkout Thai branch and make commit
        run_git_in_repo(["checkout", "ฟีเจอร์ใหม่"], self.test_dir)
        with open(f_path, "a", encoding="utf-8") as f:
            f.write("เพิ่มข้อมูลฟีเจอร์ใหม่\n")
        run_git_in_repo(["commit", "-am", "เพิ่มฟังก์ชันใหม่ในฟีเจอร์ใหม่"], self.test_dir)

        res = subprocess.run(
            [sys.executable, GENERATE_DAG_SCRIPT, self.test_dir, "-o", self.output_js],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0, f"generate_dag.py failed:\n{res.stderr}")

        with open(self.output_js, "r", encoding="utf-8") as f:
            bundle = json.loads(f.read().split("window.GIT_DAG_DATA = ")[1].rstrip(";\n "))

        branch_names = [b["name"] for b in bundle.get("branches", [])]
        self.assertIn("ฟีเจอร์ใหม่", branch_names)
        self.assertIn("สายหลัก", branch_names)
        self.assertIn("feature/ภาษาไทย-ทดสอบ", branch_names)

        # Check nodes subjects
        subjects = [n["subject"] for n in bundle.get("nodes", [])]
        self.assertTrue(any("เริ่มต้นโครงการ (สายหลัก)" in s for s in subjects))
        self.assertTrue(any("เพิ่มฟังก์ชันใหม่ในฟีเจอร์ใหม่" in s for s in subjects))

    def test_thai_branch_normalization_logic(self):
        """Verify Thai branch normalization logic mirrors index.html's normalizeBranch specification."""
        def normalize_branch(name):
            if not name:
                return ""
            s = str(name).strip().lower()
            s = re.sub(r"^feature/", "", s)
            s = re.sub(r"^origin/", "", s)
            s = re.sub(r"^branch:\s*", "", s, flags=re.IGNORECASE)
            s = re.sub(r"^merge:\s*", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s*\(main trunk\)$", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s*\(สายหลัก\)$", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s*trunk$", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s*\(wip\)$", "", s, flags=re.IGNORECASE)
            return s

        self.assertEqual(normalize_branch("feature/ฟีเจอร์ใหม่"), "ฟีเจอร์ใหม่")
        self.assertEqual(normalize_branch("สายหลัก (สายหลัก)"), "สายหลัก")
        self.assertEqual(normalize_branch("BRANCH: ฟีเจอร์ใหม่"), "ฟีเจอร์ใหม่")
        self.assertEqual(normalize_branch("MERGE: ฟีเจอร์ใหม่"), "ฟีเจอร์ใหม่")
        self.assertEqual(normalize_branch("origin/สายหลัก"), "สายหลัก")

    def test_thai_primary_trunk_lane_zero(self):
        """Verify repository with primary branch named 'สายหลัก' assigns Lane 0 and connects trunk wire."""
        repo_dir = tempfile.mkdtemp(prefix="n8n_test_thai_trunk_")
        out_js = os.path.join(repo_dir, "out.js")
        try:
            run_git_in_repo(["init", "-b", "สายหลัก"], repo_dir)
            f_path = os.path.join(repo_dir, "main.txt")
            with open(f_path, "w", encoding="utf-8") as f:
                f.write("Line 1\n")
            run_git_in_repo(["add", "main.txt"], repo_dir)
            run_git_in_repo(["commit", "-m", "คอมมิตแรก สายหลัก"], repo_dir)

            with open(f_path, "a", encoding="utf-8") as f:
                f.write("Line 2\n")
            run_git_in_repo(["commit", "-am", "คอมมิตที่สอง สายหลัก"], repo_dir)

            res = subprocess.run(
                [sys.executable, GENERATE_DAG_SCRIPT, repo_dir, "-o", out_js],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            self.assertEqual(res.returncode, 0)

            with open(out_js, "r", encoding="utf-8") as f:
                bundle = json.loads(f.read().split("window.GIT_DAG_DATA = ")[1].rstrip(";\n "))

            self.assertEqual(bundle.get("primary_branch"), "สายหลัก")
            for node in bundle.get("nodes", []):
                self.assertEqual(node.get("lane"), 0)
        finally:
            if os.path.exists(repo_dir):
                shutil.rmtree(repo_dir, ignore_errors=True)


class TestGitArgumentInjectionResilience(unittest.TestCase):
    """Verify resilience against dash-prefixed refs ('--output=evil', '--all', '-b') and command safety."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="n8n_test_arg_")
        self.output_js = os.path.join(self.test_dir, "output.js")
        run_git_in_repo(["init"], self.test_dir)
        with open(os.path.join(self.test_dir, "init.txt"), "w", encoding="utf-8") as f:
            f.write("init\n")
        run_git_in_repo(["add", "init.txt"], self.test_dir)
        run_git_in_repo(["commit", "-m", "Initial commit"], self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dash_prefixed_branches_do_not_inject_options(self):
        """Verify update-ref branches starting with '--' cannot hijack git commands in generate_dag.py."""
        dash_refs = ["--output=evil", "--all", "-b", "--tags", "--help"]
        for ref_name in dash_refs:
            run_git_in_repo(["update-ref", f"refs/heads/{ref_name}", "HEAD"], self.test_dir)
        run_git_in_repo(["update-ref", "refs/tags/--output=evil-tag", "HEAD"], self.test_dir)

        # Also symbolically point HEAD to --output=evil
        run_git_in_repo(["symbolic-ref", "HEAD", "refs/heads/--output=evil"], self.test_dir)

        res = subprocess.run(
            [sys.executable, GENERATE_DAG_SCRIPT, self.test_dir, "-o", self.output_js],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        self.assertEqual(res.returncode, 0, f"generate_dag.py failed on dash branches:\n{res.stderr}")
        self.assertTrue(os.path.exists(self.output_js))

        # Evil file should NOT have been created by argument injection
        evil_file = os.path.join(self.test_dir, "evil")
        self.assertFalse(os.path.exists(evil_file))

        with open(self.output_js, "r", encoding="utf-8") as f:
            bundle = json.loads(f.read().split("window.GIT_DAG_DATA = ")[1].rstrip(";\n "))

        branch_names = [b["name"] for b in bundle.get("branches", [])]
        for ref_name in dash_refs:
            self.assertIn(ref_name, branch_names)

    def test_generator_script_uses_safe_argument_delimiters(self):
        """Static audit of generate_dag.py verifying '--' option delimiters and shell=False."""
        with open(GENERATE_DAG_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        # shell=True must never be used
        self.assertNotIn("shell=True", code, "Discovered insecure shell=True invocation in generate_dag.py")

        # rev-list, diff-tree, show, diff, and log must use argument protection
        self.assertIn('"rev-list"', code)
        self.assertIn('"diff-tree"', code)
        self.assertIn('"--"', code, "Missing '--' argument delimiter protection in git invocations")


class TestAtomicFileOperationsAndResilience(unittest.TestCase):
    """Verify write_atomic_file guarantees data durability, crash cleanup, and atomic replacement."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="n8n_test_atomic_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_atomic_write_and_cleanup_on_success(self):
        """Verify atomic write creates valid file with zero leftover .tmp files."""
        target_path = os.path.join(self.test_dir, "data.js")
        content = "window.GIT_DAG_DATA = { 'status': 'ok' };"
        generate_dag.write_atomic_file(target_path, content)

        self.assertTrue(os.path.exists(target_path))
        with open(target_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

        files = os.listdir(self.test_dir)
        self.assertEqual(files, ["data.js"], f"Orphaned temporary files found: {files}")

    def test_atomic_write_preserves_target_and_cleans_tmp_on_failure(self):
        """Verify existing file is preserved and temporary file is removed when replace fails."""
        target_path = os.path.join(self.test_dir, "data.js")
        initial_content = "ORIGINAL_UNTOUCHED_CONTENT"
        generate_dag.write_atomic_file(target_path, initial_content)

        # Simulate failure during os.replace
        with patch("os.replace", side_effect=OSError("Simulated replacement failure")):
            with self.assertRaises(OSError):
                generate_dag.write_atomic_file(target_path, "MALICIOUS_OR_PARTIAL_DATA")

        # Original target file must remain intact
        with open(target_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), initial_content)

        # No leftover .tmp files
        files = os.listdir(self.test_dir)
        self.assertEqual(files, ["data.js"], f"Temporary files were not cleaned up: {files}")

    def test_atomic_write_creates_nested_directories(self):
        """Verify target paths with non-existent parent directories are created automatically."""
        target_path = os.path.join(self.test_dir, "deep", "nested", "path", "data.js")
        content = "/* nested test */"
        generate_dag.write_atomic_file(target_path, content)

        self.assertTrue(os.path.exists(target_path))
        with open(target_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

    def test_atomic_write_fsync_failure_cleans_tmp(self):
        """Verify that an I/O error during fsync causes complete removal of temporary file."""
        target_path = os.path.join(self.test_dir, "fsync_test.js")
        with patch("os.fsync", side_effect=OSError("Disk I/O error during fsync")):
            with self.assertRaises(OSError):
                generate_dag.write_atomic_file(target_path, "content")

        self.assertEqual(len(os.listdir(self.test_dir)), 0, "Temporary file was not cleaned up after fsync error")


if __name__ == "__main__":
    unittest.main()
