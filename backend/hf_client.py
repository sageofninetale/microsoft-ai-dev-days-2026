import os
from openai import OpenAI

HF_MODEL = "llama-3.3-70b-versatile"
HF_BASE_URL = "https://api.groq.com/openai/v1"


def get_hf_client() -> OpenAI:
    token = os.getenv("GROQ_API_KEY")
    if not token:
        raise RuntimeError("GROQ_API_KEY environment variable must be set.")
    return OpenAI(base_url=HF_BASE_URL, api_key=token)
