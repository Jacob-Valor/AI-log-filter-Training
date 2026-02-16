"""TF-IDF + XGBoost classifier with ONNX-first persistence."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import numpy as np

from src.models.base import BaseClassifier, ClassifierRegistry, Prediction
from src.models.onnx_converter import convert_text_vectorizer_to_onnx, convert_xgboost_to_onnx
from src.utils.logging import get_logger
from src.utils.text_preprocessing import normalize_log_text

logger = get_logger(__name__)

ONNX_AVAILABLE = find_spec("onnxruntime") is not None


@ClassifierRegistry.register("tfidf_xgboost")
class TFIDFClassifier(BaseClassifier):
    """TF-IDF + XGBoost log classifier."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("tfidf_xgboost", config)
        self.vectorizer: Any | None = None
        self.classifier: Any | None = None
        self.label_encoder: Any | None = None
        self.class_names: list[str] = list(self.CATEGORIES)

        self.vectorizer_session: Any | None = None
        self.classifier_session: Any | None = None
        self.vectorizer_input_name: str | None = None
        self.classifier_input_name: str | None = None

        self.tfidf_config = config.get("tfidf", {}) if config else {}
        self.max_features = self.tfidf_config.get("max_features", 10000)
        self.ngram_range = tuple(self.tfidf_config.get("ngram_range", [1, 3]))
        self.min_df = self.tfidf_config.get("min_df", 2)
        self.max_df = self.tfidf_config.get("max_df", 0.95)

        self.xgb_config = config.get("xgboost", {}) if config else {}

    async def load(self):
        """Load trained ONNX model artifacts from disk."""
        model_path = Path(self.config.get("model_path", "models/tfidf_xgboost"))
        vectorizer_path = model_path / "vectorizer.onnx"
        classifier_path = model_path / "model.onnx"
        labels_path = model_path / "labels.json"

        try:
            if vectorizer_path.exists() and classifier_path.exists():
                if not ONNX_AVAILABLE:
                    raise ImportError("onnxruntime is required for ONNX inference")

                ort = import_module("onnxruntime")

                vectorizer_session = ort.InferenceSession(str(vectorizer_path))
                classifier_session = ort.InferenceSession(str(classifier_path))
                self.vectorizer_session = vectorizer_session
                self.classifier_session = classifier_session
                self.vectorizer_input_name = vectorizer_session.get_inputs()[0].name
                self.classifier_input_name = classifier_session.get_inputs()[0].name

                if labels_path.exists():
                    with open(labels_path, encoding="utf-8") as f:
                        labels = json.load(f)
                    if isinstance(labels, list) and labels:
                        self.class_names = [str(label) for label in labels]

                self.is_loaded = True
                logger.info(f"Loaded TF-IDF ONNX artifacts from {model_path}")
                return

            logger.warning(f"ONNX artifacts not found at {model_path}, initializing empty model")
            self._initialize_empty()
            self.is_loaded = True

        except Exception as e:
            logger.error(f"Failed to load TF-IDF classifier: {e}")
            raise

    def _initialize_empty(self):
        """Initialize empty sklearn model for training."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import LabelEncoder
        from xgboost import XGBClassifier

        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            min_df=self.min_df,
            max_df=self.max_df,
            sublinear_tf=True,
        )

        self.classifier = XGBClassifier(
            n_estimators=self.xgb_config.get("n_estimators", 200),
            max_depth=self.xgb_config.get("max_depth", 6),
            learning_rate=self.xgb_config.get("learning_rate", 0.1),
            objective="multi:softprob",
            eval_metric="mlogloss",
            use_label_encoder=False,
            n_jobs=-1,
            random_state=42,
        )

        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(self.CATEGORIES)
        self.class_names = [str(cat) for cat in self.label_encoder.classes_]

        self.vectorizer_session = None
        self.classifier_session = None
        self.vectorizer_input_name = None
        self.classifier_input_name = None

    def preprocess(self, text: str) -> str:
        """Preprocess text for classification."""
        return normalize_log_text(text)

    def _decode_label(self, label: Any) -> str:
        if isinstance(label, bytes):
            label = label.decode("utf-8", errors="ignore")
        if isinstance(label, str):
            if label in self.class_names:
                return label
            if label.isdigit():
                index = int(label)
                if 0 <= index < len(self.class_names):
                    return self.class_names[index]

        try:
            index = int(label)
            if 0 <= index < len(self.class_names):
                return self.class_names[index]
        except (TypeError, ValueError):
            pass

        return "routine"

    def _normalize_probabilities(self, raw_probabilities: Any) -> dict[str, float]:
        probabilities = dict.fromkeys(self.CATEGORIES, 0.0)

        if isinstance(raw_probabilities, dict):
            for label, score in raw_probabilities.items():
                category = self._decode_label(label)
                probabilities[category] = float(score)
            return probabilities

        row = np.asarray(raw_probabilities).reshape(-1)
        for idx, score in enumerate(row):
            if idx >= len(self.class_names):
                break
            category = self.class_names[idx]
            probabilities[category] = float(score)

        return probabilities

    async def predict(self, text: str) -> Prediction:
        """Classify a single log message."""
        predictions = await self.predict_batch([text])
        return predictions[0]

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Classify a batch of log messages."""
        if not self.is_loaded:
            await self.load()

        processed = [self.preprocess(text) for text in texts]

        if self.vectorizer_session and self.classifier_session:
            return self._predict_with_onnx(processed)

        if (
            not self.vectorizer
            or not self.classifier
            or not hasattr(self.vectorizer, "vocabulary_")
        ):
            return [
                Prediction(
                    category="routine",
                    confidence=0.5,
                    model=self.name,
                    explanation={"note": "Model not trained"},
                )
                for _ in texts
            ]

        assert self.label_encoder is not None
        X = self.vectorizer.transform(processed)
        proba = self.classifier.predict_proba(X)
        predictions = self.classifier.predict(X)

        results = []
        for pred_idx, prob in zip(predictions, proba, strict=True):
            category = self.label_encoder.inverse_transform([pred_idx])[0]

            raw_probabilities = {
                cat: float(p) for cat, p in zip(self.label_encoder.classes_, prob, strict=True)
            }
            probabilities = {cat: raw_probabilities.get(cat, 0.0) for cat in self.CATEGORIES}
            confidence = max(probabilities.values()) if probabilities else 0.0

            results.append(
                Prediction(
                    category=category,
                    confidence=confidence,
                    model=self.name,
                    probabilities=probabilities,
                )
            )

        return results

    def _predict_with_onnx(self, processed: list[str]) -> list[Prediction]:
        if not self.vectorizer_session or not self.classifier_session:
            raise RuntimeError("ONNX sessions are not initialized")
        if not self.vectorizer_input_name or not self.classifier_input_name:
            raise RuntimeError("ONNX input names are missing")

        text_input = np.asarray(processed, dtype=object).reshape(-1, 1)
        vectorized_output = self.vectorizer_session.run(
            None, {self.vectorizer_input_name: text_input}
        )
        if not vectorized_output:
            raise RuntimeError("Vectorizer ONNX model returned no outputs")

        raw_features = vectorized_output[0]
        if hasattr(raw_features, "toarray"):
            features = np.asarray(raw_features.toarray(), dtype=np.float32)
        elif hasattr(raw_features, "todense"):
            features = np.asarray(raw_features.todense(), dtype=np.float32)
        else:
            features = np.asarray(raw_features, dtype=np.float32)
        classifier_output = self.classifier_session.run(
            None, {self.classifier_input_name: features}
        )
        if not classifier_output:
            raise RuntimeError("Classifier ONNX model returned no outputs")

        labels_raw = classifier_output[0]
        probabilities_raw = classifier_output[1] if len(classifier_output) > 1 else None

        results: list[Prediction] = []
        for index, raw_label in enumerate(labels_raw):
            category = self._decode_label(raw_label)

            if probabilities_raw is None:
                probabilities = {cat: (1.0 if cat == category else 0.0) for cat in self.CATEGORIES}
            elif isinstance(probabilities_raw, np.ndarray):
                probabilities = self._normalize_probabilities(probabilities_raw[index])
            else:
                probabilities = self._normalize_probabilities(probabilities_raw[index])

            confidence = max(probabilities.values()) if probabilities else 0.0
            results.append(
                Prediction(
                    category=category,
                    confidence=confidence,
                    model=self.name,
                    probabilities=probabilities,
                )
            )

        return results

    def train(self, texts: list[str], labels: list[str]):
        """Train the classifier on labeled data."""
        from sklearn.model_selection import train_test_split

        if self.vectorizer is None or self.classifier is None or self.label_encoder is None:
            self._initialize_empty()

        assert self.vectorizer is not None
        assert self.classifier is not None
        assert self.label_encoder is not None
        logger.info(f"Training TF-IDF classifier on {len(texts)} samples")

        processed = [self.preprocess(text) for text in texts]
        encoded_labels = self.label_encoder.fit_transform(labels)
        self.class_names = [str(cat) for cat in self.label_encoder.classes_]

        X_train, X_val, y_train, y_val = train_test_split(
            processed,
            encoded_labels,
            test_size=0.1,
            random_state=42,
            stratify=encoded_labels,
        )

        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_val_vec = self.vectorizer.transform(X_val)

        self.classifier.fit(X_train_vec, y_train, eval_set=[(X_val_vec, y_val)], verbose=False)
        self.vectorizer_session = None
        self.classifier_session = None

        logger.info("Training complete")

    def save(self, path: str):
        """Save model artifacts in ONNX format."""
        if self.vectorizer is None or self.classifier is None or self.label_encoder is None:
            raise ValueError("Model is not initialized for saving")
        if not hasattr(self.vectorizer, "vocabulary_"):
            raise ValueError("TF-IDF vectorizer is not fitted")

        assert self.vectorizer is not None
        assert self.classifier is not None
        assert self.label_encoder is not None

        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        feature_count = len(self.vectorizer.get_feature_names_out())
        convert_text_vectorizer_to_onnx(
            vectorizer=self.vectorizer,
            output_path=str(save_path / "vectorizer.onnx"),
        )
        convert_xgboost_to_onnx(
            estimator=self.classifier,
            output_path=str(save_path / "model.onnx"),
            feature_count=feature_count,
        )

        labels = [str(cat) for cat in self.label_encoder.classes_]
        with open(save_path / "labels.json", "w", encoding="utf-8") as f:
            json.dump(labels, f, indent=2)

        with open(save_path / "config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

        logger.info(f"TF-IDF ONNX artifacts saved to {save_path}")

    def get_feature_importance(self) -> dict[str, float] | None:
        """Get feature importance from the in-memory XGBoost model."""
        if self.classifier is None or not hasattr(self.classifier, "feature_importances_"):
            return None
        if self.vectorizer is None or not hasattr(self.vectorizer, "get_feature_names_out"):
            return None

        feature_names = self.vectorizer.get_feature_names_out()
        importances = self.classifier.feature_importances_
        indices = np.argsort(importances)[::-1][:50]

        return {str(feature_names[i]): float(importances[i]) for i in indices}
