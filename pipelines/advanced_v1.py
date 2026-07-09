from kfp import dsl
from typing import NamedTuple

@dsl.component
def ingest_data_op(source_url: str) -> str:
    return f"raw_data_from_{source_url}"

@dsl.component
def validate_schema_op(dataset: str) -> str:
    return "validated_dataset"

@dsl.component
def split_train_test_op(dataset: str) -> NamedTuple("Outputs", [("train", str), ("test", str)]):
    return "train_set", "test_set"

@dsl.component
def train_xgboost_op(train_data: str, max_depth: int = 6) -> str:
    return "xgb_model_bin"

@dsl.component
def train_lightgbm_op(train_data: str, num_leaves: int = 31) -> str:
    return "lgb_model_bin"

@dsl.component
def train_catboost_op(train_data: str, iterations: int = 500) -> str:
    return "cat_model_bin"

@dsl.component
def evaluate_models_op(
    xgb_model: str,
    lgb_model: str,
    cat_model: str,
    test_data: str,
) -> str:
    return "evaluation_summary_json"

@dsl.component
def register_champion_model_op(eval_summary: str) -> str:
    return "champion_registered_uri"

@dsl.component
def alert_slack_op(message: str) -> str:
    return "slack_notification_sent"

@dsl.pipeline(name="advanced-multi-branch-ml-ops")
def complex_ml_pipeline(
    source_url: str = "https://raw.githubusercontent.com/datasets/baseline.csv"
):
    # Stage 1: Data Ingestion
    ingest_task = ingest_data_op(source_url=source_url)
    
    # Stage 2: Quality Checks
    validate_task = validate_schema_op(dataset=ingest_task.output)
    
    # Stage 3: Splitting
    split_task = split_train_test_op(dataset=validate_task.output)
    
    # Stage 4: Tri-branch Parallel Model Training (XGB, LGB, Cat)
    xgb_task = train_xgboost_op(train_data=split_task.outputs["train"])
    lgb_task = train_lightgbm_op(train_data=split_task.outputs["train"])
    cat_task = train_catboost_op(train_data=split_task.outputs["train"])
    
    # Stage 5: Broad Merge (Evaluation depends on all three trained models + testing chunk)
    eval_task = evaluate_models_op(
        xgb_model=xgb_task.output,
        lgb_model=lgb_task.output,
        cat_model=cat_task.output,
        test_data=split_task.outputs["test"]
    )
    
    # Stage 6: Conditional Promotion & Alerting
    promote_task = register_champion_model_op(eval_summary=eval_task.output)
    alert_task = alert_slack_op(message=promote_task.output)
