"""Test basic Azure OpenAI connectivity"""
from dotenv import load_dotenv
import os
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-08-01-preview"
)

print("Testing Azure OpenAI with gpt-5-mini...")
print(f"Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT')}")
print()

try:
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "user", "content": "Say 'Hello World' in JSON format: {\"message\": \"...\"}"}
        ]
    )
    
    print(f"✅ Response received!")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    print(f"   Content: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"❌ Error: {e}")
