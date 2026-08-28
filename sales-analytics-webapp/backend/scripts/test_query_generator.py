"""
Standalone test of the full pipeline: question -> SQL -> execute -> results.
Run this BEFORE building the FastAPI layer, to confirm the generator +
validator + database actually work together correctly.

Usage:
    cd backend/scripts
    python test_query_generator.py

Requires in .env (project root):
    GEMINI_API_KEY=...
    DATABASE_URL=postgresql://analytics_readonly:CHANGE_ME_BEFORE_DEPLOY@localhost:5432/olist_analytics

Note: uses the READONLY connection deliberately — if this script can
successfully run generated queries through the readonly role, that's
a good sign the app layer will work too.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

from query_generator import QueryGenerator, QueryGenerationError

TEST_QUESTIONS = [
    "What are the top 5 products by revenue?",
    "How many customers have placed more than one order?",
    "What is the average review score by product category?",
    "Which states generate the most revenue?",
    "What percentage of orders were delivered late?",
]


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)

    readonly_url = os.getenv("READONLY_DATABASE_URL")
    if not readonly_url:
        print("ERROR: READONLY_DATABASE_URL not set in .env")
        sys.exit(1)

    generator = QueryGenerator(api_key=api_key)
    engine = create_engine(readonly_url)

    for question in TEST_QUESTIONS:
        print("=" * 70)
        print(f"Q: {question}")
        print("=" * 70)

        try:
            result = generator.generate_sql(question)
            print(f"\nGenerated SQL (attempt {result['attempts']}):")
            print(f"  {result['sql']}")
            print(f"\nExplanation: {result['explanation']}")

            with engine.connect() as conn:
                rows = conn.execute(text(result["sql"])).fetchall()

            print(f"\nResults ({len(rows)} rows, showing up to 5):")
            for row in rows[:5]:
                print(f"  {row}")

        except QueryGenerationError as e:
            print(f"\n✗ GENERATION FAILED: {e}")
        except Exception as e:
            print(f"\n✗ EXECUTION FAILED: {type(e).__name__}: {e}")

        print()


if __name__ == "__main__":
    main()
