import os
import json
import tempfile
from kfp_pipeline_diff.parser import (
    parse_pipeline_meta_and_tasks,
    extract_pipeline_name,
    TaskNode,
)
from kfp_pipeline_diff.diff import diff_pipelines
from kfp_pipeline_diff.renderer import generate_mermaid_chart, generate_markdown_report


def test_special_character_sanitization():
    # Tasks with hyphens, periods, spaces, underscores, and brackets
    before_task = TaskNode("my-special.task_0 [run]", "comp_1", [])
    after_task = TaskNode("my-special.task_0 [run]", "comp_1", [], image="python:latest") # modified

    before = {"my-special.task_0 [run]": before_task}
    after = {"my-special.task_0 [run]": after_task}

    diff = diff_pipelines(before, after)
    chart = generate_mermaid_chart(diff)

    # Confirm that it uses the sanitized index-based node ID (e.g. node0) and places raw name in quotes
    assert "node0" in chart
    # Mermaid flowchart should define the node node0 with quotes around label
    assert 'node0["[*] my-special.task_0 [run]"]' in chart


def test_pipeline_name_shift():
    before_task = TaskNode("task1", "comp1", [])
    after_task = TaskNode("task1", "comp1", [])

    before = {"task1": before_task}
    after = {"task1": after_task}

    # Test identical name
    diff_same = diff_pipelines(before, after, before_name="my-cool-pipeline", after_name="my-cool-pipeline")
    report_same = generate_markdown_report(diff_same)
    assert "**Pipeline**: `my-cool-pipeline`" in report_same
    assert "Pipeline Name Shift" not in report_same

    # Test changed name (metadata shift)
    diff_shift = diff_pipelines(before, after, before_name="old-pipeline-v1", after_name="new-pipeline-v2")
    report_shift = generate_markdown_report(diff_shift)
    assert "🔄 **Pipeline Name Shift**: `old-pipeline-v1` ➜ `new-pipeline-v2`" in report_shift


def test_multi_version_kfp_compatibility():
    # A dummy KFP Spec representing modern dict executors & components
    legacy_json_v2_spec = {
        "pipelineSpec": {
            "pipelineInfo": {"name": "multi-version-pipeline"},
            "root": {
                "dag": {
                    "tasks": [
                        {
                            "name": "data-prep",
                            "componentRef": {"name": "comp-prep"},
                        }
                    ]
                }
            },
            # components & executors as LISTS instead of standard dict mappings (seen in draft versions / early specs)
            "components": [
                {
                    "name": "comp-prep",
                    "executorLabel": "exec-prep"
                }
            ],
            "deploymentSpec": {
                "executors": [
                    {
                        "name": "exec-prep",
                        "container": {
                            "image": "alpine:latest"
                        }
                    }
                ]
            }
        }
    }

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
        json.dump(legacy_json_v2_spec, f)
        temp_path = f.name

    try:
        pipeline_name, tasks = parse_pipeline_meta_and_tasks(temp_path)
        
        # Confirm fallback extraction
        assert pipeline_name == "multi-version-pipeline"
        
        # Confirm that list structure components and executors were parsed successfully
        assert "data-prep" in tasks
        node = tasks["data-prep"]
        assert node.component_ref == "comp-prep"
        assert node.image == "alpine:latest"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_pipeline_name_extraction_fallbacks():
    # Test fallback name in spec root
    spec_fallback_root = {
        "pipelineSpec": {
            "name": "root-level-spec-name",
            "root": {}
        }
    }
    assert extract_pipeline_name(spec_fallback_root["pipelineSpec"]) == "root-level-spec-name"

    # Test fallback name in DAG root
    spec_fallback_dag = {
        "pipelineSpec": {
            "root": {
                "displayName": "dag-level-display-name"
            }
        }
    }
    assert extract_pipeline_name(spec_fallback_dag["pipelineSpec"]) == "dag-level-display-name"

    # Fallback to default
    assert extract_pipeline_name({}) == "unnamed-pipeline"


def test_kfp_v2_component_types_parsing():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    comp_path = os.path.join(base_dir, "pipelines", "components_v1.py")
    
    pipeline_name, tasks = parse_pipeline_meta_and_tasks(comp_path)
    
    assert pipeline_name == "all-component-types-pipeline"
    assert len(tasks) == 3
    
    # 1. Assert Lightweight Python Component
    assert "preprocess-op" in tasks
    python_task = tasks["preprocess-op"]
    assert python_task.component_ref == "comp-preprocess-op"
    assert python_task.image == "python:3.11"
    
    # 2. Assert KFP Importer Component
    assert "importer" in tasks
    importer_task = tasks["importer"]
    assert importer_task.image == "kfp.dsl.importer"
    assert importer_task.command == ["importer"]
    assert any("artifact_uri=" in arg for arg in importer_task.args)
    assert any("type_schema=" in arg for arg in importer_task.args)
    
    # 3. Assert Containerized Component
    assert "container-train-op" in tasks
    container_task = tasks["container-train-op"]
    assert container_task.component_ref == "comp-container-train-op"
    assert container_task.image == "tensorflow/tensorflow:latest-gpu"
    assert container_task.command == ["python3", "-m", "trainer.task"]
    assert container_task.args == [
        "--dataset", 
        "{{$.inputs.parameters['dataset']}}", 
        "--model_path", 
        "{{$.outputs.artifacts['model'].path}}", 
        "--epochs", 
        "{{$.inputs.parameters['epochs']}}"
    ]

