#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Install synchronous, Windows Job-Object-safe Git hooks (post-commit, post-checkout,
post-merge, post-rewrite) for automatic n8n-git-ui graph updates.
"""

import os
import sys

REPO_UI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_UI_DIR not in sys.path:
    sys.path.insert(0, REPO_UI_DIR)

from generate_dag import install_git_hooks


def main():
    repo_arg = sys.argv[1] if len(sys.argv) > 1 else None
    install_git_hooks(repo_path=repo_arg)


if __name__ == "__main__":
    main()
