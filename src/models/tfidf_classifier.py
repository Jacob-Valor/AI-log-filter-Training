"""
TF-IDF + XGBoost Classifier

Lightweight ML classifier using TF-IDF vectorization and XGBoost.
Good balance between accuracy and speed.
"""

import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from src.models.base import BaseClassifier, ClassifierRegistry, Prediction
from src.utils.logging import get_logger

logger = get_logger(__name__)


@ClassifierRegistry.register("tfidf_xgboost")
class TFIDFClassifier(BaseClassifier):
    """
    TF-IDF + XGBoost log classifier.

    Uses TF-IDF vectorization for text features and XGBoost
    for classification. Provides good accuracy with low latency.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("tfidf_xgboost", config)
        self.vectorizer = None
        self.classifier = None
        self.label_encoder = None

        # TF-IDF config
        self.tfidf_config = config.get("tfidf", {}) if config else {}
        self.max_features = self.tfidf_config.get("max_features", 10000)
        self.ngram_range = tuple(self.tfidf_config.get("ngram_range", [1, 3]))
        self.min_df = self.tfidf_config.get("min_df", 2)
        self.max_df = self.tfidf_config.get("max_df", 0.95)

        # XGBoost config
        self.xgb_config = config.get("xgboost", {}) if config else {}

    async def load(self):
        """Load trained model from disk."""
        model_path = Path(self.config.get("model_path", "models/tfidf_xgboost"))

        try:
            artifacts = joblib.load(model_path / "model.joblib")
            self.vectorizer = artifacts["vectorizer"]
            self.classifier = artifacts["classifier"]
            self.label_encoder = artifacts["label_encoder"]
            self.is_loaded = True
            logger.info(f"Loaded TF-IDF classifier from {model_path}")

        except FileNotFoundError:
            logger.warning(f"Model not found at {model_path}, initializing empty model")
            self._initialize_empty()
            self.is_loaded = True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _initialize_empty(self):
        """Initialize empty model for training."""
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

    def preprocess(self, text: str) -> str:
        """Preprocess text for classification."""
        # Normalize IP addresses
        text = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", text)

        # Normalize timestamps
        text = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "<TIMESTAMP>", text)

        # Normalize hex values
        text = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", text)

        # Normalize UUIDs
        text = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<UUID>",
            text,
            flags=re.IGNORECASE,
        )

        # Normalize emails
        text = re.sub(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", "<EMAIL>", text)

        # Normalize MAC addresses
        text = re.sub(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", "<MAC>", text, flags=re.I)

        # Normalize hashes (MD5/SHA1/SHA256)
        text = re.sub(r"\b[a-f0-9]{32}\b", "<HASH>", text, flags=re.I)
        text = re.sub(r"\b[a-f0-9]{40}\b", "<HASH>", text, flags=re.I)
        text = re.sub(r"\b[a-f0-9]{64}\b", "<HASH>", text, flags=re.I)

        # Normalize paths
        text = re.sub(r"(/[\w\-./]+)+", "<PATH>", text)

        # Normalize large numbers
        text = re.sub(r"\b\d{5,}\b", "<LONGNUM>", text)

        # Lowercase and normalize whitespace
        text = text.lower()
        text = re.sub(r"\s+", " ", text).strip()

        return text

    async def predict(self, text: str) -> Prediction:
        """Classify a single log message."""
        predictions = await self.predict_batch([text])
        return predictions[0]

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Classify a batch of log messages."""
        if not self.is_loaded:
            await self.load()

        # Preprocess texts
        processed = [self.preprocess(text) for text in texts]

        # Check if model is trained
        if not hasattr(self.vectorizer, "vocabulary_"):
            # Model not trained, return default predictions
            return [
                Prediction(
                    category="routine",
                    confidence=0.5,
                    model=self.name,
                    explanation={"note": "Model not trained"},
                )
                for _ in texts
            ]

        # Vectorize
        X = self.vectorizer.transform(processed)

        # Predict
        proba = self.classifier.predict_proba(X)
        predictions = self.classifier.predict(X)

        # Create prediction objects
        results = []
        for _i, (pred_idx, prob) in enumerate(zip(predictions, proba, strict=False)):
            category = self.label_encoder.inverse_transform([pred_idx])[0]

            raw_probabilities = {
                cat: float(p) for cat, p in zip(self.label_encoder.classes_, prob, strict=False)
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

    def train(self, texts: list[str], labels: list[str]):
        """Train the classifier on labeled data."""
        from sklearn.model_selection import train_test_split

        logger.info(f"Training TF-IDF classifier on {len(texts)} samples")

        # Preprocess
        processed = [self.preprocess(text) for text in texts]

        # Encode labels
        encoded_labels = self.label_encoder.fit_transform(labels)

        # Split for validation
        X_train, X_val, y_train, y_val = train_test_split(
            processed, encoded_labels, test_size=0.1, random_state=42, stratify=encoded_labels
        )

        # Vectorize
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_val_vec = self.vectorizer.transform(X_val)

        # Train with early stopping
        self.classifier.fit(X_train_vec, y_train, eval_set=[(X_val_vec, y_val)], verbose=False)

        logger.info("Training complete")

    def save(self, path: str):
        """Save model to disk."""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        artifacts = {
            "vectorizer": self.vectorizer,
            "classifier": self.classifier,
            "label_encoder": self.label_encoder,
            "config": self.config,
        }

        joblib.dump(artifacts, save_path / "model.joblib")
        logger.info(f"Model saved to {save_path}")

    def get_feature_importance(self) -> dict[str, float] | None:
        """Get feature importance from XGBoost."""
        if not hasattr(self.classifier, "feature_importances_"):
            return None

        feature_names = self.vectorizer.get_feature_names_out()
        importances = self.classifier.feature_importances_

        # Get top features
        indices = np.argsort(importances)[::-1][:50]

        return {feature_names[i]: float(importances[i]) for i in indices}
