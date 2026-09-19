"""Smoke test: confirms ask(agent, question) actually works end-to-end
before CI spends time/money on the full evaluation suite.

Builds the real agent (real Groq/Jina/Qdrant/Portkey calls) and asks it one
question - this is deliberately an integration check, not a mocked unit test.
"""

from hr_assistant.pipeline import ask, build_hr_assistant


def test_ask_returns_a_real_answer():
    agent = build_hr_assistant()
    answer = ask(agent, "How many days of paid annual leave do I get per year?")

    assert isinstance(answer, str)
    assert answer.strip() != ""
