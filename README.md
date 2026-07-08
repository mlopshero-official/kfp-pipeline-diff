# KFP Pipeline Diff (kfp-pipeline-diff) 🧬

A lightweight, robust, and dependency-free automated command-line tool and GitHub composite action to parse, diff, and visualize changes in **Kubeflow Pipelines (KFP) v2** DAG structures, rendering a unified, color-coded Mermaid diagram inside sticky, auto-updating GitHub PR comments.

---

## 🌟 Features

- **Unified Color-Coded Diagram**: Combines the baseline ("before") and target ("after") state into a single visual DAG with clear status styling:
  - 🟢 **Added** (Green outline)
  - 🔴 **Removed** (Red dashed outline)
  - 🟡 **Modified** (Amber outline)
  - ⚪ **Unchanged** (Gray outline)
- **Automatic DSL Compilation**: Compiles `.py` pipeline DSL files on the fly using the native KFP compiler, or parses pre-compiled `.yaml` or `.json` IR specifications.
- **Detailed Property Diffing**: Pinpoints exact changes in container images, command arguments, component references, and input parameters.
- **Zero-Dependency Action**: Runs entirely on Python's built-in modules (utilizing `urllib` for comments), meaning it loads in seconds with zero startup friction.
- **Sticky GitHub PR Comments**: Posts a markdown report to the PR, automatically updating on every push so reviewers always see the latest topology.

---

## 🛠️ Installation & Local Usage

To use the tool locally, clone the repository and install the package with standard development dependencies:

```bash
git clone https://github.com/soubenz94/kfp-pipeline-diff.git
cd kfp-pipeline-diff
pip install .
```

### CLI Command Options

```bash
kfp-pipeline-diff \
  --before pipeline_v1.yaml \
  --after pipeline_v2.py \
  --output report.md
```

#### Complete CLI Arguments:
- `--before` / `-b` (Required): Path to baseline compiled spec (.yaml, .json) or Python DSL script (.py).
- `--after` / `-a` (Required): Path to target compiled spec (.yaml, .json) or Python DSL script (.py).
- `--output` / `-o` (Optional): Path to write the Markdown report locally.
- `--github-token` / `-t` (Optional): GitHub Token for writing comment outputs.
- `--github-repo` / `-r` (Optional): Repository formatted as `owner/repo`.
- `--github-pr` / `-p` (Optional): target Pull Request ID number.

---

## 🐙 Usage as a GitHub Action

Include KFP Pipeline Diff directly into your CI/CD workflows (e.g. `.github/workflows/kfp-diff.yml`) to generate topological diffs on every Pull Request update:

```yaml
name: KFP Pipeline Change Visualizer

on:
  pull_request:
    paths:
      - 'pipelines/**'

jobs:
  visualize-diff:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write # Required to post sticky comments
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Render DAG Diff
        uses: soubenz94/kfp-pipeline-diff@main
        with:
          before: "pipelines/baseline.yaml"
          after: "pipelines/target.py"
          github-token: "${{ secrets.GITHUB_TOKEN }}"
```

---

## 🧪 Testing

The codebase includes a fully covered test suite running on `pytest`. Run tests locally with:

```bash
PYTHONPATH=. pytest tests/
```

---

## 📄 License

This project is licensed under the MIT License.
