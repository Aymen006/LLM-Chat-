from app.llm.client import client
from app.llm.prompts import MEMORY_UPDATER_PROMPT
from app.utils.validation import validate_coach_state
from app.db.coach_state_repo import get_or_create_coach_state, save_coach_state
from app.db.recent_turns_repo import load_recent_turns
from app.memory.dialogue_chunk import build_dialogue_chunk
import json
from datetime import datetime, timezone

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


def safe_update_coach_state(old_state: dict, dialogue_chunk: str) -> tuple[dict, bool, str]:
    """
    Calls update_coach_state with one-retry policy on validation failure.
    Returns (new_state, success: bool, message: str).
    Does NOT modify the core MEMORY_UPDATER_PROMPT.
    """
    
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
            temperature=1,  # gpt-5-nano requires temp 1
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


def perform_memory_update(user_id: str) -> tuple[bool, str]:
    """
    Core memory update pipeline used by both manual save and auto-save.
    Returns (success: bool, message: str).
    """
    if not user_id:
        return False, "⚠ No user loaded."
    
    # Step 7A: Build dialogue chunk from DB (Phase 2)
    # Fetch recent turns from DB instead of in-memory history
    # Limit fetch to 40 turns, cap strings at 6000 chars
    db_history = load_recent_turns(user_id, limit=40)
    dialogue_chunk = build_dialogue_chunk(db_history, max_turns=40, max_chars=6000)
    
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
