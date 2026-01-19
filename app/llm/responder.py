from app.llm.client import client

def get_message_completion(messages, model="gpt-5-nano", temperature=1):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )
    return response.choices[0].message.content
