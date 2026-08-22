"""Step 6b: route the LLM through the Portkey gateway.

Instead of calling Groq directly, the main LLM call goes through Portkey.
Portkey stores the real Groq credentials behind a "slug" (set up once in
the Portkey dashboard) - our code never sees the raw Groq key.

NOTE on fallback: we used to send a "config" (strategy: fallback + a
list of targets) via the x-portkey-config header, either as inline JSON
or as a saved config's "pc-..." slug. This Portkey workspace has
"block_inline_config" enabled, and there's no saved config to reference
either, so ANY x-portkey-config header - inline or slug - gets rejected
with `inline_config_blocked`. Routing straight to one provider via
x-portkey-provider sidesteps the config mechanism entirely (that header
isn't validated the same way), which is why this version doesn't send a
config at all. The tradeoff: no more automatic Portkey-side fallback to
a second slug if @hrpolicy fails - see docs/05_portkey_gateway.md.
"""

from langchain_openai import ChatOpenAI
from portkey_ai import createHeaders, PORTKEY_GATEWAY_URL

from hr_assistant import config
from hr_assistant.logger import get_logger


logger = get_logger(__name__)

# The one Groq integration set up in the Portkey dashboard for this
# workspace (see module docstring for why there's only one).
PRIMARY_PROVIDER = "@hrpolicy"



def get_gateway_llm() -> ChatOpenAI:
    """Return a chat model routed through Portkey (no config/fallback - see module docstring)."""
    logger.info("Routing LLM calls through Portkey (provider=%s)", PRIMARY_PROVIDER)
    headers = createHeaders(api_key=config.PORTKEY_API_KEY, provider=PRIMARY_PROVIDER)
    return ChatOpenAI(
        api_key="portkey",  # dummy value - the real auth is in the headers
        base_url=PORTKEY_GATEWAY_URL,
        model=config.LLM_MODEL_NAME,
        default_headers=headers,
    )
    
