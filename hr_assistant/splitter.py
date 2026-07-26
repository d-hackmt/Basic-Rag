"""Step 2: chop the document into small, searchable chunks."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from hr_assistant import config 

def split_into_chunks(documents):
    """Split documents into small overlapping chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    return text_splitter.split_documents(documents)