import hashlib
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_model: Optional[object] = None


def _get_model():
    """Lazy-load fastembed model."""
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            logger.info("✓ Loaded fastembed model")
        except Exception as e:
            logger.warning(f"Failed to load fastembed: {e}")
            _model = False  # Sentinel: use fallback
    return _model if _model is not False else None


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = _get_model()

    def _tfidf_embed(self, text: str) -> list[float]:
        """Generate a semantic-aware 384-dim embedding using TF-IDF + hashing.

        Better fallback than pure hashing - captures word importance.
        """
        # Tokenize: lowercase, split on whitespace, remove punctuation
        tokens = text.lower().split()
        tokens = [
            ''.join(c for c in t if c.isalnum())
            for t in tokens
        ]
        tokens = [t for t in tokens if len(t) > 2]  # Skip short words

        if not tokens:
            return [0.0] * 384

        # Compute term frequency
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        # Create embedding by hashing tokens to dimensions
        embedding = [0.0] * 384

        # For each unique term, hash to dimensions and add weighted value
        for term, freq in tf.items():
            # Log-normalize frequency
            weight = math.log(1 + freq) / math.sqrt(len(tf))

            # Hash term to 3 different dimensions
            for i in range(3):
                hash_val = hash((term, i)) % 384
                embedding[hash_val] += weight

        # L2 normalize
        norm = math.sqrt(sum(x**2 for x in embedding) + 1e-8)
        embedding = [x / norm for x in embedding]

        return embedding

    def _mock_embed(self, text: str) -> list[float]:
        """Fallback: simple hash-based embedding."""
        h = hashlib.md5(text.encode()).digest()
        embedding = [(b - 128) / 128.0 for b in h * 48]
        return embedding[:384]

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        if self.model is None:
            # Use TF-IDF fallback for better semantic matching
            return self._tfidf_embed(text)

        try:
            embeddings = list(self.model.embed([text]))
            if embeddings:
                return embeddings[0].tolist()
        except Exception as e:
            logger.warning(f"embed_text failed: {e}, using TF-IDF")

        return self._tfidf_embed(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        if self.model is None:
            return [self._tfidf_embed(text) for text in texts]

        try:
            embeddings = list(self.model.embed(texts))
            if embeddings:
                return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.warning(f"embed_texts failed: {e}, using TF-IDF")

        return [self._tfidf_embed(text) for text in texts]
