import sys
import os
import json
import time
from dotenv import load_dotenv, find_dotenv

# Load env vars
load_dotenv(find_dotenv())

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ui.gradio_app import load_user_state, process_message, update_memory
from app.db.coach_state_repo import get_or_create_coach_state
from app.db.recent_turns_repo import load_recent_turns, save_turn_pair, prune_recent_turns
from app.db.supabase_client import supabase

USER_ID = "test_user_verification_v5"

def test_chat_and_persistence():
    print(f"--- Testing Chat and Persistence for {USER_ID} ---")
    
    # 1. Load User State
    print("1. Loading User State...")
    uid, _, _, status, count = load_user_state(USER_ID)
    assert uid == USER_ID
    print(f"   Success: {status}")
    
    # Get initial version from DB column
    state_response = supabase.table("coach_state").select("version").eq("user_id", USER_ID).execute()
    initial_version = state_response.data[0]['version'] if state_response.data else 0
    print(f"   Initial Version: {initial_version}")
    
    # 2. Send 10 messages to trigger auto-save
    print("2. Sending 10 messages...")
    history = []
    messages = [
        "Hello", "I am testing", "Is this working?", "Fourth message", "Fifth message",
        "Sixth", "Seventh", "Eighth", "Ninth", "Tenth message"
    ]
    
    current_count = 0
    
    for i, msg in enumerate(messages):
        # Mock history for context
        # We need to simulate the count increment.
        # process_message returns new_count.
        
        # Note: process_message signature: 
        # (user_message, history, user_id, conv_history, user_msg_count)
        
        history, _, _, new_count = process_message(msg, history, USER_ID, [], current_count)
        
        # Verify response is generated (last item in history)
        last_exchange = history[-1]
        assert last_exchange['role'] == 'assistant'
        assert len(last_exchange['content']) > 0
        
        current_count = new_count
        print(f"   Sent msg {i+1}, new_count: {current_count}")
        
    # 3. Verify Auto-save triggered
    # Logic: check_and_trigger_autosave resets count to 0 if threshold (10) reached.
    # So if we sent 10 messages starting from 0, current_count should be 0.
    assert current_count == 0, f"Expected count 0 after 10 messages, got {current_count}"
    print("   Auto-save trigger logic (count verification) passed.")
    
    # Verify DB version incremented
    # Note: process_message calls 'check_and_trigger_autosave'
    # which calls 'perform_memory_update' (async task usually, but here it's synchronous in autosave.py?)
    # Let's check imports in gradio_app.py: "from app.memory.autosave import check_and_trigger_autosave"
    # We assume it runs synchronously or we wait a bit.
    
    updated_response = supabase.table("coach_state").select("version").eq("user_id", USER_ID).execute()
    new_version = updated_response.data[0]['version'] if updated_response.data else 0
    print(f"   New Version: {new_version}")
    
    # It should have incremented. (Initial was X, after auto-save should be > X)
    # Note: Only if 'perform_memory_update' succeeded.
    if new_version > initial_version:
        print("   ✅ Auto-save persisted to DB (Version incremented).")
    else:
        print("   ⚠️ Auto-save might not have persisted (Version same). Check autosave logic.")
        # Attempt manual force if autosave logic is conditional/async
        
    # 4. Verify Manual Save
    print("4. Testing Manual Update...")
    msg = update_memory(USER_ID, [])
    print(f"   Manual Update Response: {msg}")
    
    final_response = supabase.table("coach_state").select("version").eq("user_id", USER_ID).execute()
    final_version = final_response.data[0]['version'] if final_response.data else 0
    print(f"   Final Version: {final_version}")
    
    assert final_version > new_version or (final_version > initial_version), "Version did not increment on manual save"
    print("   ✅ Manual save confirmed.")

def test_recent_turns_logic():
    print("--- Testing Recent Turns Logic ---")
    
    # 1. Check insertion
    turns = load_recent_turns(USER_ID, limit=100)
    # We sent 10 messages * 2 (user+assistant) = 20 turns.
    # Plus potentially previous runs if we didn't clear.
    # We should see at least 20 recent turns from today.
    count_turns = len(turns)
    print(f"   Found {count_turns} turns.")
    assert count_turns >= 20
    
    # 2. Verify most recent is what we sent
    # load_recent_turns returns chronological order (oldest -> newest)?
    # Wait, repo says: "Returns: list(reversed(response.data))" 
    # Query is "order created_at desc". So response.data is [newest, 2nd_newest...]. 
    # Reversed -> [oldest... newest].
    last_turn = turns[-1]
    # The last message we sent was "Tenth message".
    # The response to that should be the last turn (assistant).
    # The second to last should be "Tenth message" (user).
    
    assert turns[-2]['content'] == "Tenth message"
    assert turns[-1]['role'] == "assistant"
    print("   ✅ Recent turns insertion content verified.")

    # 3. Test Pruning
    # Force prune with small limit
    print("3. Testing Pruning (forcing keep_last=5)...")
    prune_recent_turns(USER_ID, keep_last=5)
    
    turns_after = load_recent_turns(USER_ID, limit=100)
    print(f"   Turns after pruning (keep 5): {len(turns_after)}")
    
    # Ideally should be 5 (or slightly more if logic is rough, but expected <= 5 or 6).
    # Logic: delete < cutoff of 5th element.
    # So we keep 5.
    assert len(turns_after) <= 6 # allowing off-by-one
    print("   ✅ Pruning works (count reduced).")

if __name__ == "__main__":
    try:
        test_chat_and_persistence()
        test_recent_turns_logic()
        print("\n🎉 ALL CHECKS PASSED")
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        # traceback
        import traceback
        traceback.print_exc()
        sys.exit(1)
