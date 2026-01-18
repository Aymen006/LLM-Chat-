def get_completion(prompt, model="gpt-5-nano"):
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=1
    )
    return response.choices[0].message.content

def get_message_completion(messages, model="gpt-5-nano", temperature=1):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )
    return response.choices[0].message.content

def chat_with_context(user_message, context):
    """
    Takes user message and context, gets response from LLM,
    and updates context with both user message and assistant response
    """
    # Add user message to context
    context.append({"role": "user", "content": user_message})
    
    # Get response from LLM with full context
    assistant_response = get_message_completion(context)
    
    # Add assistant response to context
    context.append({"role": "assistant", "content": assistant_response})
    
    return assistant_response, context
