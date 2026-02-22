"""
MLflow Experiment Tracking Integration

Provides experiment tracking, model registry, and artifact management
for the AI log filter training pipeline.
"""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

MLFLOW_AVAILABLE = False
try:
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost

    MLFLOW_AVAILABLE = True
except ImportError:
    logger.warning("MLflow not available. Install with: pip install mlflow")


@dataclass
class ExperimentConfig:
    """Configuration for MLflow experiment tracking."""

    tracking_uri: str | None = None
    experiment_name: str = "ai-log-filter"
    run_name: str | None = None
    tags: dict[str, str] | None = None
    log_models: bool = True
    log_dataset_stats: bool = True


class ExperimentTracker:
    """
    MLflow experiment tracker for training pipelines.

    Features:
    - Automatic experiment creation
    - Parameter logging
    - Metric tracking
    - Model versioning
    - Artifact management

    Example:
        tracker = ExperimentTracker(experiment_name="log-classifier-v3")

        with tracker.start_run("training-run-001"):
            tracker.log_params({"model": "xgboost", "learning_rate": 0.1})
            tracker.log_metrics({"accuracy": 0.95, "f1": 0.93})
            tracker.log_model(model, "classifier")
    """

    def __init__(self, config: ExperimentConfig | None = None):
        self.config = config or ExperimentConfig()
        self._run = None
        self._active = False

        if not MLFLOW_AVAILABLE:
            logger.warning("MLflow not available - tracking disabled")
            return

        if self.config.tracking_uri:
            mlflow.set_tracking_uri(self.config.tracking_uri)
        elif os.environ.get("MLFLOW_TRACKING_URI"):
            mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        else:
            default_path = Path("mlruns")
            default_path.mkdir(exist_ok=True)
            mlflow.set_tracking_uri(f"file://{default_path.absolute()}")

        mlflow.set_experiment(self.config.experiment_name)
        logger.info(f"MLflow experiment: {self.config.experiment_name}")

    @contextmanager
    def start_run(self, run_name: str | None = None, tags: dict[str, str] | None = None):
        """Start a new MLflow run context."""
        if not MLFLOW_AVAILABLE:
            yield self
            return

        run_name = (
            run_name or self.config.run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        merged_tags = {**(self.config.tags or {}), **(tags or {})}

        with mlflow.start_run(run_name=run_name, tags=merged_tags) as run:
            self._run = run
            self._active = True
            logger.info(f"Started MLflow run: {run.info.run_id}")
            yield self
            self._active = False
            logger.info(f"Ended MLflow run: {run.info.run_id}")

    def log_params(self, params: dict[str, Any]) -> None:
        """Log parameters for the current run."""
        if not self._active or not MLFLOW_AVAILABLE:
            return

        mlflow.log_params(params)
        logger.debug(f"Logged params: {list(params.keys())}")

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log metrics for the current run."""
        if not self._active or not MLFLOW_AVAILABLE:
            return

        mlflow.log_metrics(metrics, step=step)
        logger.debug(f"Logged metrics: {list(metrics.keys())}")

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        """Log a single metric."""
        self.log_metrics({key: value}, step=step)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        """Log an artifact (file) for the current run."""
        if not self._active or not MLFLOW_AVAILABLE:
            return

        mlflow.log_artifact(local_path, artifact_path)
        logger.debug(f"Logged artifact: {local_path}")

    def log_artifacts(self, local_dir: str, artifact_path: str | None = None) -> None:
        """Log all artifacts in a directory."""
        if not self._active or not MLFLOW_AVAILABLE:
            return

        mlflow.log_artifacts(local_dir, artifact_path)
        logger.debug(f"Logged artifacts from: {local_dir}")

    def log_model(
        self,
        model: Any,
        artifact_path: str,
        model_type: str = "sklearn",
        registered_model_name: str | None = None,
        **kwargs,
    ) -> None:
        """
        Log a model with MLflow.

        Args:
            model: The model object to log
            artifact_path: Path within the artifact directory
            model_type: Type of model (sklearn, xgboost, etc.)
            registered_model_name: Name to register in model registry
            **kwargs: Additional arguments for model logging
        """
        if not self._active or not MLFLOW_AVAILABLE:
            return

        if model_type == "xgboost":
            mlflow.xgboost.log_model(
                model, artifact_path, registered_model_name=registered_model_name, **kwargs
            )
        elif model_type == "sklearn":
            mlflow.sklearn.log_model(
                model, artifact_path, registered_model_name=registered_model_name, **kwargs
            )
        else:
            mlflow.log_artifact(artifact_path)

        logger.info(f"Logged model: {artifact_path}")

    def log_dataset_stats(
        self,
        train_size: int,
        val_size: int,
        test_size: int,
        class_distribution: dict[str, int],
    ) -> None:
        """Log dataset statistics."""
        if not self._active or not MLFLOW_AVAILABLE:
            return

        self.log_params(
            {
                "dataset.train_size": train_size,
                "dataset.val_size": val_size,
                "dataset.test_size": test_size,
            }
        )

        for cls, count in class_distribution.items():
            self.log_metric(f"dataset.class_{cls}_count", count)

    def log_confusion_matrix(
        self, y_true: list, y_pred: list, labels: list[str], step: int | None = None
    ) -> None:
        """Log confusion matrix as artifact and metrics."""
        if not self._active or not MLFLOW_AVAILABLE:
            return

        from sklearn.metrics import confusion_matrix

        cm = confusion_matrix(y_true, y_pred, labels=labels)

        for i, true_label in enumerate(labels):
            for j, pred_label in enumerate(labels):
                self.log_metric(f"cm.{true_label}_pred_{pred_label}", float(cm[i, j]), step=step)

    def set_tag(self, key: str, value: str) -> None:
        """Set a tag for the current run."""
        if not self._active or not MLFLOW_AVAILABLE:
            return

        mlflow.set_tag(key, value)

    def get_run_id(self) -> str | None:
        """Get the current run ID."""
        if self._run:
            return self._run.info.run_id
        return None

    def get_artifact_uri(self, artifact_path: str | None = None) -> str | None:
        """Get the URI for an artifact."""
        if not self._active or not MLFLOW_AVAILABLE:
            return None

        return mlflow.get_artifact_uri(artifact_path)


def get_model_versions(model_name: str) -> list[dict]:
    """
    Get all versions of a registered model.

    Args:
        model_name: Name of the registered model

    Returns:
        List of model version dictionaries
    """
    if not MLFLOW_AVAILABLE:
        return []

    client = mlflow.tracking.MlflowClient()

    try:
        versions = client.search_model_versions(f"name='{model_name}'")
        return [
            {
                "version": v.version,
                "stage": v.current_stage,
                "run_id": v.run_id,
                "creation_timestamp": v.creation_timestamp,
            }
            for v in versions
        ]
    except Exception as e:
        logger.warning(f"Failed to get model versions: {e}")
        return []


def transition_model_stage(model_name: str, version: str, stage: str) -> bool:
    """
    Transition a model version to a new stage.

    Args:
        model_name: Name of the registered model
        version: Version number
        stage: Target stage (None, Staging, Production, Archived)

    Returns:
        True if successful
    """
    if not MLFLOW_AVAILABLE:
        return False

    client = mlflow.tracking.MlflowClient()

    try:
        client.transition_model_version_stage(model_name, version, stage)
        logger.info(f"Transitioned {model_name} v{version} to {stage}")
        return True
    except Exception as e:
        logger.error(f"Failed to transition model stage: {e}")
        return False
