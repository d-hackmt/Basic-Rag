"""Step 5: wrap the retriever as a tool the agent can call."""

from langchain.tools import tool

from hr_assistant.logger import get_logger

logger = get_logger(__name__)

def create_search_tool(retriever):
    """Return a @tool function that searches the HR policy document."""

    @tool
    def search_hr_policy(question: str) -> str:
        """Search the HR policy document for information about leave, work from home,
        probation, notice period, reimbursement, code of conduct, holidays, or exit process."""
        logger.info("search_hr_policy called with query: %s", question)
        matching_chunks = retriever.invoke(question)
        logger.info("Found %d matching chunk(s)", len(matching_chunks))
        return "\n\n".join(chunk.page_content for chunk in matching_chunks)

    return search_hr_policy
