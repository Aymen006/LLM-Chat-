#!/usr/bin/env python3
"""
Standalone test script for the Gradio chatbot interface
"""
import gradio as gr
import json
from openai import OpenAI
import os
from dotenv import load_dotenv, find_dotenv
from db_functions import get_or_create_coach_state, save_coach_state

# Load environment variables
dotenv_path = find_dotenv()
print(f"Loading .env from: {dotenv_path}")
load_dotenv(dotenv_path)

api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError("Missing OPENAI_API_KEY. Put it in your .env file")

# Strip any quotes that might be included
api_key = api_key.strip('"').strip("'")

# Initialize the OpenAI client
client = OpenAI(api_key=api_key)

print("✓ Key loaded successfully and client initialized.")

def get_message_completion(messages, model="gpt-5-nano", temperature=1):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )
    return response.choices[0].message.content

# Check version and determine if we can set type="tuples"
major_version = int(gr.__version__.split('.')[0])
print(f"Gradio Version: {gr.__version__}")

# System prompt for the coach
COACH_SYSTEM_PROMPT = """You are a mentor-coach for high-pressure individuals such as founders. For each session, you will receive:
- **COACH_STATE:** a JSON containing the user's long-term goals, plans, blockers, preferences, and commitments. Treat this as authoritative.
- **RECENT_TURNS:** the user's most recent conversation exchanges.
- **The user's latest message.**

Your outputs must adhere to these instructions:

- Use **COACH_STATE** as the reliable source of the user's objectives, blockers, and commitments.
- Use **RECENT_TURNS** for short-term context and recent conversational flow.

For each response, follow this structured format:

1. **Pattern & Stress Signals**: Begin by analyzing the user's latest message for stress indicators, recurring patterns, and potential mindset pitfalls. Reference COACH_STATE and RECENT_TURNS for accuracy.
2. **Recommendations**: Based on the above, provide highly specific, actionable advice that speaks to the user's context, closing the gap between their goals and current situation. Avoid generic or repetitive suggestions.
3. **Next Actions (checklist)**: Provide a short, actionable checklist (2–4 items max) for what the user should do before the next check-in.
4. **Follow-up Questions (if needed)**: Pose 1–3 sharp clarifying questions that help flesh out missing details about goals, blockers, preferences, commitments, or timelines. Only ask if this information is not precise in COACH_STATE or RECENT_TURNS.

**Rules:**
- Do NOT fabricate or infer facts, deadlines, or commitments not present in COACH_STATE or RECENT_TURNS.
- If key information is missing, use targeted follow-up questions to uncover it.
- If the user reports progress, recognize it and tailor new advice precisely, but do not assert that memory has been updated (this process is external).
- Keep language concise, direct, and accountability-focused. Avoid platitudes or soft generalities.

**Output Format**: Human-readable, no JSON or code formatting. Use clear, separate section headers for each part (Pattern & Stress Signals, Recommendations, Next Actions, Follow-up Questions).

**Reminder:** Always ground your responses in the provided COACH_STATE and RECENT_TURNS. Never fabricate information, commitments, or deadlines not found there. Organize your answer using the mandatory output sections.
"""

