from app.db.supabase_client import supabase

# INITIAL_STATE must match the structure used in the Memory Updater
INITIAL_STATE = {
    "user_profile": {"name": None, "preferences": {"tone": "direct", "accountability": "high", "constraints": []}},
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

def get_or_create_coach_state(user_id: str) -> dict:
    """
    Retrieve existing coach_state for user_id, or create a new one with INITIAL_STATE.
    Returns the state as a Python dict.
    """
    try:
        response = supabase.table("coach_state").select("state_json").eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            # Row exists, return the state
            return response.data[0]["state_json"]
        else:
            # Row does not exist, insert new row
            new_row = {
                "user_id": user_id,
                "state_json": INITIAL_STATE,
                "version": 1
            }
            insert_response = supabase.table("coach_state").insert(new_row).execute()
            
            if insert_response.data:
                return INITIAL_STATE
            else:
                raise Exception(f"Failed to insert new coach_state for user_id: {user_id}")
    except Exception as e:
        print(f"Error in get_or_create_coach_state: {e}")
        # For read failures, return INITIAL_STATE to avoid crashing
        return INITIAL_STATE


def save_coach_state(user_id: str, new_state: dict) -> None:
    """
    Update coach_state for user_id with new_state.
    Increments version and updates updated_at.
    Raises on failure.
    """
    try:
        # First get current version
        response = supabase.table("coach_state").select("version").eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            current_version = response.data[0]["version"]
        else:
            current_version = 0
        
        # Update the row
        update_response = supabase.table("coach_state").update({
            "state_json": new_state,
            "version": current_version + 1,
            "updated_at": "now()"  # Supabase handles this as SQL now()
        }).eq("user_id", user_id).execute()
        
        if not update_response.data:
            raise Exception(f"Failed to update coach_state for user_id: {user_id}")
            
    except Exception as e:
        print(f"Error in save_coach_state: {e}")
        raise  # Re-raise to fail loudly on write errors
