"""Step 7: build the agent that ties the LLM and the search tool together."""


from langchain.agents import create_agent

from hr_assistant import config
from hr_assistant.logger import get_logger

logger = get_logger(__name__)

def create_hr_agent(llm, tools):
    """Return a LangChain agent that can
    call our tools to answer questions."""
    logger.info("Creating HR agent with %d tool(s)", len(tools))
    agent = create_agent(model=llm,
                        tools=tools,
                        system_prompt=config.SYSTEM_PROMPT)
    logger.info("HR agent ready")
    return agent
