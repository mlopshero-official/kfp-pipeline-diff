from kfp import dsl

@dsl.component
def preprocess_op(text: str) -> str:
    return text.lower().strip()

@dsl.component
def train_op(data: str, epochs: int) -> str:
    return f"Model trained on {data} for {epochs} epochs"

@dsl.pipeline(name="sample-training-pipeline")
def my_pipeline(input_text: str = "  Some Text  "):
    preprocess_task = preprocess_op(text=input_text)
    train_task = train_op(data=preprocess_task.output, epochs=10)
