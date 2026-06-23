from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config import settings


class QdrantService:
    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        url = url or settings.qdrant_url
        api_key = api_key or settings.qdrant_api_key

        # Use in-memory Qdrant for local development if URL is localhost and no API key
        if url == "http://localhost:6333" and not api_key:
            self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(url=url, api_key=api_key if api_key else None)

    def create_collection(self, collection_name: str, vector_size: int = 384):
        """Create a new collection for embeddings (384-dim for BAAI/bge-small-en-v1.5)."""
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        except Exception:
            # Collection may already exist
            pass

    def upsert_vectors(
        self,
        collection_name: str,
        points: list[dict],  # {id, vector, payload}
    ):
        """Upsert (insert or update) vectors into a collection."""
        point_structs = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {}),
            )
            for p in points
        ]
        self.client.upsert(collection_name=collection_name, points=point_structs)

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """Search for top-k similar vectors and return with payloads."""
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
        )
        return [
            {
                "score": result.score,
                "text": result.payload.get("text", ""),
            }
            for result in results
        ]

    def delete_collection(self, collection_name: str):
        """Delete a collection."""
        self.client.delete_collection(collection_name=collection_name)