MEMORY_UPDATER_PROMPT = """
You are a memory updater for a coaching chatbot.
Input:
- OLD_COACH_STATE (JSON)
- DIALOGUE_CHUNK (recent turns from the CURRENT session, in-memory)

Task:
Update OLD_COACH_STATE using ONLY facts explicitly stated in DIALOGUE_CHUNK.
Return ONLY the UPDATED_COACH_STATE as valid JSON. No extra text.

Special requirement:
Update "pattern_analysis" and "last_emotional_state" to reflect how the user presented in this session.
- Derive emotional state ONLY from explicit wording/tone in DIALOGUE_CHUNK.
- Keep it compact and conservative; do not over-infer.
- Use short strings for signals/patterns; avoid long narrative.

Rules:
- Add or modify goals only if the user clearly stated them.
- Add next actions only if the user explicitly committed to them.
- Mark actions done ONLY if user confirmed completion.
- Track blockers only if clearly described.
- Track preferences only if explicitly stated.
- Do NOT store secrets (API keys, passwords).
- Keep IDs stable if present.

Required keys (must always exist):
{
  "user_profile": { "name": null, "preferences": { "tone": "direct", "accountability": "high", "constraints": [] } },
  "goals": [],
  "current_focus": "",
  "next_actions": [],
  "plan": [],
  "blockers": [],
  "open_loops": [],
  "pattern_analysis": {
    "overall_tone": "neutral",
    "stress_level": 0,
    "dominant_emotions": [],
    "confidence_level": 0,
    "signals": [],
    "recurring_patterns": [],
    "last_session_notes": ""
  },
  "last_emotional_state": {
    "mood_label": "neutral",
    "valence": 0,
    "arousal": 0,
    "risk_flags": []
  },
  "last_session_summary": "",
  "updated_at": ""
}

Return JSON only.
"""

def update_coach_state(old_state, dialogue_chunk):
    messages = [
        {"role": "system", "content": MEMORY_UPDATER_PROMPT},
        {"role": "user", "content": f"OLD_COACH_STATE: {json.dumps(old_state)}\n\nDIALOGUE_CHUNK: {dialogue_chunk}"}
    ]

    # Using a model capable of good JSON generation
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=messages,
        temperature=1,
        response_format={ "type": "json_object" }
    )
    
    new_state_json = response.choices[0].message.content
    try:
        return json.loads(new_state_json)
    except json.JSONDecodeError:
        print("Error decoding JSON from memory updater")
        return old_state


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: VALIDATION + RETRY POLICY
# ═══════════════════════════════════════════════════════════════════════════════

def validate_coach_state(state: dict) -> tuple[bool, str]:
    """
    Validates that the coach state has all required keys and nested structure.
    Returns (is_valid: bool, error_message: str).
    """
    if not isinstance(state, dict):
        return False, "State is not a dictionary"
    
    # Required top-level keys
    required_top_level = [
        "user_profile", "goals", "current_focus", "next_actions", "plan",
        "blockers", "open_loops", "pattern_analysis", "last_emotional_state",
        "last_session_summary", "updated_at"
    ]
    
    for key in required_top_level:
        if key not in state:
            return False, f"Missing required top-level key: {key}"
    
    # Validate pattern_analysis nested keys
    pattern_analysis_keys = [
        "overall_tone", "stress_level", "dominant_emotions", "confidence_level",
        "signals", "recurring_patterns", "last_session_notes"
    ]
    
    if not isinstance(state.get("pattern_analysis"), dict):
        return False, "pattern_analysis is not a dictionary"
    
    for key in pattern_analysis_keys:
        if key not in state["pattern_analysis"]:
            return False, f"Missing pattern_analysis key: {key}"
    
    # Validate last_emotional_state nested keys
    emotional_state_keys = ["mood_label", "valence", "arousal", "risk_flags"]
    
    if not isinstance(state.get("last_emotional_state"), dict):
        return False, "last_emotional_state is not a dictionary"
    
    for key in emotional_state_keys:
        if key not in state["last_emotional_state"]:
            return False, f"Missing last_emotional_state key: {key}"
    
    return True, ""


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


