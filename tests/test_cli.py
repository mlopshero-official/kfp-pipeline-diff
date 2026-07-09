import os
from kfp_pipeline_diff.cli import scan_and_diff_directory

def test_scan_and_diff_directory_basic():
    # Use our own pipelines/ directory and main branch for local scan testing
    # Passing None for GitHub parameters to avoid actual API calls
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pipelines_dir = os.path.join(base_dir, "pipelines")
    
    # We expect this to run and scan 8 pipelines, writing output if requested
    # We pass exit status check
    status = scan_and_diff_directory(
        pipelines_dir=pipelines_dir,
        base_branch="main",
        github_pr=None,
        github_repo=None,
        github_token=None,
        github_api_url="https://api.github.com",
        output_path=None,
    )
    
    # It should complete with 0 failures now that components_modified.py is fixed!
    assert status == 0
