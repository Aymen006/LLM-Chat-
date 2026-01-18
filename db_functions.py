"""
Database access functions for coach_state persistence.
Uses Supabase Python client.
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: RECENT TURNS PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

def save_turn(user_id: str, role: str, content: str) -> None:
    """
    Save a single turn to recent_turns.
    """
    if role not in ('user', 'assistant'):
        raise ValueError(f"Invalid role: {role}")
    
    try:
        supabase.table("recent_turns").insert({
            "user_id": user_id,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        print(f"Error in save_turn: {e}")
        # We assume fire-and-forget for history to avoid blocking chat
        pass

def save_turn_pair(user_id: str, user_text: str, assistant_text: str) -> None:
    """
    Save a pair of turns (user + assistant) in one batch if possible.
    Includes auto-pruning every 50 turns approx (random check or simple count).
    """
    try:
        # Batch insert
        rows = [
            {"user_id": user_id, "role": "user", "content": user_text},
            {"user_id": user_id, "role": "assistant", "content": assistant_text}
        ]
        supabase.table("recent_turns").insert(rows).execute()
        
        # Simple probability-based pruning to avoid counting every time
        # Or just prune unconditionally if cheap. Let's do unconditional for safety first.
        # But checking count is expensive. Let's prune blindly "keep last N" every time? 
        # No, that's heavy. Let's call prune_recent_turns every time for now as per requirements
        # "after each memory save ... OR every X inserts".
        # We will call it here to be safe and simple.
        # To optimize, we can check a global counter or randomness.
        # For this phase, let's keep it simple: prune every time is robust but slow.
        # Let's use a 1/10 chance to prune.
        import random
        if random.random() < 0.1:
            prune_recent_turns(user_id)
            
    except Exception as e:
        print(f"Error in save_turn_pair: {e}")

def load_recent_turns(user_id: str, limit: int = 30) -> list[dict]:
    """
    Load last N turns for user_id in chronological order.
    Returns: [{"role": "user", "content": "..."}, ...]
    """
    try:
        response = supabase.table("recent_turns")\
            .select("role, content")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        # Reverse to get chronological order (oldest -> newest)
        return list(reversed(response.data)) if response.data else []
    except Exception as e:
        print(f"Error in load_recent_turns: {e}")
        return []

def prune_recent_turns(user_id: str, keep_last: int = 500) -> None:
    """
    Delete turns older than the newest keep_last rows.
    Uses subquery deletion for safety.
    """
    try:
        # Find the ID of the Nth most recent row
        # We want to keep IDs >= (SELECT id FROM ... ORDER BY created_at DESC LIMIT 1 OFFSET keep_last-1)
        # Actually easier to delete IDs NOT IN top N.
        
        # Supabase/Postgrest delete with filtered logic is tricky via JS client syntax.
        # We can use a stored procedure if available, but requirements asked for Python.
        # We'll use a two-step approach: fetch the cutoff ID, then delete < cutoff.
        
        response = supabase.table("recent_turns")\
            .select("id")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .offset(keep_last)\
            .execute()
            
        if response.data:
            # This is the first ID to *DELETE* (or keep? wait)
            # offset 500 means we skipped 500. So the 501st row.
            # We want to delete anything older than or equal to this row.
            # Assuming IDs increase with time (mostly true but created_at is better).
            # Created_at based cut-off is safer.
            
            # Let's get the timestamp of the 500th item (boundary).
            cutoff_response = supabase.table("recent_turns")\
                .select("created_at")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(1)\
                .offset(keep_last)\
                .execute()
                
            if cutoff_response.data:
                cutoff_time = cutoff_response.data[0]['created_at']
                
                # Delete rows strictly older than cutoff (or equal if we want to be strict about count)
                # "lte" (less than or equal) might delete the 500th item depending on precision.
                # "lt" (less than) the 500th's timestamp keeps the 500th.
                # But if duplicates exist... straightforward is to allow small buffer.
                supabase.table("recent_turns")\
                    .delete()\
                    .eq("user_id", user_id)\
                    .lt("created_at", cutoff_time)\
                    .execute()
                    
    except Exception as e:
        print(f"Error in prune_recent_turns: {e}")