def safe_update_coach_state(old_state: dict, dialogue_chunk: str) -> tuple[dict, bool, str]:
    """
    Calls update_coach_state with one-retry policy on validation failure.
    Returns (new_state, success: bool, message: str).
    Does NOT modify the core MEMORY_UPDATER_PROMPT.
    """
    from datetime import datetime, timezone
    
    # First attempt
    print("[Memory] Attempting state update (attempt 1/2)...")
    new_state = update_coach_state(old_state, dialogue_chunk)
    
    is_valid, error_msg = validate_coach_state(new_state)
    
    if is_valid:
        # Set updated_at timestamp
        new_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print("[Memory] ✓ State validated successfully on first attempt.")
        return new_state, True, "Success"
    
    # First attempt failed - retry with stricter wrapper
    print(f"[Memory] First attempt failed validation: {error_msg}")
    print("[Memory] Retrying with stricter instructions (attempt 2/2)...")
    
    # Build stricter messages WITHOUT modifying MEMORY_UPDATER_PROMPT
    strict_messages = [
        {"role": "system", "content": MEMORY_UPDATER_PROMPT},
        {"role": "user", "content": "IMPORTANT: Return ONLY valid JSON matching the required schema exactly. No extra text, no markdown, no explanations."},
        {"role": "assistant", "content": "Understood. I will return only valid JSON matching the exact schema."},
        {"role": "user", "content": f"OLD_COACH_STATE: {json.dumps(old_state)}\n\nDIALOGUE_CHUNK: {dialogue_chunk}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=strict_messages,
            temperature=0.5,  # Lower temperature for more deterministic output
            response_format={"type": "json_object"}
        )
        
        retry_state_json = response.choices[0].message.content
        retry_state = json.loads(retry_state_json)
        
        is_valid, error_msg = validate_coach_state(retry_state)
        
        if is_valid:
            retry_state["updated_at"] = datetime.now(timezone.utc).isoformat()
            print("[Memory] ✓ State validated successfully on retry.")
            return retry_state, True, "Success on retry"
        else:
            print(f"[Memory] ✗ Retry also failed validation: {error_msg}")
            return old_state, False, f"Validation failed after retry: {error_msg}"
            
    except json.JSONDecodeError as e:
        print(f"[Memory] ✗ Retry failed with JSON decode error: {e}")
        return old_state, False, f"JSON decode error on retry: {e}"
    except Exception as e:
        print(f"[Memory] ✗ Retry failed with error: {e}")
        return old_state, False, f"Error on retry: {e}"


def perform_memory_update(user_id: str, conv_history: list) -> tuple[bool, str]:
    """
    Core memory update pipeline used by both manual save and auto-save.
    Returns (success: bool, message: str).
    """
    if not user_id:
        return False, "⚠ No user loaded."
    if not conv_history:
        return False, "⚠ No conversation to save."
    
    # Step 7A: Build dialogue chunk with size limits
    dialogue_chunk = build_dialogue_chunk(conv_history, max_turns=40, max_chars=6000)
    
    if not dialogue_chunk:
        return False, "⚠ No valid dialogue to save."
    
    # Fetch fresh state from DB
    old_state = get_or_create_coach_state(user_id)
    
    # Step 7C: Call updater with retry logic
    new_state, success, message = safe_update_coach_state(old_state, dialogue_chunk)
    
    if not success:
        print(f"[Memory] Update failed for {user_id}: {message}")
        return False, f"⚠ Memory update failed: {message}"
    
    # Step 7D: Save to database
    try:
        save_coach_state(user_id, new_state)
        print(f"[Memory] ✓ State saved to database for {user_id}")
        return True, f"✓ Memory updated for {user_id}."
    except Exception as e:
        print(f"[Memory] ✗ Database save failed: {e}")
        return False, f"⚠ Database save failed: {e}"

def load_user_state(user_id):
    """
    Loads user state from database. Resets message counter on new session.
    Returns: (user_id, chatbot_history, conv_history, status, user_msg_count)
    """
    if not user_id or user_id.strip() == "":
        return None, [], [], "Please enter a User ID to start.", 0
    
    user_id = user_id.strip()
    state = get_or_create_coach_state(user_id)
    goals_preview = state.get('goals', [])[:3]
    goals_text = f" Goals: {goals_preview}" if goals_preview else ""
    # Reset counter to 0 on new session
    return user_id, [], [], f"✓ Loaded state for user: {user_id}.{goals_text}", 0

def process_message(user_message, history, user_id, conv_history, user_msg_count):
    """
    Processes user message and handles auto-save trigger every 10 user messages.
    Returns: (chatbot_history, conv_history, msg_input_clear, user_msg_count)
    """
    if not user_id:
        return history, conv_history, "⚠ Please load a User ID first.", user_msg_count
    if not user_message or user_message.strip() == "":
        return history, conv_history, "", user_msg_count
    
    coach_state = get_or_create_coach_state(user_id)
    messages = [{"role": "system", "content": COACH_SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": f"COACH_STATE:\n{json.dumps(coach_state, indent=2)}"})
    messages.append({"role": "assistant", "content": "I've reviewed the COACH_STATE."})
    
    # clean_conv_history ensures we don't mix up types
    clean_conv_history = [m for m in conv_history if isinstance(m, dict) and 'role' in m] if conv_history else []
    for msg in clean_conv_history:
        messages.append(msg)
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = get_message_completion(messages)
    except Exception as e:
        return history, conv_history, f"Error: {str(e)}", user_msg_count
    
    # Append to internal history (dicts for LLM)
    new_conv_history = clean_conv_history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response}
    ]
    
    # For Gradio 6.x: Use messages format (dictionaries) for the chatbot display
    if history is None: history = []
    new_history = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response}
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 6: AUTO-TRIGGER MEMORY UPDATE EVERY 10 USER MESSAGES
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Increment counter only for user messages
    new_count = user_msg_count + 1
    print(f"[AutoSave] User message count: {new_count}/10")
    
    # Check if we've hit the auto-save threshold
    if new_count >= 10:
        print(f"[AutoSave] Triggering auto-save for {user_id} after {new_count} messages...")
        success, message = perform_memory_update(user_id, new_conv_history)
        
        if success:
            print(f"[AutoSave] ✓ Auto-save successful: {message}")
            new_count = 0  # Reset counter on success
        else:
            print(f"[AutoSave] ✗ Auto-save failed: {message}")
            # Keep counter so we retry on next message
    
    return new_history, new_conv_history, "", new_count

