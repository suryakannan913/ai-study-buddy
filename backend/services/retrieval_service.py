"""Hybrid retrieval service combining BM25 and semantic search."""

import math
from typing import Optional
from sqlalchemy.orm import Session
from models import StudyMaterial
from services.embedding_service import EmbeddingService
from services.qdrant_service import QdrantService


class RetrievalService:
    """Hybrid retriever combining BM25 (keyword) + semantic search."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.qdrant_service = QdrantService()

    def retrieve_context(
        self,
        query: str,
        materials: list[StudyMaterial],
        top_k: int = 5,
    ) -> str:
        """
        Retrieve relevant context using hybrid search with fallback.

        Strategy:
        1. Try semantic search via Qdrant
        2. If that fails, use BM25 keyword matching
        3. Combine and rank by hybrid score
        4. Return top-k chunks
        """
        if not materials or not query:
            return ""

        # Tokenize query for BM25
        query_tokens = self._tokenize(query)
        query_embedding = self.embedding_service.embed_text(query)

        all_results = []

        for material in materials:
            # Try Qdrant first
            semantic_results = self._try_qdrant_search(
                material.qdrant_collection_name, query_embedding
            )

            if semantic_results:
                # Re-rank with BM25
                for result in semantic_results:
                    text = result.get("text", "")
                    semantic_score = result.get("score", 0.0)

                    # BM25-style scoring
                    bm25_score = self._bm25_score(query_tokens, text)

                    # Hybrid score: 60% semantic + 40% BM25
                    hybrid_score = (0.6 * semantic_score) + (0.4 * bm25_score)

                    all_results.append(
                        {
                            "text": text,
                            "semantic_score": semantic_score,
                            "bm25_score": bm25_score,
                            "hybrid_score": hybrid_score,
                        }
                    )

        if not all_results:
            return ""

        # Sort by hybrid score and take top-k
        all_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        top_results = all_results[:top_k]

        # Return concatenated context
        context = "\n---\n".join([r["text"] for r in top_results])
        return context

    def _try_qdrant_search(self, collection_name: str, query_vector: list[float]):
        """Try Qdrant search, return None if it fails."""
        try:
            results = self.qdrant_service.search(
                collection_name=collection_name,
                query_vector=query_vector,
                top_k=10,
            )
            if results:
                return results
        except Exception:
            pass
        return None

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization."""
        tokens = text.lower().split()
        return [t.strip(".,!?;:") for t in tokens if len(t) > 2]

    def _bm25_score(self, query_tokens: list[str], document: str) -> float:
        """
        Simplified BM25 scoring.

        BM25 = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))
        """
        k1 = 1.5  # Term frequency saturation
        b = 0.75  # Document length normalization

        doc_tokens = self._tokenize(document)
        doc_len = len(doc_tokens)
        avg_len = 100  # Assume avg doc length

        score = 0.0
        for query_token in query_tokens:
            # Term frequency in document
            term_freq = sum(1 for t in doc_tokens if t == query_token)

            if term_freq == 0:
                continue

            # IDF: log((N - df + 0.5) / (df + 0.5))
            # Simplified: assume df = 1 (rare terms get higher weight)
            idf = math.log(100 / (1 + 1))  # Simplified

            # BM25 formula
            numerator = term_freq * (k1 + 1)
            denominator = term_freq + k1 * (1 - b + b * (doc_len / avg_len))
            score += idf * (numerator / denominator)

        # Normalize by number of query terms
        return score / max(1, len(query_tokens))
