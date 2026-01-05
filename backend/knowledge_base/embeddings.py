"""
Embeddings Module

Generates vector embeddings using HuggingFace (all-MiniLM-L6-v2) or Z.ai API.
Provides a unified interface for both providers.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional
import hashlib
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name/identifier."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass


class HuggingFaceEmbeddings(EmbeddingProvider):
    """
    HuggingFace sentence-transformers embedding provider.
    Uses all-MiniLM-L6-v2 by default (384 dimensions).
    """

    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "cpu",
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize the HuggingFace embedding provider.

        Args:
            model_name: HuggingFace model name/path
            device: Device to run model on ('cpu', 'cuda', 'mps')
            cache_dir: Directory to cache model files
        """
        self._model_name = model_name
        self._device = device
        self._model = None
        self._cache_dir = cache_dir

    def _load_model(self):
        """Lazy load the model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading model: {self._model_name}")
            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
                cache_folder=self._cache_dir,
            )
            logger.info(f"Model loaded successfully (dimension: {self.dimension})")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for HuggingFace embeddings. "
                "Install with: pip install sentence-transformers"
            )

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        self._load_model()
        return self._model.get_sentence_embedding_dimension()

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors
        """
        self._load_model()
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        return embeddings.tolist()


class ZaiEmbeddings(EmbeddingProvider):
    """
    Z.ai embedding provider using their API.
    """

    DEFAULT_MODEL = "embedding-001"
    API_BASE_URL = "https://api.z.ai/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        api_base_url: str = API_BASE_URL,
    ):
        """
        Initialize the Z.ai embedding provider.

        Args:
            api_key: Z.ai API key (or set ZAI_API_KEY environment variable)
            model_name: Z.ai embedding model name
            api_base_url: Base URL for Z.ai API
        """
        self._api_key = api_key or os.environ.get("ZAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Z.ai API key is required. Set ZAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self._model_name = model_name
        self._api_base_url = api_base_url.rstrip("/")
        self._dimension: Optional[int] = None

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        if self._dimension is None:
            # Get dimension by embedding a test string
            test_embedding = self.embed_text("test")
            self._dimension = len(test_embedding)
        return self._dimension

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    def _make_request(self, texts: list[str]) -> list[list[float]]:
        """
        Make API request to Z.ai.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "requests library is required for Z.ai embeddings. "
                "Install with: pip install requests"
            )

        url = f"{self._api_base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_name,
            "input": texts,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            # Extract embeddings from response
            embeddings = []
            for item in sorted(data["data"], key=lambda x: x["index"]):
                embeddings.append(item["embedding"])

            return embeddings

        except requests.exceptions.RequestException as e:
            logger.error(f"Z.ai API request failed: {e}")
            raise

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        embeddings = self._make_request([text])
        return embeddings[0]

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self._make_request(batch)
            all_embeddings.extend(embeddings)
            logger.debug(f"Embedded batch {i // batch_size + 1}")

        return all_embeddings


class CachedEmbeddings(EmbeddingProvider):
    """
    Wrapper that caches embeddings to disk.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize cached embedding provider.

        Args:
            provider: Underlying embedding provider
            cache_dir: Directory to store cache files
        """
        self._provider = provider

        if cache_dir is None:
            cache_dir = Path(__file__).parent / ".embedding_cache"
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._cache_file = self._cache_dir / f"{provider.model_name.replace('/', '_')}.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cache from disk."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load embedding cache: {e}")
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self._cache_file, "w") as f:
                json.dump(self._cache, f)
        except Exception as e:
            logger.warning(f"Failed to save embedding cache: {e}")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    @property
    def model_name(self) -> str:
        return f"cached_{self._provider.model_name}"

    def embed_text(self, text: str) -> list[float]:
        """
        Get embedding with caching.
        """
        key = self._get_cache_key(text)
        if key in self._cache:
            return self._cache[key]

        embedding = self._provider.embed_text(text)
        self._cache[key] = embedding
        self._save_cache()
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings with caching.
        """
        embeddings = []
        uncached_texts = []
        uncached_indices = []

        # Check cache first
        for i, text in enumerate(texts):
            key = self._get_cache_key(text)
            if key in self._cache:
                embeddings.append(self._cache[key])
            else:
                embeddings.append(None)
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Embed uncached texts
        if uncached_texts:
            new_embeddings = self._provider.embed_batch(uncached_texts)
            for idx, embedding, text in zip(uncached_indices, new_embeddings, uncached_texts):
                embeddings[idx] = embedding
                self._cache[self._get_cache_key(text)] = embedding
            self._save_cache()

        return embeddings


def create_embedding_provider(
    provider: str = "huggingface",
    **kwargs,
) -> EmbeddingProvider:
    """
    Factory function to create an embedding provider.

    Args:
        provider: Provider name ('huggingface' or 'zai')
        **kwargs: Additional arguments for the provider

    Returns:
        EmbeddingProvider instance
    """
    providers = {
        "huggingface": HuggingFaceEmbeddings,
        "hf": HuggingFaceEmbeddings,
        "zai": ZaiEmbeddings,
        "z.ai": ZaiEmbeddings,
    }

    provider_lower = provider.lower()
    if provider_lower not in providers:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available providers: {list(providers.keys())}"
        )

    return providers[provider_lower](**kwargs)


def main():
    """
    Main entry point for testing embeddings.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Test embedding generation"
    )
    parser.add_argument(
        "--provider",
        choices=["huggingface", "zai"],
        default="huggingface",
        help="Embedding provider to use",
    )
    parser.add_argument(
        "--text",
        default="Hello, world! This is a test.",
        help="Text to embed",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Create provider
    try:
        provider = create_embedding_provider(args.provider)
        print(f"Provider: {provider.model_name}")
        print(f"Dimension: {provider.dimension}")

        # Generate embedding
        embedding = provider.embed_text(args.text)
        print(f"\nText: {args.text}")
        print(f"Embedding shape: ({len(embedding)},)")
        print(f"First 5 values: {embedding[:5]}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
