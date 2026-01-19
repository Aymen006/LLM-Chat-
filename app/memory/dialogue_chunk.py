def build_dialogue_chunk(conv_history: list, max_turns: int = 40, max_chars: int = 6000) -> str:
    """
    Builds a dialogue chunk from conversation history for the memory updater.
    Caps at max_turns or max_chars to avoid token blowups.
    """
    if not conv_history:
        return ""
    
    # Filter valid messages
    valid_messages = [
        m for m in conv_history 
        if isinstance(m, dict) and 'role' in m and 'content' in m
    ]
    
    # Take most recent turns
    recent = valid_messages[-max_turns:] if len(valid_messages) > max_turns else valid_messages
    
    # Build chunk with character limit
    lines = []
    total_chars = 0
    
    for msg in recent:
        line = f"{msg['role'].capitalize()}: {msg['content']}"
        if total_chars + len(line) > max_chars:
            break
        lines.append(line)
        total_chars += len(line) + 1  # +1 for newline
    
    return "\n".join(lines)
