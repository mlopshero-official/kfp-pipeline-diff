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
