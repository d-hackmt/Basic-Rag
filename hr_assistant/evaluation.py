"""
Step 9: evaluate answer quality against a fixed set 
of test questions.

Unlike tracing (which just records what happened), 
evaluation runs the
agent against a known set of question/reference-answer 
pairs and scores
each answer using a second LLM as a judge.
Results are uploaded to
LangSmith as a Dataset + Experiment, 
so quality can be compared across
runs (after a prompt change, a new model, a new guardrail, etc).

The judge model is routed through Portkey too,
using the same slug as
the main app's LLM (gateway.py's PRIMARY_PROVIDER) 
but a different
underlying model (JUDGE_MODEL_NAME) - 
so it isn't grading its own
output verbatim, without needing a second slug set up.
"""


from langchain_openai import ChatOpenAI
from langsmith import Client
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT, RAG_GROUNDEDNESS_PROMPT
from portkey_ai import createHeaders, PORTKEY_GATEWAY_URL

from hr_assistant import config
from hr_assistant.gateway import PRIMARY_PROVIDER , JUDGE_PROVIDER
from hr_assistant.logger import get_logger
from hr_assistant.pipeline import ask, build_hr_assistant
from hr_assistant.vector_store import get_retriever, load_vector_store



logger = get_logger(__name__)

# question paper 
DATASET_NAME = "hr-policy-qna"

TEST_CASES = [
    {"question": "How many days of paid annual leave do I get per year?",
    "answer": "20 days"},
    {"question": "How many days of unused annual leave can be carried forward?", "answer": "Up to 5 days"},
    {"question": "How many paid sick days do I get per year?", "answer": "10 days"},
    {"question": "How many days per week can I work from home?", "answer": "Up to 2 days, with manager approval"},
    {"question": "How long is the probation period?",
    "answer": "3 months"},
    {"question": "What is the notice period during probation?", "answer": "15 days"},
    {"question": "What is the standard notice period for resignation?",
    "answer": "30 days"},
    {"question": "Within how many days must reimbursement claims be submitted?",
    "answer": "30 days of the expense"},
    {"question": "How many public holidays does the company observe each year?", "answer": "12"},
    {"question": "Within how many days is full and final settlement processed after the last working day?", "answer": "45 days"},
]


JUDGE_MODEL_NAME = "openai/gpt-oss-20b"


# making  a judge llm

def _get_judge_llm() -> ChatOpenAI:
    """Return a judge model routed through Portkey, same slug as the main app."""
    headers = createHeaders(api_key=config.PORTKEY_API_KEY, 
            provider=PRIMARY_PROVIDER)
    return ChatOpenAI(api_key="portkey", 
        base_url=PORTKEY_GATEWAY_URL, 
        default_headers=headers, 
        model=JUDGE_MODEL_NAME)
    
# if dataset is there reuse it , if not create a new dataset 
# question paper 
def _ensure_dataset(client: Client):
    """Create the LangSmith dataset if it doesn't exist yet, and upload the test cases."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        logger.info("Dataset '%s' already exists, reusing it", DATASET_NAME)
        return client.read_dataset(dataset_name=DATASET_NAME)

    logger.info("Creating dataset '%s' with %d example(s)", 
        DATASET_NAME, len(TEST_CASES))
    dataset = client.create_dataset(dataset_name=DATASET_NAME)
    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {"inputs": {"question": case["question"]},
            "outputs": {"answer": case["answer"]}}
            for case in TEST_CASES
        ],
    )
    return dataset

# start the exam
def run_evaluation():
    """Upload the dataset (if needed) 
    and run the correctness evaluation."""
    client = Client()
    dataset = _ensure_dataset(client)

    # Built once and reused for every test case, instead of rebuilding
    # the whole agent (and reconnecting to Qdrant) 10 times over.
    agent = build_hr_assistant()
    retriever = get_retriever(load_vector_store())

    # write the answers 
    def target(inputs: dict) -> dict:
        """
        Run one test question through the real agent, 
        and also capture
        the retrieved chunks 
        so groundedness can check the answer against
        what was actually retrieved 
        (not just the reference answer).
        """
        answer = ask(agent, inputs["question"])
        chunks = retriever.invoke(inputs["question"])
        context = "\n\n".join(chunk.page_content for chunk in chunks)
        return {"answer": answer, "context": context}

    # giving marks 
    correctness_evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        feedback_key="correctness",
        judge=_get_judge_llm(),
    )

    groundedness_judge = create_llm_as_judge(
        prompt=RAG_GROUNDEDNESS_PROMPT,
        feedback_key="groundedness",
        judge=_get_judge_llm(),
    )

    def groundedness_evaluator(outputs: dict, **kwargs) -> dict:
        """Check the answer is supported by the retrieved context, not invented."""
        return groundedness_judge(outputs={"answer": outputs["answer"]}, context=outputs["context"])

    logger.info("Running evaluation against dataset '%s'", DATASET_NAME)
    return client.evaluate(
        target,
        data=dataset.name,
        evaluators=[correctness_evaluator,
                groundedness_evaluator],
        experiment_prefix="hr-policy-evalzz",
        description="HR policy assistant correctness + groundedness evaluation",
    )
