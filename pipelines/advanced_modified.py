from kfp import dsl
from typing import NamedTuple

@dsl.component
def ingest_data_op(source_url: str, format_type: str = "parquet") -> str: # Added new format parameter
    return f"raw_data_from_{source_url}_as_{format_type}"

@dsl.component
def validate_schema_op(dataset: str) -> str:
    return "validated_dataset"

@dsl.component
def split_train_test_op(dataset: str) -> NamedTuple("Outputs", [("train", str), ("test", str)]):
    return "train_set", "test_set"

# XGBoost remains the same
@dsl.component
def train_xgboost_op(train_data: str, max_depth: int = 6) -> str:
    return "xgb_model_bin"

# LightGBM parameter was modified
@dsl.component
def train_lightgbm_op(train_data: str, num_leaves: int = 64) -> str: # modified num_leaves from 31 to 64
    return "lgb_model_bin"

# CatBoost component was completely deleted!

# Added PyTorch Deep Learning training component! (New parallel branch!)
@dsl.component
def train_pytorch_op(train_data: str, epochs: int = 50, batch_size: int = 128) -> str:
    return "pytorch_model_pt"

# Broad Merge changed components - replaces cat_model with pytorch_model
@dsl.component
def evaluate_models_op(
    xgb_model: str,
    lgb_model: str,
    pytorch_model: str, # changed from cat_model
    test_data: str,
) -> str:
    return "evaluation_summary_json"

@dsl.component
def register_champion_model_op(eval_summary: str) -> str:
    return "champion_registered_uri"

# Added a new parallel Post-processing & Model Bias validation step!
@dsl.component
def check_model_bias_op(model_uri: str, dataset: str) -> str:
    return "bias_report_verified"

@dsl.component
def alert_slack_op(message: str) -> str:
    return "slack_notification_sent"

@dsl.pipeline(name="advanced-multi-branch-ml-ops")
def complex_ml_pipeline(
    source_url: str = "https://raw.githubusercontent.com/datasets/production.csv" # modified pipeline default
):
    # Stage 1: Data Ingestion (Modified parameters!)
    ingest_task = ingest_data_op(source_url=source_url, format_type="csv")
    
    # Stage 2: Quality Checks
    validate_task = validate_schema_op(dataset=ingest_task.output)
    
    # Stage 3: Splitting
    split_task = split_train_test_op(dataset=validate_task.output)
    
    # Stage 4: Parallel Model Training (XGBoost, LightGBM, and Neural Network)
    xgb_task = train_xgboost_op(train_data=split_task.outputs["train"])
    lgb_task = train_lightgbm_op(train_data=split_task.outputs["train"]) # parameters modified!
    
    # CatBoost training was removed!
    
    # PyTorch training was added! (New dependency)
    pytorch_task = train_pytorch_op(train_data=split_task.outputs["train"], epochs=100)
    
    # Stage 5: Evaluation broad merge depends on PyTorch now instead of CatBoost
    eval_task = evaluate_models_op(
        xgb_model=xgb_task.output,
        lgb_model=lgb_task.output,
        pytorch_model=pytorch_task.output, # Edge connection modified!
        test_data=split_task.outputs["test"]
    )
    
    # Stage 6: Champion registration
    promote_task = register_champion_model_op(eval_summary=eval_task.output)
    
    # Added parallel check task (New node, splits execution flow)
    bias_task = check_model_bias_op(
        model_uri=promote_task.output, 
        dataset=split_task.outputs["test"]
    )
    
    # Slack alerting depends on champion + bias check completes! (Dependencies changed!)
    alert_task = alert_slack_op(message=promote_task.output)
    alert_task.after(bias_task) # added explicit edge execution block!
