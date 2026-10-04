#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-commit Guard Script: Verify No Leak
Ensures git_data.js (containing local/live repository data) is NEVER staged or committed to Git.
"""

import os
import sys
import subprocess

def run_git(args, cwd):
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        sys.stderr.write(f"[ERROR] Failed to run git {' '.join(args)}: {e}\n")
        return 1, "", str(e)

def verify_no_leak():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, ".."))

    # Resolve repo root via git
    code, out, _ = run_git(["rev-parse", "--show-toplevel"], cwd=repo_root)
    if code == 0 and out.strip():
        repo_root = os.path.abspath(out.strip())

    has_leak = False
    reasons = []

    # 1. Check git ls-files --stage for git_data.js in the staging area / index
    code, ls_out, _ = run_git(["ls-files", "--stage", "git_data.js", "**/git_data.js"], cwd=repo_root)
    if code == 0 and ls_out.strip():
        has_leak = True
        reasons.append(f"git_data.js is tracked/present in git index:\n{ls_out.strip()}")

    # 2. Check git diff --cached --name-status for any staging of git_data.js
    code, diff_out, _ = run_git(["diff", "--cached", "--name-status"], cwd=repo_root)
    if code == 0 and diff_out.strip():
        for line in diff_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            status_char = parts[0].strip()
            if status_char.startswith("D"):
                # Pure deletion of git_data.js is permitted (untracking)
                continue
            elif status_char.startswith("R"):
                # In renames, parts[1] is old_path, parts[2] is new_path
                # If new_path is git_data.js, it's being staged into git!
                if len(parts) >= 3 and os.path.basename(parts[2].strip()) == "git_data.js":
                    has_leak = True
                    reasons.append(f"git_data.js is staged as rename destination: {line}")
            else:
                # Added ('A'), Modified ('M'), Copied ('C'), etc.
                for f in parts[1:]:
                    if os.path.basename(f.strip()) == "git_data.js":
                        has_leak = True
                        reasons.append(f"git_data.js is staged for commit (status: {status_char}, path: {f})")

    # 3. Check git status --porcelain for staged entries
    code, status_out, _ = run_git(["status", "--porcelain"], cwd=repo_root)
    if code == 0 and status_out.strip():
        for line in status_out.splitlines():
            if len(line) < 3:
                continue
            index_status = line[0]
            path_part = line[3:].strip()
            if "git_data.js" in path_part:
                # If staged in index and not deleted
                if index_status in ["A", "M", "C", "U"]:
                    has_leak = True
                    reasons.append(f"git_data.js is staged in index ({line})")
                elif index_status == "R":
                    if "->" in path_part:
                        src, dst = [p.strip() for p in path_part.split("->", 1)]
                        if os.path.basename(dst) == "git_data.js":
                            has_leak = True
                            reasons.append(f"git_data.js is staged as rename destination ({line})")

    if has_leak:
        sys.stderr.write("=" * 70 + "\n")
        sys.stderr.write("[SECURITY VIOLATION] git_data.js MUST NOT be committed to git!\n")
        sys.stderr.write("=" * 70 + "\n")
        for reason in reasons:
            sys.stderr.write(f"- {reason}\n")
        sys.stderr.write("\nAction required:\n")
        sys.stderr.write("  Run: git rm --cached git_data.js\n")
        sys.stderr.write("  Ensure git_data.js is listed in .gitignore\n")
        sys.stderr.write("=" * 70 + "\n")
        sys.exit(1)

    print("[SECURITY CHECK PASSED] No git_data.js staged. Working tree is clean of data leaks.")
    sys.exit(0)

if __name__ == "__main__":
    verify_no_leak()
