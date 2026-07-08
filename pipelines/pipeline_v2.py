from kfp import dsl

@dsl.component
def preprocess_op(text: str) -> str:
    return text.lower().strip()

@dsl.component
def train_op(data: str, epochs: int) -> str:
    return f"Model trained on {data} for {epochs} epochs"

@dsl.component
def evaluate_op(model: str) -> float:
    return 0.95

@dsl.pipeline(name="sample-training-pipeline")
def my_pipeline(input_text: str = "  Some Text  "):
    preprocess_task = preprocess_op(text=input_text)
    # Modified training epochs from 10 to 20
    train_task = train_op(data=preprocess_task.output, epochs=20)
    # Added evaluate task
    eval_task = evaluate_op(model=train_task.output)
