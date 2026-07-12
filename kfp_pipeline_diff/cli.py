"""CLI module for orchestrating the KFP pipeline parsing, diffing, rendering, and comment posting.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from typing import List, Optional

from .diff import diff_pipelines
from .github import post_or_update_sticky_comment
from .parser import parse_pipeline_meta_and_tasks, parse_pipeline_tasks, parse_pipeline_parameters
from .renderer import generate_markdown_report


def scan_and_diff_directory(
    pipelines_dir: str,
    base_branch: str,
    github_pr: Optional[int],
    github_repo: Optional[str],
    github_token: Optional[str],
    github_api_url: str,
    output_path: Optional[str],
) -> int:
    """Scans a directory for pipelines, diffs each against its Git baseline, and posts comments."""
    if not os.path.exists(pipelines_dir):
        print(f"❌ Error: Pipelines directory '{pipelines_dir}' does not exist.")
        return 1

    # 1. Fetch the base branch to ensure baseline refs are available (handles shallow clones)
    print(f"📡 Fetching base branch '{base_branch}' from origin...")
    subprocess.run(["git", "fetch", "origin", base_branch, "--depth=1"], capture_output=True)

    # 2. Gather candidate pipeline files in the directory
    candidates = []
    for root, _, files in os.walk(pipelines_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in [".py", ".yaml", ".json"]:
                candidates.append(os.path.join(root, f))

    candidates = sorted(list(set(candidates)))

    valid_pipelines = []
    # Identify valid KFP pipeline specs or python scripts
    for filepath in candidates:
        if "pycache" in filepath or "diff_report" in filepath or "report.md" in filepath:
            continue
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if filepath.endswith(".py") and ("dsl.pipeline" not in content and "import kfp" not in content):
                continue
            if (filepath.endswith(".yaml") or filepath.endswith(".json")) and ("pipelineSpec" not in content and "PipelineJob" not in content):
                continue
            valid_pipelines.append(filepath)
        except Exception:
            continue

    if not valid_pipelines:
        print(f"⚠️ No valid KFP v2 pipelines found in scan directory '{pipelines_dir}'.")
        return 0

    print(f"📂 Found {len(valid_pipelines)} valid KFP pipeline files in scan directory '{pipelines_dir}':")
    for filepath in valid_pipelines:
        print(f"  - {filepath}")

    has_failures = False
    successful_runs = []
    failed_runs = []

    for filepath in valid_pipelines:
        print(f"\n🧬 Processing pipeline file: {filepath}")
        
        # Parse target version (after)
        try:
            after_name, after_tasks = parse_pipeline_meta_and_tasks(filepath)
            after_params = parse_pipeline_parameters(filepath)
        except Exception as e:
            print(f"⚠️ Skipping '{filepath}': failed to parse/compile target version: {e}")
            failed_runs.append({"file": filepath, "error": str(e)})
            has_failures = True
            continue

        # Extract baseline version from Git history
        before_file = None
        before_name = after_name
        before_tasks = {}
        before_params = {}

        # Convert path to relative representation to query Git
        rel_path = os.path.relpath(filepath)
        ref_path = f"origin/{base_branch}:{rel_path}"
        res = subprocess.run(["git", "show", ref_path], capture_output=True, text=True)
        if res.returncode == 0:
            suffix = os.path.splitext(filepath)[1]
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="w", encoding="utf-8") as tmp:
                tmp.write(res.stdout)
                before_file = tmp.name

            try:
                before_name, before_tasks = parse_pipeline_meta_and_tasks(before_file)
                before_params = parse_pipeline_parameters(before_file)
            except Exception as e:
                print(f"⚠️ Warning: Found '{filepath}' in baseline '{base_branch}', but failed to parse: {e}. Treating as new.")
                before_tasks = {}
                before_params = {}
            finally:
                if before_file and os.path.exists(before_file):
                    os.remove(before_file)
        else:
            print(f"ℹ️ File '{filepath}' does not exist in baseline branch '{base_branch}'. Treating as newly added.")

        # Reconcile baseline and target
        diff = diff_pipelines(
            before_tasks,
            after_tasks,
            before_name,
            after_name,
            before_params=before_params,
            after_params=after_params,
        )

        # Render reports
        report = generate_markdown_report(diff, github_pr)

        if output_path:
            out_dir = os.path.dirname(output_path) or "."
            out_base = os.path.basename(output_path)
            prefix = os.path.splitext(out_base)[0]
            ext = os.path.splitext(out_base)[1]
            pipeline_out_path = os.path.join(out_dir, f"{prefix}_{after_name}{ext}")
            print(f"💾 Writing local report to: {pipeline_out_path}")
            with open(pipeline_out_path, "w", encoding="utf-8") as f:
                f.write(report)

        # Print quick results summary to output stdout console log
        print(f"  📈 Diff Results for '{after_name}':")
        print(f"    🟢 Added tasks: {len(diff.added_nodes)} | Edges: {len(diff.added_edges)}")
        print(f"    🔴 Removed tasks: {len(diff.removed_nodes)} | Edges: {len(diff.removed_edges)}")
        print(f"    🟡 Modified tasks: {len(diff.modified_nodes)}")
        print(f"    ⚪ Unchanged tasks: {len(diff.unchanged_nodes)} | Edges: {len(diff.unchanged_edges)}")

        commented_ok = False
        # Post update/create issue comments
        if github_token and github_repo and github_pr:
            print(f"📬 Posting/Updating sticky comment on PR #{github_pr} for pipeline '{after_name}'...")
            unique_anchor = f"<!-- kfp-pipeline-diff-sticky-comment-anchor-{after_name} -->"
            try:
                post_or_update_sticky_comment(
                    repo=github_repo,
                    pr_number=github_pr,
                    token=github_token,
                    body=report,
                    api_url=github_api_url,
                    anchor=unique_anchor,
                )
                print(f"✨ Sticky comment for '{after_name}' posted successfully!")
                commented_ok = True
            except Exception as e:
                print(f"❌ Failed to post sticky comment for '{after_name}': {e}")
                has_failures = True

        successful_runs.append({
            "file": filepath,
            "name": after_name,
            "added": len(diff.added_nodes),
            "removed": len(diff.removed_nodes),
            "modified": len(diff.modified_nodes),
            "unchanged": len(diff.unchanged_nodes),
            "commented": commented_ok
        })

    print("\n" + "=" * 80)
    print("🏁 KFP PIPELINE DIFF SCAN EXECUTION SUMMARY")
    print("=" * 80)
    print(f"📁 Total Files Scanned: {len(valid_pipelines)}")
    print(f"✅ Successfully Processed: {len(successful_runs)}")
    print(f"❌ Skipped/Failed: {len(failed_runs)}\n")

    if successful_runs:
        print("📊 Successful Runs Detail:")
        print("-" * 110)
        print(f"{'Pipeline Name':<35} | {'File Path':<35} | {'Added':<6} | {'Removed':<7} | {'Modified':<8} | {'Commented':<9}")
        print("-" * 110)
        for run in successful_runs:
            comment_status = "Yes" if run["commented"] else "No"
            name_disp = run["name"][:32] + "..." if len(run["name"]) > 35 else run["name"]
            file_disp = run["file"][:32] + "..." if len(run["file"]) > 35 else run["file"]
            print(f"{name_disp:<35} | {file_disp:<35} | {run['added']:<6} | {run['removed']:<7} | {run['modified']:<8} | {comment_status:<9}")
        print("-" * 110 + "\n")

    if failed_runs:
        print("⚠️ Skipped/Failed Runs Detail:")
        print("-" * 80)
        for run in failed_runs:
            print(f"File:  {run['file']}")
            print(f"Error: {run['error']}")
            print("-" * 80)
        print()
    print("=" * 80 + "\n")

    return 1 if has_failures else 0


def run_pipeline_diff(argv: Optional[List[str]] = None) -> int:
    """Executes the pipeline diff compilation, reconciliation, rendering, and reporting.

    Args:
        argv: Optional list of command-line arguments.

    Returns:
        Status exit code (0 for success, non-zero for error).
    """
    parser = argparse.ArgumentParser(
        description="Diff KFP pipeline DAG specs and report structure changes."
    )
    parser.add_argument(
        "--before",
        "-b",
        help="Path to baseline pipeline spec (.yaml, .json) or DSL (.py) file.",
    )
    parser.add_argument(
        "--after",
        "-a",
        help="Path to target pipeline spec (.yaml, .json) or DSL (.py) file.",
    )
    parser.add_argument(
        "--pipelines-dir",
        "-d",
        help="Optional path to directory containing pipelines to scan and compare automatically.",
    )
    parser.add_argument(
        "--git-base-branch",
        default=os.environ.get("GITHUB_BASE_REF", "main"),
        help="Optional Git baseline branch (defaults to GITHUB_BASE_REF or 'main').",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional path to write the markdown report locally.",
    )
    parser.add_argument(
        "--github-token",
        "-t",
        help="GitHub Actions or Personal Access Token for PR commenting.",
    )
    parser.add_argument(
        "--github-repo",
        "-r",
        help="GitHub Repository name formatted as 'owner/repo'.",
    )
    parser.add_argument(
        "--github-pr",
        "-p",
        type=int,
        help="The target Pull Request ID number to comment on.",
    )
    parser.add_argument(
        "--github-api-url",
        default="https://api.github.com",
        help="The base URL of the GitHub REST API (defaults to https://api.github.com).",
    )

    args = parser.parse_args(argv)

    # Validate arguments input mode
    if not args.pipelines_dir and (not args.before or not args.after):
        parser.error("Either specify both --before and --after, or specify --pipelines-dir.")

    if args.pipelines_dir:
        base_branch = args.git_base_branch or "main"
        return scan_and_diff_directory(
            pipelines_dir=args.pipelines_dir,
            base_branch=base_branch,
            github_pr=args.github_pr,
            github_repo=args.github_repo,
            github_token=args.github_token,
            github_api_url=args.github_api_url,
            output_path=args.output,
        )

    try:
        print(f"🔍 Parsing baseline pipeline: {args.before}")
        before_name, before_tasks = parse_pipeline_meta_and_tasks(args.before)
        before_params = parse_pipeline_parameters(args.before)

        print(f"🔍 Parsing target pipeline: {args.after}")
        after_name, after_tasks = parse_pipeline_meta_and_tasks(args.after)
        after_params = parse_pipeline_parameters(args.after)

        print("⚖️ Diffing pipeline DAG representations...")
        diff = diff_pipelines(
            before_tasks,
            after_tasks,
            before_name,
            after_name,
            before_params=before_params,
            after_params=after_params,
        )

        print("📝 Generating markdown and Mermaid visual representation...")
        report = generate_markdown_report(diff, args.github_pr)

        # Output to local file if path provided
        if args.output:
            print(f"💾 Writing markdown report to file: {args.output}")
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report)

        # Print high level stats to stdout
        print("\n📈 Diff Results Summary:")
        print(f"  🟢 Added tasks: {len(diff.added_nodes)}")
        print(f"  🔴 Removed tasks: {len(diff.removed_nodes)}")
        print(f"  🟡 Modified tasks: {len(diff.modified_nodes)}")
        print(f"  ⚪ Unchanged tasks: {len(diff.unchanged_nodes)}")
        print(f"  🟢 Added edges: {len(diff.added_edges)}")
        print(f"  🔴 Removed edges: {len(diff.removed_edges)}")
        print(f"  ⚪ Unchanged edges: {len(diff.unchanged_edges)}\n")

        # Handle GitHub sticky comment posting
        has_token = bool(args.github_token)
        has_repo = bool(args.github_repo)
        has_pr = bool(args.github_pr)

        if has_token or has_repo or has_pr:
            if has_token and has_repo and has_pr:
                print(f"📬 Posting/Updating sticky comment on PR #{args.github_pr} in {args.github_repo}...")
                unique_anchor = f"<!-- kfp-pipeline-diff-sticky-comment-anchor-{diff.after_name} -->"
                post_or_update_sticky_comment(
                    repo=args.github_repo,
                    pr_number=args.github_pr,
                    token=args.github_token,
                    body=report,
                    api_url=args.github_api_url,
                    anchor=unique_anchor,
                )
                print("✨ Comment posted successfully!")
            else:
                missing = []
                if not has_token:
                    missing.append("--github-token")
                if not has_repo:
                    missing.append("--github-repo")
                if not has_pr:
                    missing.append("--github-pr")
                print(
                    f"⚠️ Skipping comment posting. Missing parameters for GitHub API: {', '.join(missing)}."
                )

        return 0

    except Exception as e:
        print(f"❌ Error occurred while diffing pipelines: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main() -> None:
    """Entrypoint function for the console_scripts registry."""
    sys.exit(run_pipeline_diff())


if __name__ == "__main__":
    main()
