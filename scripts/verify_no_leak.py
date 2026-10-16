#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-commit Guard Script: Verify No Leak (F14)
Ensures:
1. git_data.js is actively ignored by .gitignore (git check-ignore -q git_data.js).
2. Prohibited live artifacts (git_data.js, git_data*.json, test_output*.js, test_*.js, test_m2*.js, *.tmp)
   are NEVER staged in git index or working tree.
3. Commit history (last 50 commits) does not contain leaked live data or test outputs.
4. demo_data.js contains only sanitized/synthetic hashes and does not leak host repository commit hashes.
"""

import os
import sys
import fnmatch
import subprocess

LEAK_PATTERNS = [
    "git_data.js",
    "git_data*.json",
    "test_output*.js",
    "test_*.js",
    "test_m2*.js",
    "*.tmp",
]

# Historical initial repository release commit prior to Plan 110 data-leak guard introduction.
HISTORICAL_ROOT_WHITELIST = {
    "af0bb3fc677b995826107aa414b53e80ba9c69c6",
    "af0bb3f",
}

def run_git(args, cwd):
    """Run git command and return (returncode, stdout, stderr)."""
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

def is_leaked_artifact(path_str):
    """
    Check if a file path matches any prohibited artifact pattern.
    Checks against both filename (basename) and normalized path.
    """
    normalized = path_str.replace("\\", "/").strip().strip("\"'")
    base_name = os.path.basename(normalized)
    for pat in LEAK_PATTERNS:
        if fnmatch.fnmatch(base_name, pat):
            return True
        if fnmatch.fnmatch(normalized, pat) or fnmatch.fnmatch(normalized, f"**/{pat}"):
            return True
    return False

def find_host_repo(repo_root):
    """
    Locate host repository if n8n-git-ui is embedded within .git/ of another repository.
    Can also be overridden by HOST_REPO_DIR environment variable.
    """
    env_host = os.environ.get("HOST_REPO_DIR")
    if env_host and os.path.isdir(os.path.join(env_host, ".git")):
        return os.path.abspath(env_host)
    
    candidate_2up = os.path.abspath(os.path.join(repo_root, "..", ".."))
    if os.path.isdir(os.path.join(candidate_2up, ".git")) and candidate_2up != repo_root:
        return candidate_2up
    
    candidate_1up = os.path.abspath(os.path.join(repo_root, ".."))
    if os.path.isdir(os.path.join(candidate_1up, ".git")) and candidate_1up != repo_root:
        return candidate_1up

    return None

def verify_no_leak(repo_root=None):
    if repo_root is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.abspath(os.path.join(script_dir, ".."))

    # Resolve actual repo root via git
    code, out, _ = run_git(["rev-parse", "--show-toplevel"], cwd=repo_root)
    if code == 0 and out.strip():
        repo_root = os.path.abspath(out.strip())

    has_leak = False
    reasons = []

    # 1. Active .gitignore enforcement: git_data.js MUST be ignored
    code, _, _ = run_git(["check-ignore", "-q", "git_data.js"], cwd=repo_root)
    if code != 0:
        has_leak = True
        reasons.append("Active .gitignore check failed: 'git_data.js' is NOT ignored by git (git check-ignore -q git_data.js returned non-zero)")

    # 2. Check git ls-files --stage for prohibited patterns in git index
    code, ls_out, _ = run_git(["ls-files", "--stage"], cwd=repo_root)
    if code == 0 and ls_out.strip():
        for line in ls_out.splitlines():
            parts = line.strip().split(None, 3)
            if len(parts) >= 4:
                filepath = parts[3]
                if is_leaked_artifact(filepath):
                    has_leak = True
                    reasons.append(f"Prohibited artifact tracked in index: {filepath}")

    # 3. Check git diff --cached --name-status for staged additions/modifications/renames
    code, diff_out, _ = run_git(["diff", "--cached", "--name-status"], cwd=repo_root)
    if code == 0 and diff_out.strip():
        for line in diff_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            status_char = parts[0].strip()
            if status_char.startswith("D"):
                # Pure deletion is permitted (untracking)
                continue
            elif status_char.startswith("R"):
                if len(parts) >= 3 and is_leaked_artifact(parts[2].strip()):
                    has_leak = True
                    reasons.append(f"Prohibited artifact staged as rename destination: {parts[2].strip()}")
            else:
                for f in parts[1:]:
                    if is_leaked_artifact(f.strip()):
                        has_leak = True
                        reasons.append(f"Prohibited artifact staged for commit (status: {status_char}, path: {f.strip()})")

    # 4. Check git status --porcelain for staged entries
    code, status_out, _ = run_git(["status", "--porcelain"], cwd=repo_root)
    if code == 0 and status_out.strip():
        for line in status_out.splitlines():
            if len(line) < 3:
                continue
            index_status = line[0]
            path_part = line[3:].strip()
            if index_status in ["A", "M", "C", "U"]:
                if is_leaked_artifact(path_part):
                    has_leak = True
                    reasons.append(f"Prohibited artifact staged in index ({index_status}): {path_part}")
            elif index_status == "R":
                if "->" in path_part:
                    dst = path_part.split("->", 1)[1].strip()
                    if is_leaked_artifact(dst):
                        has_leak = True
                        reasons.append(f"Prohibited artifact staged as rename destination: {dst}")

    # 5. Commit history check (last 50 commits)
    code, log_out, _ = run_git(["log", "-n", "50", "--name-only", "--format=commit %H"], cwd=repo_root)
    if code == 0 and log_out.strip():
        current_commit = None
        for line in log_out.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("commit "):
                current_commit = line.split()[1]
                continue
            if current_commit and any(current_commit.startswith(w) for w in HISTORICAL_ROOT_WHITELIST):
                continue
            if is_leaked_artifact(line):
                has_leak = True
                reasons.append(f"Prohibited artifact '{line}' was committed in recent commit {current_commit}")

    # 6. demo_data.js check: verify that no recent host repository commit hashes appear in demo_data.js
    demo_path = os.path.join(repo_root, "demo_data.js")
    if os.path.isfile(demo_path):
        with open(demo_path, "r", encoding="utf-8", errors="replace") as f:
            demo_content = f.read()

        # Cross-check host repository commits
        host_repo = find_host_repo(repo_root)
        if host_repo:
            h_code, h_out, _ = run_git(["log", "-n", "50", "--format=%H"], cwd=host_repo)
            if h_code == 0 and h_out.strip():
                host_hashes = [h.strip() for h in h_out.splitlines() if len(h.strip()) >= 7]
                for h in host_hashes:
                    if h in demo_content or h[:7] in demo_content:
                        has_leak = True
                        reasons.append(f"Host repository commit hash '{h}' (or short '{h[:7]}') leaked into demo_data.js")

        # Cross-check local repository commits (excluding historical initial commit)
        r_code, r_out, _ = run_git(["log", "-n", "50", "--format=%H"], cwd=repo_root)
        if r_code == 0 and r_out.strip():
            repo_hashes = [h.strip() for h in r_out.splitlines() if len(h.strip()) >= 7]
            for h in repo_hashes:
                if any(h.startswith(w) for w in HISTORICAL_ROOT_WHITELIST):
                    continue
                if h in demo_content or h[:7] in demo_content:
                    has_leak = True
                    reasons.append(f"Repository commit hash '{h}' found in demo_data.js (demo_data.js must use synthetic hashes)")

    if has_leak:
        sys.stderr.write("=" * 70 + "\n")
        sys.stderr.write("[SECURITY VIOLATION] Private data or test artifacts detected in git!\n")
        sys.stderr.write("=" * 70 + "\n")
        for reason in reasons:
            sys.stderr.write(f"- {reason}\n")
        sys.stderr.write("\nAction required:\n")
        sys.stderr.write("  Ensure git_data.js and test outputs are listed in .gitignore\n")
        sys.stderr.write("  Run: git rm --cached <file> for any mistakenly tracked artifacts\n")
        sys.stderr.write("  Ensure demo_data.js uses exclusively synthetic hashes and metadata\n")
        sys.stderr.write("=" * 70 + "\n")
        sys.exit(1)

    print("[SECURITY CHECK PASSED] .gitignore enforced. Staging and history clean of data leaks.")
    sys.exit(0)

if __name__ == "__main__":
    target_repo = sys.argv[1] if len(sys.argv) > 1 else None
    verify_no_leak(target_repo)
