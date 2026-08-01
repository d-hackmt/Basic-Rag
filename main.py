"""Command-line demo of the HR Policy Assistant.

Run with:  python main.py
"""

from hr_assistant.pipeline import ask , build_hr_assistant
from hr_assistant.logger import get_logger
logger = get_logger(__name__)

def main():
    logger.info("=== CLI run started ===")
    print("Building the HR policy assistant...")
    agent = build_hr_assistant()
    print("Assistant ready!\n")

    demo_questions = [
        "How many paid annual leave days do I get?",
        "What is the notice period during probation?",
        "Can I work from home every day?",
    ]

    for question in demo_questions:
        print("=" * 60)
        print("QUESTION:", question)
        print("-" * 60)
        answer = ask(agent, question)
        print("ANSWER:", answer)
        print("=" * 60)
        print()
        
        logger.info("=== CLI run finished ===")


if __name__ == "__main__":
    main()