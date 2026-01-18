from db_functions import get_or_create_coach_state, save_coach_state
from gradio_app_fixed import perform_memory_update
import time

def verify_autosave():
    user_id = "autosave_proof_user"
    print(f"--- Auto-save Verification for {user_id} ---")
    
    # Ensure fresh state
    get_or_create_coach_state(user_id)
    
    # Get initial version
    initial = get_or_create_coach_state(user_id)
    v_start = initial.get("version", 0) # db_functions insert sets version=1, but let's check
    # Actually DB schema might have a version column separate from JSON?
    # No, save_coach_state updates a column "version".
    # get_or_create returns the JSON which doesn't necessarily have it unless we put it there.
    # checking db_functions.py: get_or_create returns response.data[0]["state_json"].
    # save_coach_state updates "version" column.
    # "state_json" might not have version inside it unless we sync it.
    # Let's check the "updated_at" inside JSON, or query the version column directly.
    
    from db_functions import supabase
    res = supabase.table("coach_state").select("version").eq("user_id", user_id).execute()
    v_start_db = res.data[0]["version"] if res.data else 0
    print(f"Initial DB Version: {v_start_db}")
    
    # Simulate 10 messages triggering auto-save
    # We can't easily call process_message 10 times because it calls LLM (slow/costly).
    # But we can call perform_memory_update directly to prove IT increments version.
    # The user asked: "Proof auto-save every 10 user messages still triggers".
    # This implies verifying the TRIGGER logic in process_message.
    # But I can't mock the 10 clicks easily without browser. 
    # Browser is best.
    pass

if __name__ == "__main__":
    # verification via browser is better for "trigger" logic.
    # This script is a placeholder to remind me.
    pass
