"""Step 0b: LangSmith tracing.

LangSmith tracing needs no wiring in our own code - LangChain looks for
LANGSMITH_TRACING / LANGSMITH_ENDPOINT / LANGSMITH_API_KEY / LANGSMITH_PROJECT
directly in the environment (loaded from .env by config.py) and, if
tracing is turned on, automatically sends a trace of every LLM call,
tool call, and agent step to your LangSmith project.

This module doesn't turn tracing on - the env vars already do that. All
it does is log, once per run, whether tracing is active, so it's obvious
from the logs (see logger.py) whether this run was traced.
"""

from hr_assistant import config
from hr_assistant.logger import get_logger

logger = get_logger(__name__)


def check_langsmith_tracing() -> None:
    """Log whether LangSmith tracing is enabled for this run."""
    tracing_on = config.LANGSMITH_TRACING.lower() == "true"

    if tracing_on and config.LANGSMITH_API_KEY:
        logger.info(
            "LangSmith tracing ENABLED - project '%s', traces at %s",
            config.LANGSMITH_PROJECT,
            "https://smith.langchain.com",
        )
    else:
        logger.info("LangSmith tracing is OFF (set LANGSMITH_TRACING=true in .env to enable)")
