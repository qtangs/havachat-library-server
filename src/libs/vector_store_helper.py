import os
from typing import Optional
from typing import Tuple

from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings

from libs.logging_helper import logger

cached_vector_stores = {}


def prep_embeddings_for_vector_store(vs_type: str) -> Optional[Tuple]:
    if vs_type.startswith("Qdrant"):
        from langchain_qdrant import FastEmbedSparse
        from custom.langchain_qdrant.fastembed_late_interaction import (
            FastEmbedLateInteraction,
        )

        return FastEmbedSparse(
            "Qdrant/bm42-all-minilm-l6-v2-attentions",
            # cache_dir=fastembed_cache_dir,
            local_files_only=True,
        ), FastEmbedLateInteraction(
            "colbert-ir/colbertv2.0",
            # cache_dir=fastembed_cache_dir,
            local_files_only=True,
        )

    return None


def get_vector_store(
    vs_type: str, embeddings: Embeddings, embeddings_dimensions=1536, **kwargs
) -> VectorStore:
    global cached_vector_stores
    cached_key = f"{vs_type}{embeddings_dimensions}"

    if cached_key in cached_vector_stores:
        return cached_vector_stores[cached_key]

    if vs_type == "Milvus":
        from langchain_community.vectorstores import Milvus

        vector_store = Milvus(
            primary_field="id",
            embedding_function=embeddings,
            connection_args={
                "uri": os.environ["MILVUS_URI"],
                "token": os.environ["MILVUS_TOKEN"],
            },
            collection_name=os.environ["MILVUS_COLLECTION_NAME"],
        )

    elif vs_type == "Pinecone":
        import pinecone
        from langchain_community.vectorstores import Pinecone

        logger.info("Start connection to Pinecone")
        # initialize pinecone
        pinecone.init(
            api_key=os.getenv("PINECONE_API_KEY"),
            environment=os.getenv("PINECONE_ENV"),
        )

        index_name = os.getenv("PINECONE_INDEX")

        logger.info("Add documents to Pinecone")
        index = pinecone.Index(index_name)

        vector_store = Pinecone(index, embeddings, "text")

    elif vs_type == "Qdrant":
        required_envvars = [
            "QDRANT_COLLECTION_NAME",
            "QDRANT_URL",
            "QDRANT_API_KEY",
        ]
        if any(_ not in os.environ for _ in required_envvars):
            raise OSError(
                f"Environment variables {', '.join(required_envvars)}"
                "are required"
            )

        from qdrant_client import QdrantClient

        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )

        collection_name = os.getenv("QDRANT_COLLECTION_NAME")

        from langchain_qdrant import QdrantVectorStore

        if os.getenv("QDRANT_COLLECTION_CREATE_NEW"):
            try:
                from qdrant_client.http.models import VectorParams, Distance

                qdrant_client.create_collection(
                    collection_name,
                    vectors_config={
                        QdrantVectorStore.VECTOR_NAME: VectorParams(
                            size=embeddings_dimensions,
                            distance=Distance.COSINE,
                        )
                    },
                )
            except Exception:
                logger.info(f"Collection {collection_name} already exists")

        vector_store = QdrantVectorStore(
            client=qdrant_client,
            collection_name=os.getenv("QDRANT_COLLECTION_NAME"),
            embedding=embeddings,
        )

    elif vs_type == "Qdrant-Custom" or vs_type == "Qdrant-Local":
        required_envvars = [
            "QDRANT_COLLECTION_NAME",
            "QDRANT_DENSE_VECTOR_NAME",
        ] + (
            ["QDRANT_URL", "QDRANT_API_KEY"]
            if vs_type == "Qdrant-Custom"
            else ["QDRANT_PATH"]
        )
        if any(_ not in os.environ for _ in required_envvars):
            raise OSError(
                f"Environment variables {', '.join(required_envvars)}"
                "are required"
            )

        from custom.langchain_qdrant.custom_qdrant import RetrievalMode
        from custom.langchain_qdrant.custom_qdrant import (
            CustomQdrantVectorStore,
        )

        (
            sparse_embeddings,
            late_interaction_embedding,
        ) = prep_embeddings_for_vector_store(vs_type)

        url = (
            kwargs.get("url", os.getenv("QDRANT_URL"))
            if vs_type == "Qdrant-Custom"
            else None
        )
        path = (
            kwargs.get("path", os.getenv("QDRANT_PATH"))
            if vs_type == "Qdrant-Local"
            else None
        )
        collection_name = kwargs.get(
            "collection_name", os.getenv("QDRANT_COLLECTION_NAME")
        )

        cached_key = (
            f"{vs_type}"
            f"{embeddings_dimensions}"
            f"{url}"
            f"{path}"
            f"{collection_name}"
        )

        if cached_key in cached_vector_stores:
            return cached_vector_stores[cached_key]

        # Use from_texts with dummy input as it supports force_recreate flag
        vector_store = CustomQdrantVectorStore.from_texts(
            texts=[],
            url=url,
            path=path,
            api_key=kwargs.get("api_key", os.getenv("QDRANT_API_KEY")),
            collection_name=collection_name,
            retrieval_mode=(
                RetrievalMode.CUSTOM
                if vs_type == "Qdrant-Custom"
                else RetrievalMode.DENSE
            ),
            embedding=embeddings,
            vector_name=kwargs.get(
                "vector_name", os.getenv("QDRANT_DENSE_VECTOR_NAME")
            ),
            sparse_embedding=sparse_embeddings,
            sparse_vector_name="bm42",
            late_interaction_embedding=late_interaction_embedding,
            late_interaction_vector_name="colbert2",
            force_recreate=kwargs.get(
                "force_recreate", os.getenv("QDRANT_COLLECTION_CREATE_NEW")
            )
            is not None,
        )

    elif vs_type == "Faiss":
        from langchain_community.vectorstores.faiss import (
            dependable_faiss_import,
        )

        faiss = dependable_faiss_import()
        # Default to L2, currently other metric types not initialized.
        index = faiss.IndexFlatL2(embeddings_dimensions)

        from langchain_community.vectorstores import FAISS
        from langchain.docstore import InMemoryDocstore

        vector_store = FAISS(
            embeddings,
            index,
            InMemoryDocstore(),
            {},
        )

    else:
        raise Exception(f"Unknown vector store type {vs_type}")

    cached_vector_stores[cached_key] = vector_store

    return vector_store
