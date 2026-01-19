from app.db.supabase_client import supabase
import random

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
        # Let's use a 1/10 chance to prune.
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
