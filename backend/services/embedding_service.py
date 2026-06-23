import hashlib
from fastembed import TextEmbedding


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = None
        self._try_load_model()

    def _try_load_model(self):
        """Try to load the real model, fall back to mock if download fails."""
        try:
            self.model = TextEmbedding(model_name=self.model_name)
        except Exception:
            # Fallback to mock embeddings for local dev without internet
            self.model = None

    def _mock_embed(self, text: str) -> list[float]:
        """Generate a deterministic mock embedding for testing."""
        # Create a consistent 384-dim embedding from text hash
        h = hashlib.md5(text.encode()).digest()
        # Convert bytes to float values in range [-1, 1]
        embedding = [(b - 128) / 128.0 for b in h * 48]  # 16 * 48 = 768 bytes, use first 384
        return embedding[:384]

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        if self.model is None:
            return self._mock_embed(text)
        embeddings = list(self.model.embed([text]))
        return embeddings[0].tolist() if embeddings else []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        if self.model is None:
            return [self._mock_embed(text) for text in texts]
        embeddings = list(self.model.embed(texts))
        return [emb.tolist() for emb in embeddings]
