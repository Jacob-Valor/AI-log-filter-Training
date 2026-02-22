from typing import Any

from src.domain.ports import ClassifierPort


class ClassifierFactory:
    """Factory for creating log classifiers."""

    @staticmethod
    def create(config: dict[str, Any]) -> ClassifierPort:
        """
        Create a classifier instance based on configuration.

        Args:
            config: Model configuration dictionary

        Returns:
            Configured ClassifierPort instance
        """
        model_type = str(config.get("type", "safe_ensemble"))
        model_path = config.get("path")

        if model_type == "safe_ensemble":
            from src.models.safe_ensemble import SafeEnsembleClassifier

            return SafeEnsembleClassifier(model_path=model_path, config=config)

        if model_type == "onnx_safe_ensemble":
            from src.models.onnx_ensemble import ONNXSafeEnsembleClassifier

            return ONNXSafeEnsembleClassifier(model_path=model_path, config=config)

        if model_type == "ensemble":
            from src.models.ensemble import EnsembleClassifier

            return EnsembleClassifier(model_path=model_path, config=config)

        raise ValueError(f"Unknown classifier type: {model_type}")
