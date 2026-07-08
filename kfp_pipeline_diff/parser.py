"""Parser module for KFP Pipeline Specs and PipelineJobs.

Handles on-the-fly compilation of python DSL files as well as loading YAML/JSON files.
"""

import importlib.util
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set
import yaml

class TaskNode:
    """Represents a compiled KFP task with its metadata, inputs, and dependencies."""

    def __init__(
        self,
        name: str,
        component_ref: str,
        dependent_tasks: List[str],
        image: Optional[str] = None,
        command: Optional[List[str]] = None,
        args: Optional[List[str]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        is_subdag: bool = False,
    ):
        self.name = name
        self.component_ref = component_ref
        self.dependent_tasks = dependent_tasks or []
        self.image = image
        self.command = command or []
        self.args = args or []
        self.inputs = inputs or {}
        self.is_subdag = is_subdag

    def __repr__(self) -> str:
        return f"TaskNode(name={self.name}, component_ref={self.component_ref}, image={self.image})"


def compile_dsl_to_dict(py_path: str) -> Dict[str, Any]:
    """Compiles a Python KFP DSL file into a pipeline specification dictionary.

    Args:
        py_path: Absolute or relative path to the Python script.

    Returns:
        The compiled pipeline spec as a dictionary.

    Raises:
        ValueError: If no pipeline function is found.
        RuntimeError: If execution/compilation fails.
    """
    module_name = os.path.splitext(os.path.basename(py_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, py_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load python file spec for {py_path}")
    
    module = importlib.util.module_from_spec(spec)
    dir_path = os.path.dirname(os.path.abspath(py_path))
    if dir_path not in sys.path:
        sys.path.insert(0, dir_path)
        
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"Failed to execute pipeline script {py_path}: {e}")
    finally:
        if dir_path in sys.path:
            sys.path.remove(dir_path)

    # Find the pipeline function
    pipeline_func = None
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if callable(obj):
            if getattr(obj, "_is_pipeline_func", False) or hasattr(obj, "_pipeline_spec"):
                pipeline_func = obj
                break
    
    if pipeline_func is None:
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if callable(obj) and not attr_name.startswith("_"):
                if "pipeline" in attr_name.lower():
                    pipeline_func = obj
                    break

    if pipeline_func is None:
        raise ValueError(f"No pipeline function found in {py_path}. Ensure it is decorated with @dsl.pipeline")

    try:
        from kfp import compiler
    except ImportError:
        raise ImportError("The 'kfp' package is required to compile Python DSL files on-the-fly.")

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        compiler.Compiler().compile(pipeline_func=pipeline_func, package_path=tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            compiled_content = yaml.safe_load(f)
        return compiled_content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def load_pipeline_spec_from_file(file_path: str) -> Dict[str, Any]:
    """Loads a KFP pipeline spec or PipelineJob from a .py, .yaml, or .json file.

    Args:
        file_path: Path to the file.

    Returns:
        The pipeline spec or PipelineJob as a dictionary.
    """
    if file_path.endswith(".py"):
        return compile_dsl_to_dict(file_path)
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            return yaml.safe_load(content)
        except Exception as e:
            raise ValueError(f"Failed to parse {file_path} as JSON or YAML: {e}")


def extract_pipeline_spec(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts the pipelineSpec dictionary from raw parsed file data.

    Args:
        data: Raw dict parsed from JSON or YAML.

    Returns:
        The raw pipelineSpec dict if found, otherwise the original dict.
    """
    if "pipelineSpec" in data:
        return data["pipelineSpec"]
    if "spec" in data and isinstance(data["spec"], dict) and "pipelineSpec" in data["spec"]:
        return data["spec"]["pipelineSpec"]
    return data


def parse_pipeline_tasks(file_path: str) -> Dict[str, TaskNode]:
    """Parses a pipeline file and extracts its task execution DAG nodes.

    Args:
        file_path: Path to the .py, .yaml, or .json pipeline file.

    Returns:
        A dictionary mapping task names to TaskNode instances.
    """
    raw_data = load_pipeline_spec_from_file(file_path)
    pipeline_spec = extract_pipeline_spec(raw_data)

    root = pipeline_spec.get("root", {})
    dag = root.get("dag", {})
    tasks_data = dag.get("tasks", {})

    # In KFP, sometimes tasks is a list of dicts, or a dict keyed by task name
    normalized_tasks: Dict[str, Dict[str, Any]] = {}
    if isinstance(tasks_data, list):
        for t in tasks_data:
            name = t.get("taskInfo", {}).get("name") or t.get("name")
            if name:
                normalized_tasks[name] = t
    elif isinstance(tasks_data, dict):
        for k, v in tasks_data.items():
            name = v.get("taskInfo", {}).get("name") or k
            normalized_tasks[name] = v

    components = pipeline_spec.get("components", {})
    deployment_spec = pipeline_spec.get("deploymentSpec", {})
    executors = deployment_spec.get("executors", {})

    parsed_nodes: Dict[str, TaskNode] = {}

    for task_name, task_def in normalized_tasks.items():
        component_ref = task_def.get("componentRef", {}).get("name", "")
        dependent_tasks = task_def.get("dependentTasks", [])

        # Inputs resolution
        inputs: Dict[str, Any] = {}
        task_inputs = task_def.get("inputs", {})
        if "parameters" in task_inputs:
            inputs["parameters"] = task_inputs["parameters"]
        if "artifacts" in task_inputs:
            inputs["artifacts"] = task_inputs["artifacts"]

        # Resolve component type & executor
        is_subdag = False
        image = None
        command = None
        args = None

        if component_ref and component_ref in components:
            component_def = components[component_ref]
            if "dag" in component_def:
                is_subdag = True
            
            executor_label = component_def.get("executorLabel")
            if executor_label and executor_label in executors:
                executor_def = executors[executor_label]
                container = executor_def.get("container", {})
                if container:
                    image = container.get("image")
                    command = container.get("command")
                    args = container.get("args")

        node = TaskNode(
            name=task_name,
            component_ref=component_ref,
            dependent_tasks=dependent_tasks,
            image=image,
            command=command,
            args=args,
            inputs=inputs,
            is_subdag=is_subdag,
        )
        parsed_nodes[task_name] = node

    return parsed_nodes

