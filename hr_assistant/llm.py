"""Step 6: connect to the LLM (the "brain" of the assistant)."""


from hr_assistant.gateway import get_gateway_llm

from hr_assistant.logger import get_logger

logger = get_logger(__name__)

def get_llm():
    """Return a Groq chat model. Reads GROQ_API_KEY from the environment."""
    logger.info("Initializing LLM via Portkey")
    return get_gateway_llm()