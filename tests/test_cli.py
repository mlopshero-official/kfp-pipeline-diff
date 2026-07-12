import os
import tempfile
import pytest
from kfp_pipeline_diff.cli import scan_and_diff_directory, run_pipeline_diff

def test_scan_and_diff_directory_basic():
    # Use our own pipelines/ directory and main branch for local scan testing
    # Passing None for GitHub parameters to avoid actual API calls
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pipelines_dir = os.path.join(base_dir, "pipelines")
    
    # We expect this to run and scan pipelines, returning 0 for success
    status = scan_and_diff_directory(
        pipelines_dir=pipelines_dir,
        base_branch="main",
        github_pr=None,
        github_repo=None,
        github_token=None,
        github_api_url="https://api.github.com",
        output_path=None,
    )
    assert status == 0


def test_scan_and_diff_directory_missing():
    status = scan_and_diff_directory(
        pipelines_dir="non-existent-dir-foo-bar-baz",
        base_branch="main",
        github_pr=None,
        github_repo=None,
        github_token=None,
        github_api_url="https://api.github.com",
        output_path=None,
    )
    assert status == 1


def test_cli_argument_parsing_errors():
    # Missing both --before/--after and --pipelines-dir
    with pytest.raises(SystemExit):
        run_pipeline_diff([])

    # Only --before specified
    with pytest.raises(SystemExit):
        run_pipeline_diff(["--before", "file.py"])


def test_cli_single_pair_mode_success():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    v1_path = os.path.join(base_dir, "pipelines", "pipeline_v1.py")
    v2_path = os.path.join(base_dir, "pipelines", "pipeline_v2.py")

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = os.path.join(tmp_dir, "report.md")
        
        status = run_pipeline_diff([
            "--before", v1_path,
            "--after", v2_path,
            "--output", out_file
        ])
        
        assert status == 0
        assert os.path.exists(out_file)
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "## 🧬 KFP DAG Structure Diff" in content
        assert "evaluate-op" in content or "evaluate_op" in content


def test_cli_single_pair_mode_parse_error():
    # Calling diff with a totally invalid file should return 1
    status = run_pipeline_diff([
        "--before", "non-existent-file.py",
        "--after", "non-existent-file-2.py"
    ])
    assert status == 1
