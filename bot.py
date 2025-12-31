import os
from openai import OpenAI

# ENV se key uthao
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY env me set nahi hai")
    exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

try:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input="Say hello in one short line"
    )

    print("✅ OpenAI Working")
    print("Reply:", response.output_text)

except Exception as e:
    print("❌ OpenAI Error")
    print(e)
