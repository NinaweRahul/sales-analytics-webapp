"""
List the Gemini models actually available to your API key, and which
ones support generateContent (the method query_generator.py uses).

Usage:
    cd backend/scripts
    python list_models.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

from google import genai

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not set in .env")
    sys.exit(1)

client = genai.Client(api_key=api_key)

print("Models available to your API key that support generateContent:\n")
for model in client.models.list():
    if "generateContent" in getattr(model, "supported_actions", []):
        print(f"  {model.name}")