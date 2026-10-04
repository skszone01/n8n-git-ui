#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schema Validator for n8n-git-ui DAG Data Files (git_data.js / demo_data.js)

Validates the window.GIT_DAG_DATA payload structure, field types, coordinates,
and relational integrity without external dependencies.
"""

import os
import sys
import json
import re
import math
from typing import Any, Dict, List, Optional, Tuple, Set


class SchemaValidationError:
    def __init__(self, category: str, message: str, item_id: Optional[str] = None):
        self.category = category  # 'MISSING_KEY', 'TYPE_MISMATCH', 'INVALID_COORD', 'INTEGRITY'
        self.message = message
        self.item_id = item_id

    def __str__(self) -> str:
        if self.item_id:
            return f"[{self.category}] {self.item_id}: {self.message}"
        return f"[{self.category}] {self.message}"


class ValidationReport:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.repo: str = "Unknown"
        self.head_branch: str = "Unknown"
        self.schema_version: str = "1 (legacy/unspecified)"
        self.node_count: int = 0
        self.edge_count: int = 0
        self.branch_count: int = 0
        self.is_dirty: bool = False
        self.dirty_count: int = 0
        self.errors: List[SchemaValidationError] = []
        self.warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, category: str, message: str, item_id: Optional[str] = None):
        self.errors.append(SchemaValidationError(category, message, item_id))

    def add_warning(self, message: str):
        self.warnings.append(message)


def parse_git_dag_js(file_path: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Parse the window.GIT_DAG_DATA payload from a JS file.
    Returns (data_dict, error_message).
    """
    if not os.path.exists(file_path):
        return None, f"File does not exist: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return None, f"Failed to read file '{file_path}': {e}"

    match = re.search(r'(?:window\.)?GIT_DAG_DATA\s*=', content)
    if not match:
        return None, "File does not contain 'window.GIT_DAG_DATA = ...' assignment"

    start_pos = match.end()
    brace_idx = content.find('{', start_pos)
    if brace_idx == -1:
        return None, "No JSON object opening '{' found after GIT_DAG_DATA assignment"

    decoder = json.JSONDecoder()
    try:
        data, _ = decoder.raw_decode(content[brace_idx:])
    except json.JSONDecodeError as e:
        return None, f"JSON syntax error while parsing GIT_DAG_DATA: {e}"

    if not isinstance(data, dict):
        return None, f"GIT_DAG_DATA must be a JSON object, got {type(data).__name__}"

    return data, None


def _is_valid_number(val: Any) -> bool:
    """Check if value is a valid real number (not None, not bool, not NaN, not inf)."""
    if val is None:
        return False
    if isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    if math.isnan(val) or math.isinf(val):
        return False
    return True


