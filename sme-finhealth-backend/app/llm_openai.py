import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def advisor_reply(system_prompt: str, user_message: str) -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-5")
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    # responses output_text helper
    return resp.output_text
