from kfp import dsl

@dsl.component
def preprocess_op(data_path: str) -> str:
    return f"cleaned_{data_path}"

@dsl.component
def train_rf_op(dataset: str) -> str:
    return "random_forest_model"

@dsl.component
def train_nn_op(dataset: str, epochs: int = 100) -> str:
    return "neural_network_model"

@dsl.component
def ensemble_op(model_a: str, model_b: str) -> str:
    return f"ensembled_{model_a}_{model_b}"

@dsl.pipeline(name="branching-ml-pipeline")
def branching_pipeline(data_path: str = "s3://my-bucket/raw-data.csv"):
    # Preprocess remains the same
    clean_task = preprocess_op(data_path=data_path)
    
    # XGBoost train task was removed
    
    # Random Forest train task remains unchanged
    rf_task = train_rf_op(dataset=clean_task.output)
    
    # Added Neural Network train task (New component/task!)
    nn_task = train_nn_op(dataset=clean_task.output, epochs=150)
    
    # Ensemble them (Dependencies/edges changed: xgb removed, nn added!)
    ensemble_task = ensemble_op(model_a=rf_task.output, model_b=nn_task.output)
