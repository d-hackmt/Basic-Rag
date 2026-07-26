"""Step 7: build the agent that ties the LLM and the search tool together."""


from langchain.agents import create_agent

from hr_assistant import config


def create_hr_agent(llm, tools):
    """Return a LangChain agent that can 
    call our tools to answer questions."""
    return create_agent(model=llm, 
                        tools=tools, 
                        system_prompt=config.SYSTEM_PROMPT)