def validate_schema(data: dict, file_path: str, strict: bool = False) -> ValidationReport:
    """
    Perform complete schema validation on parsed GIT_DAG_DATA dictionary.
    """
    report = ValidationReport(file_path)

    # 1. Top-Level Fields Validation
    report.repo = str(data.get("repo", "Unknown"))
    report.head_branch = str(data.get("head_branch", "Unknown"))
    if "schema_version" in data:
        report.schema_version = str(data["schema_version"])

    # 'repo' (str)
    if "repo" not in data:
        report.add_error("MISSING_KEY", "Missing required top-level key: 'repo'")
    elif not isinstance(data["repo"], str) or not data["repo"].strip():
        report.add_error("TYPE_MISMATCH", f"Top-level 'repo' must be a non-empty string, got {type(data['repo']).__name__}")

    # 'head_branch' (str)
    if "head_branch" not in data:
        report.add_error("MISSING_KEY", "Missing required top-level key: 'head_branch'")
    elif not isinstance(data["head_branch"], str) or not data["head_branch"].strip():
        report.add_error("TYPE_MISMATCH", f"Top-level 'head_branch' must be a non-empty string, got {type(data['head_branch']).__name__}")

    # 'nodes' (list, len > 0)
    if "nodes" not in data:
        report.add_error("MISSING_KEY", "Missing required top-level key: 'nodes'")
        nodes = []
    elif not isinstance(data["nodes"], list):
        report.add_error("TYPE_MISMATCH", f"Top-level 'nodes' must be a list, got {type(data['nodes']).__name__}")
        nodes = []
    elif len(data["nodes"]) == 0:
        report.add_error("TYPE_MISMATCH", "Top-level 'nodes' list must not be empty (length > 0)")
        nodes = []
    else:
        nodes = data["nodes"]

    report.node_count = len(nodes)

    # 'edges' (list)
    if "edges" not in data:
        report.add_error("MISSING_KEY", "Missing required top-level key: 'edges'")
        edges = []
    elif not isinstance(data["edges"], list):
        report.add_error("TYPE_MISMATCH", f"Top-level 'edges' must be a list, got {type(data['edges']).__name__}")
        edges = []
    else:
        edges = data["edges"]

    report.edge_count = len(edges)

    # 'status' (dict with is_dirty, dirty_count)
    if "status" not in data:
        report.add_error("MISSING_KEY", "Missing required top-level key: 'status'")
    elif not isinstance(data["status"], dict):
        report.add_error("TYPE_MISMATCH", f"Top-level 'status' must be a dict, got {type(data['status']).__name__}")
    else:
        status_dict = data["status"]
        if "is_dirty" not in status_dict:
            report.add_error("MISSING_KEY", "Top-level 'status' missing required key: 'is_dirty'")
        elif not isinstance(status_dict["is_dirty"], bool):
            report.add_error("TYPE_MISMATCH", f"'status.is_dirty' must be bool, got {type(status_dict['is_dirty']).__name__}")
        else:
            report.is_dirty = status_dict["is_dirty"]

        if "dirty_count" not in status_dict:
            report.add_error("MISSING_KEY", "Top-level 'status' missing required key: 'dirty_count'")
        elif not isinstance(status_dict["dirty_count"], int) or isinstance(status_dict["dirty_count"], bool) or status_dict["dirty_count"] < 0:
            report.add_error("TYPE_MISMATCH", f"'status.dirty_count' must be a non-negative integer, got {status_dict['dirty_count']!r}")
        else:
            report.dirty_count = status_dict["dirty_count"]

    # 'branches' (list)
    if "branches" not in data:
        report.add_error("MISSING_KEY", "Missing required top-level key: 'branches'")
        branches = []
    elif not isinstance(data["branches"], list):
        report.add_error("TYPE_MISMATCH", f"Top-level 'branches' must be a list, got {type(data['branches']).__name__}")
        branches = []
    else:
        branches = data["branches"]

    report.branch_count = len(branches)

    # 2. Node Item Validation
    node_ids: Set[str] = set()
    head_node_count = 0

    for idx, node in enumerate(nodes):
        node_ref = f"nodes[{idx}]"
        if not isinstance(node, dict):
            report.add_error("TYPE_MISMATCH", f"Node at index {idx} must be a dict, got {type(node).__name__}", node_ref)
            continue

        nid = node.get("id")
        if nid is None or not isinstance(nid, str) or not nid.strip():
            report.add_error("MISSING_KEY", f"Missing or invalid required key 'id' (must be non-empty str)", node_ref)
            node_id_str = f"node-{idx}"
        else:
            node_id_str = str(nid)
            if node_id_str in node_ids:
                report.add_error("INTEGRITY", f"Duplicate node id detected: '{node_id_str}'", node_id_str)
            node_ids.add(node_id_str)

        # short_id or short_hash (str)
        has_short_id = "short_id" in node
        has_short_hash = "short_hash" in node
        if not has_short_id and not has_short_hash:
            report.add_error("MISSING_KEY", "Node must have either 'short_id' or 'short_hash'", node_id_str)
        else:
            if has_short_id and (not isinstance(node["short_id"], str) or not node["short_id"]):
                report.add_error("TYPE_MISMATCH", f"'short_id' must be non-empty str, got {type(node['short_id']).__name__}", node_id_str)
            if has_short_hash and (not isinstance(node["short_hash"], str) or not node["short_hash"]):
                report.add_error("TYPE_MISMATCH", f"'short_hash' must be non-empty str, got {type(node['short_hash']).__name__}", node_id_str)

        # title or subject (str)
        has_title = "title" in node
        has_subject = "subject" in node
        if not has_title and not has_subject:
            report.add_error("MISSING_KEY", "Node must have either 'title' or 'subject'", node_id_str)
        else:
            if has_title and not isinstance(node["title"], str):
                report.add_error("TYPE_MISMATCH", f"'title' must be str, got {type(node['title']).__name__}", node_id_str)
            if has_subject and not isinstance(node["subject"], str):
                report.add_error("TYPE_MISMATCH", f"'subject' must be str, got {type(node['subject']).__name__}", node_id_str)

        # author (str)
        if "author" not in node:
            report.add_error("MISSING_KEY", "Missing required key 'author'", node_id_str)
        elif not isinstance(node["author"], str):
            report.add_error("TYPE_MISMATCH", f"'author' must be str, got {type(node['author']).__name__}", node_id_str)

        # date (str)
        if "date" not in node:
            report.add_error("MISSING_KEY", "Missing required key 'date'", node_id_str)
        elif not isinstance(node["date"], str):
            report.add_error("TYPE_MISMATCH", f"'date' must be str, got {type(node['date']).__name__}", node_id_str)

        # branches (list)
        if "branches" not in node:
            report.add_error("MISSING_KEY", "Missing required key 'branches'", node_id_str)
        elif not isinstance(node["branches"], list):
            report.add_error("TYPE_MISMATCH", f"'branches' must be list, got {type(node['branches']).__name__}", node_id_str)
        else:
            for b in node["branches"]:
                if not isinstance(b, str):
                    report.add_error("TYPE_MISMATCH", f"Every item in 'branches' must be str, got {type(b).__name__}", node_id_str)

        # parents (list)
        if "parents" not in node:
            report.add_error("MISSING_KEY", "Missing required key 'parents'", node_id_str)
        elif not isinstance(node["parents"], list):
            report.add_error("TYPE_MISMATCH", f"'parents' must be list, got {type(node['parents']).__name__}", node_id_str)
        else:
            for p in node["parents"]:
                if not isinstance(p, str):
                    report.add_error("TYPE_MISMATCH", f"Every item in 'parents' must be str, got {type(p).__name__}", node_id_str)

        # lane (int)
        if "lane" not in node:
            report.add_error("MISSING_KEY", "Missing required key 'lane'", node_id_str)
        elif isinstance(node["lane"], bool) or not isinstance(node["lane"], int):
            report.add_error("TYPE_MISMATCH", f"'lane' must be int, got {type(node['lane']).__name__}", node_id_str)

        # Coordinates: x, y, width, height (int/float, not None, not NaN, not inf)
        for coord_name in ["x", "y", "width", "height"]:
            if coord_name not in node:
                report.add_error("MISSING_KEY", f"Missing required coordinate key '{coord_name}'", node_id_str)
            else:
                cval = node[coord_name]
                if not _is_valid_number(cval):
                    report.add_error("INVALID_COORD", f"Coordinate '{coord_name}' must be valid int/float (not None, NaN, inf), got {cval!r}", node_id_str)
                elif coord_name in ["width", "height"] and cval <= 0:
                    report.add_error("INVALID_COORD", f"Dimension '{coord_name}' must be > 0, got {cval!r}", node_id_str)

        # is_head (bool)
        if "is_head" not in node:
            report.add_error("MISSING_KEY", "Missing required key 'is_head'", node_id_str)
        elif not isinstance(node["is_head"], bool):
            report.add_error("TYPE_MISMATCH", f"'is_head' must be bool, got {type(node['is_head']).__name__}", node_id_str)
        elif node["is_head"]:
            head_node_count += 1

        # is_merge (bool)
        if "is_merge" not in node:
            report.add_error("MISSING_KEY", "Missing required key 'is_merge'", node_id_str)
        elif not isinstance(node["is_merge"], bool):
            report.add_error("TYPE_MISMATCH", f"'is_merge' must be bool, got {type(node['is_merge']).__name__}", node_id_str)

        # is_wip (bool)
        is_wip_explicit = "is_wip" in node
        if is_wip_explicit:
            if not isinstance(node["is_wip"], bool):
                report.add_error("TYPE_MISMATCH", f"'is_wip' must be bool, got {type(node['is_wip']).__name__}", node_id_str)
        else:
            # Check if this node is clearly a WIP node
            is_wip_node = (node.get("status") == "wip" or node_id_str == "active-wip" or node_id_str == "working-directory-wip")
            if is_wip_node:
                report.add_error("MISSING_KEY", "WIP node must explicitly declare 'is_wip': True", node_id_str)
            elif strict:
                report.add_error("MISSING_KEY", "Missing required key 'is_wip' (strict mode enabled)", node_id_str)

    if head_node_count == 0 and len(nodes) > 0:
        report.add_warning("No node in the graph is marked with 'is_head': True")

    # 3. Edges Validation
    for idx, edge in enumerate(edges):
        edge_ref = f"edges[{idx}]"
        if not isinstance(edge, dict):
            report.add_error("TYPE_MISMATCH", f"Edge at index {idx} must be a dict, got {type(edge).__name__}", edge_ref)
            continue

        edge_id = str(edge.get("id", f"edge-{idx}"))

        # 'from' (str)
        efrom = edge.get("from")
        if efrom is None:
            report.add_error("MISSING_KEY", "Missing required key 'from'", edge_id)
        elif not isinstance(efrom, str) or not efrom.strip():
            report.add_error("TYPE_MISMATCH", f"'from' must be non-empty str, got {type(efrom).__name__}", edge_id)
        elif efrom not in node_ids:
            report.add_warning(f"Edge '{edge_id}': 'from' node '{efrom}' does not exist in nodes list")

        # 'to' (str)
        eto = edge.get("to")
        if eto is None:
            report.add_error("MISSING_KEY", "Missing required key 'to'", edge_id)
        elif not isinstance(eto, str) or not eto.strip():
            report.add_error("TYPE_MISMATCH", f"'to' must be non-empty str, got {type(eto).__name__}", edge_id)
        elif eto not in node_ids:
            report.add_warning(f"Edge '{edge_id}': 'to' node '{eto}' does not exist in nodes list")

        # 'svg_path' (str)
        svg_path = edge.get("svg_path")
        if svg_path is None:
            report.add_error("MISSING_KEY", "Missing required key 'svg_path'", edge_id)
        elif not isinstance(svg_path, str) or not svg_path.strip():
            report.add_error("TYPE_MISMATCH", f"'svg_path' must be non-empty str, got {type(svg_path).__name__}", edge_id)

        # 'color' (str)
        color = edge.get("color")
        if color is None:
            report.add_error("MISSING_KEY", "Missing required key 'color'", edge_id)
        elif not isinstance(color, str) or not color.strip():
            report.add_error("TYPE_MISMATCH", f"'color' must be non-empty str, got {type(color).__name__}", edge_id)

    return report


