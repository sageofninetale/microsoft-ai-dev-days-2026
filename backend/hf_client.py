import os
from openai import OpenAI

HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
HF_BASE_URL = "https://router.huggingface.co/v1"


def get_hf_client() -> OpenAI:
    token = os.getenv("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN environment variable must be set.")
    return OpenAI(base_url=HF_BASE_URL, api_key=token)
