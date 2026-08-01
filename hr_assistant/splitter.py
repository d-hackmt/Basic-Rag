"""Step 2: chop the document into small, searchable chunks."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from hr_assistant import config 
from hr_assistant.logger import get_logger

logger = get_logger(__name__)


def split_into_chunks(documents):
    """Split documents into small overlapping chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    chunks = text_splitter.split_documents(documents)
    logger.info("Split document(s) into %d chunk(s)", len(chunks))
    return chunks