def update_memory(user_id, conv_history):
    """
    Manual memory update triggered by the 'Update Memory' button.
    Uses the shared perform_memory_update() pipeline.
    """
    success, message = perform_memory_update(user_id, conv_history)
    return message

with gr.Blocks(title="AI Coach") as demo:
    gr.Markdown("# AI Coaching Assistant (v5-AutoSave)")
    gr.Markdown("Enter your User ID to load your coaching state.")
    
    current_user_id = gr.State(value=None)
    conversation_history = gr.State(value=[])
    user_msg_count = gr.State(value=0)  # STEP 6: Counter for auto-save trigger
    
    with gr.Row():
        user_id_input = gr.Textbox(label="User ID", placeholder="Enter your name or ID...")
        load_btn = gr.Button("Load State", variant="primary")
    status_text = gr.Textbox(label="Status", interactive=False)
    
    # Gradio 6.x uses messages format (dict) by default
    chatbot = gr.Chatbot(label="Conversation", height=400)
        
    msg_input = gr.Textbox(label="Your message", placeholder="Type your message here...")
    
    with gr.Row():
        send_btn = gr.Button("Send", variant="primary")
        save_btn = gr.Button("💾 Update Memory", variant="secondary")
    gr.Markdown("*Memory auto-saves every 10 messages. Click 'Update Memory' to save manually.*")
    
    # STEP 6: Updated wiring with user_msg_count
    load_btn.click(
        fn=load_user_state, 
        inputs=[user_id_input], 
        outputs=[current_user_id, chatbot, conversation_history, status_text, user_msg_count]
    )
    send_btn.click(
        fn=process_message, 
        inputs=[msg_input, chatbot, current_user_id, conversation_history, user_msg_count], 
        outputs=[chatbot, conversation_history, msg_input, user_msg_count]
    )
    msg_input.submit(
        fn=process_message, 
        inputs=[msg_input, chatbot, current_user_id, conversation_history, user_msg_count], 
        outputs=[chatbot, conversation_history, msg_input, user_msg_count]
    )
    save_btn.click(
        fn=update_memory, 
        inputs=[current_user_id, conversation_history], 
        outputs=[status_text]
    )

if __name__ == "__main__":
    demo.launch(share=False)
