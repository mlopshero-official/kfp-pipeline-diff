from kfp import dsl
from kfp.dsl import Dataset, Input, Model, Output

# 1. Standard Lightweight Python Component
@dsl.component
def preprocess_op(text: str) -> str:
    return text.lower().strip()

# 2. Containerized Component
@dsl.container_component
def container_train_op(
    dataset: str,
    model: Output[Model],
    epochs: int = 10,
):
    return dsl.ContainerSpec(
        image="tensorflow/tensorflow:latest-gpu",
        command=["python3", "-m", "trainer.task"],
        args=[
            "--dataset", dataset,
            "--model_path", model.path,
            "--epochs", epochs,
        ]
    )

@dsl.pipeline(name="all-component-types-pipeline")
def complex_pipeline(input_text: str = "  hello world  "):
    # (a) Invoke Lightweight Python Component
    prep_task = preprocess_op(text=input_text)
    
    # (b) Invoke KFP Importer Component
    import_task = dsl.importer(
        artifact_uri="gs://mlops-hero-bucket/reference_dataset.csv",
        artifact_class=Dataset,
        reimport=True,
    )
    
    # (c) Invoke Containerized Component
    train_task = container_train_op(
        dataset=prep_task.output,
        epochs=15,
    )
