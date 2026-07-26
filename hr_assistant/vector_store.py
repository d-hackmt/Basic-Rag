"""Step 4: store chunk embeddings in FAISS so we can search them later."""


import os
from langchain_community.vectorstores import FAISS

from hr_assistant import config 
from hr_assistant.embeddings import get_embeddings_model


# build_vector_store 

def build_vector_store(chunks):
    """Embed every chunk and build 
    a searchable FAISS index in memory."""
    embeddings_model = get_embeddings_model()
    return FAISS.from_documents(chunks, embeddings_model)


## save vector store 

def save_vector_store(vector_store, path: str = config.VECTOR_STORE_PATH) -> None:
    """Save the FAISS index to disk 
    so we don't have to rebuild it every time."""
    vector_store.save_local(path)


def load_vector_store(path: str = config.VECTOR_STORE_PATH):
    """Load a previously saved FAISS index from disk."""
    embeddings_model = get_embeddings_model()
    # allow_dangerous_deserialization is safe here because we only ever load
    # an index that this same app created and saved.
    return FAISS.load_local(path, embeddings_model, allow_dangerous_deserialization=True)


def vector_store_exists(path: str = config.VECTOR_STORE_PATH) -> bool:
    """Check if a saved FAISS index already exists on disk."""
    return os.path.exists(os.path.join(path, "index.faiss"))


def get_retriever(vector_store, k: int = config.TOP_K_RESULTS):
    """Turn a vector store into a retriever 
    that returns the top-k matching chunks."""
    return vector_store.as_retriever(search_kwargs={"k": k})