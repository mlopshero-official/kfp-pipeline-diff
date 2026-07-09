from kfp import dsl
from kfp.dsl import Dataset, Input, Model, Output

# 1. Standard Lightweight Python Component (Modifying baseline pre-processing)
@dsl.component
def preprocess_op(text: str) -> str:
    # Slightly updated return string representation
    return text.lower().strip() + "_processed"

# 2. Containerized Component (Changing configuration parameters and image tag)
@dsl.container_component
def container_train_op(
    dataset: str,
    model: Output[Model],
    epochs: int = 20, # baseline default epochs modified from 10 to 20
):
    return dsl.ContainerSpec(
        image="tensorflow/tensorflow:2.15.0-gpu", # Base Docker image tag updated!
        command=["python3", "trainer/task.py"],  # command list slightly adjusted
        args=[
            "--dataset", dataset,
            "--model_path", model.path,
            "--epochs", epochs,
        ]
    )

@dsl.pipeline(name="sample-training-pipeline")
def complex_pipeline(input_text: str = "  Some Text  "):
    # Target name of the pipeline changed from "sample-training-pipeline" to something else!
    pass
