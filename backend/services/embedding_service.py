from fastembed import TextEmbedding


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model = TextEmbedding(model_name=model_name)

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        embeddings = list(self.model.embed([text]))
        return embeddings[0].tolist() if embeddings else []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        embeddings = list(self.model.embed(texts))
        return [emb.tolist() for emb in embeddings]
