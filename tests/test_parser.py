import json
import os
import tempfile
from kfp_pipeline_diff.parser import (
    load_pipeline_spec_from_file,
    extract_pipeline_spec,
    parse_pipeline_tasks,
    TaskNode,
)

# Define mock KFP v2 pipeline definition
MOCK_PIPELINE = {
    "pipelineSpec": {
        "pipelineInfo": {"name": "test-pipeline"},
        "root": {
            "dag": {
                "tasks": {
                    "step-1": {
                        "taskInfo": {"name": "step-1"},
                        "componentRef": {"name": "comp-step-1"},
                    },
                    "step-2": {
                        "taskInfo": {"name": "step-2"},
                        "componentRef": {"name": "comp-step-2"},
                        "dependentTasks": ["step-1"],
                    }
                }
            }
        },
        "components": {
            "comp-step-1": {"executorLabel": "exec-step-1"},
            "comp-step-2": {"executorLabel": "exec-step-2"},
        },
        "deploymentSpec": {
            "executors": {
                "exec-step-1": {
                    "container": {
                        "image": "alpine:latest",
                        "command": ["echo"],
                        "args": ["hello"],
                    }
                },
                "exec-step-2": {
                    "container": {
                        "image": "ubuntu:20.04",
                        "command": ["echo"],
                        "args": ["world"],
                    }
                }
            }
        }
    }
}


def test_extract_pipeline_spec():
    # Test when raw pipelineSpec is root
    data = {"pipelineSpec": {"foo": "bar"}}
    assert extract_pipeline_spec(data) == {"foo": "bar"}

    # Test when spec is container (like PipelineJob custom resource)
    data = {"spec": {"pipelineSpec": {"foo": "bar"}}}
    assert extract_pipeline_spec(data) == {"foo": "bar"}

    # Test fallback
    data = {"foo": "bar"}
    assert extract_pipeline_spec(data) == {"foo": "bar"}


def test_parse_pipeline_tasks():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
        json.dump(MOCK_PIPELINE, f)
        temp_path = f.name

    try:
        nodes = parse_pipeline_tasks(temp_path)
        assert len(nodes) == 2
        assert "step-1" in nodes
        assert "step-2" in nodes

        node1 = nodes["step-1"]
        assert node1.name == "step-1"
        assert node1.component_ref == "comp-step-1"
        assert node1.image == "alpine:latest"
        assert node1.command == ["echo"]
        assert node1.args == ["hello"]
        assert node1.dependent_tasks == []

        node2 = nodes["step-2"]
        assert node2.name == "step-2"
        assert node2.component_ref == "comp-step-2"
        assert node2.image == "ubuntu:20.04"
        assert node2.command == ["echo"]
        assert node2.args == ["world"]
        assert node2.dependent_tasks == ["step-1"]
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
