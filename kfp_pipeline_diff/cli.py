"""CLI module for orchestrating the KFP pipeline parsing, diffing, rendering, and comment posting.
"""

import argparse
import sys
from typing import List, Optional

from .diff import diff_pipelines
from .github import post_or_update_sticky_comment
from .parser import parse_pipeline_tasks
from .renderer import generate_markdown_report


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
        required=True,
        help="Path to baseline pipeline spec (.yaml, .json) or DSL (.py) file.",
    )
    parser.add_argument(
        "--after",
        "-a",
        required=True,
        help="Path to target pipeline spec (.yaml, .json) or DSL (.py) file.",
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

    try:
        print(f"🔍 Parsing baseline pipeline: {args.before}")
        before_tasks = parse_pipeline_tasks(args.before)

        print(f"🔍 Parsing target pipeline: {args.after}")
        after_tasks = parse_pipeline_tasks(args.after)

        print("⚖️ Diffing pipeline DAG representations...")
        diff = diff_pipelines(before_tasks, after_tasks)

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
                post_or_update_sticky_comment(
                    repo=args.github_repo,
                    pr_number=args.github_pr,
                    token=args.github_token,
                    body=report,
                    api_url=args.github_api_url,
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