def print_report(report: ValidationReport, verbose: bool = False):
    """Print a clean, structured validation report."""
    border = "=" * 80
    subborder = "-" * 80

    print(border)
    status_str = "SUCCESS" if report.is_valid else "FAILURE"
    print(f"SCHEMA VALIDATION REPORT: {status_str}")
    print(border)
    print(f"  Target File:     {report.file_path}")
    print(f"  Repository:      {report.repo}")
    print(f"  Head Branch:     {report.head_branch}")
    print(f"  Schema Version:  {report.schema_version}")
    print(subborder)
    print("SUMMARY COUNTS:")
    print(f"  Nodes:           {report.node_count}")
    print(f"  Edges:           {report.edge_count}")
    print(f"  Branches:        {report.branch_count}")
    print(f"  Working Tree:    {'DIRTY (' + str(report.dirty_count) + ' changes)' if report.is_dirty else 'CLEAN'}")
    print(subborder)

    if report.warnings:
        print(f"WARNINGS ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"  [WARN] {w}")
        print(subborder)

    if report.is_valid:
        print("[OK] Top-level schema structure: PASSED")
        print(f"[OK] All {report.node_count} nodes validated: PASSED")
        print(f"[OK] All {report.edge_count} edges validated: PASSED")
        print(f"[OK] Coordinates and dimensions: PASSED")
        print(border)
        print("RESULT: SUCCESS (0 errors) - Schema is 100% compliant")
        print(border)
    else:
        print(f"ERRORS FOUND ({len(report.errors)}):")
        # Group errors by category
        by_cat: Dict[str, List[SchemaValidationError]] = {}
        for err in report.errors:
            by_cat.setdefault(err.category, []).append(err)

        for cat, err_list in by_cat.items():
            print(f"\n  Category: {cat} ({len(err_list)} items)")
            display_items = err_list if verbose else err_list[:15]
            for err in display_items:
                print(f"    - {err}")
            if not verbose and len(err_list) > 15:
                print(f"    ... and {len(err_list) - 15} more {cat} errors (run with --verbose to view all)")

        print("\n" + border)
        print(f"RESULT: FAILURE ({len(report.errors)} errors) - Validation failed")
        print(border)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate n8n-git-ui DAG JS data files (git_data.js / demo_data.js) against schema."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="One or more .js files to validate (defaults to demo_data.js or git_data.js in repo root)."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict schema checking (e.g., explicit is_wip on all nodes)."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print all error details without truncation."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results in JSON format."
    )

    args = parser.parse_args()

    files_to_check = args.files
    if not files_to_check:
        # Default lookup
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        demo_candidate = os.path.join(repo_root, "demo_data.js")
        git_candidate = os.path.join(repo_root, "git_data.js")

        if os.path.exists(demo_candidate):
            files_to_check = [demo_candidate]
        elif os.path.exists(git_candidate):
            files_to_check = [git_candidate]
        else:
            # Check current working directory
            if os.path.exists("demo_data.js"):
                files_to_check = ["demo_data.js"]
            elif os.path.exists("git_data.js"):
                files_to_check = ["git_data.js"]
            else:
                sys.stderr.write("[ERROR] No target file specified and neither demo_data.js nor git_data.js was found.\n")
                sys.exit(1)

    all_passed = True
    reports = []

    for file_path in files_to_check:
        data, err = parse_git_dag_js(file_path)
        if err:
            report = ValidationReport(file_path)
            report.add_error("SYNTAX_ERROR", err)
            reports.append(report)
            all_passed = False
            if not args.json_output:
                print_report(report, verbose=args.verbose)
            continue

        report = validate_schema(data, file_path, strict=args.strict)
        reports.append(report)
        if not report.is_valid:
            all_passed = False

        if not args.json_output:
            print_report(report, verbose=args.verbose)

    if args.json_output:
        json_summary = {
            "all_passed": all_passed,
            "reports": [
                {
                    "file_path": r.file_path,
                    "repo": r.repo,
                    "head_branch": r.head_branch,
                    "schema_version": r.schema_version,
                    "is_valid": r.is_valid,
                    "node_count": r.node_count,
                    "edge_count": r.edge_count,
                    "branch_count": r.branch_count,
                    "is_dirty": r.is_dirty,
                    "dirty_count": r.dirty_count,
                    "errors": [str(e) for e in r.errors],
                    "warnings": r.warnings,
                }
                for r in reports
            ]
        }
        print(json.dumps(json_summary, indent=2))

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
