# app/llm_helper.py
# Optional wrapper to call an LLM for interpretation.
# Keep usage minimal and never trust LLM for numeric answers.

import os

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

async def interpret_instruction(instruction: str) -> dict:
    """Return a small JSON describing steps to take. Example:
    { 'action': 'sum_column', 'column': 'value', 'page': 2 }
    This is a thin wrapper — implement calling a provider you prefer.
    """
    # Placeholder: implement OpenAI or other provider calls here.
    
    return {'action': 'unknown'}