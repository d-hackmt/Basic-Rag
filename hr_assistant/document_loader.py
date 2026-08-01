"""Step 1: read the raw document from the data folder."""

from langchain_community.document_loaders import TextLoader
from lark import logger
from hr_assistant import config
from hr_assistant.logger import get_logger

logger = get_logger(__name__)

def load_document(file_path: str = config.DATA_FILE_PATH):
    """Load a .txt file and return it as a list of LangChain Document objects."""
    logger.info("Loading document from '%s'", file_path)
    loader = TextLoader(file_path, encoding="utf-8")
    documents = loader.load()
    logger.info("Loaded %d document(s)", len(documents))
    return documents