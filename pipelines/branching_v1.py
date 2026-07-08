from kfp import dsl

@dsl.component
def preprocess_op(data_path: str) -> str:
    return f"cleaned_{data_path}"

@dsl.component
def train_xgboost_op(dataset: str) -> str:
    return "xgboost_model"

@dsl.component
def train_rf_op(dataset: str) -> str:
    return "random_forest_model"

@dsl.component
def ensemble_op(model_a: str, model_b: str) -> str:
    return f"ensembled_{model_a}_{model_b}"

@dsl.pipeline(name="branching-ml-pipeline")
def branching_pipeline(data_path: str = "s3://my-bucket/raw-data.csv"):
    clean_task = preprocess_op(data_path=data_path)
    
    # Train two models in parallel
    xgb_task = train_xgboost_op(dataset=clean_task.output)
    rf_task = train_rf_op(dataset=clean_task.output)
    
    # Ensemble them
    ensemble_task = ensemble_op(model_a=xgb_task.output, model_b=rf_task.output)
