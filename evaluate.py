"""Run the correctness evaluation and upload results to LangSmith.

Run with:  python evaluate.py
"""

from hr_assistant.evaluation import run_evaluation


def main():
    print("Running HR policy assistant evaluation...")
    results = run_evaluation()
    print("Done. Open your LangSmith project to see the experiment.")
    print(results)


if __name__ == "__main__":
    main()
