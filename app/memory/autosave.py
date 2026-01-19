from app.memory.updater import perform_memory_update

def check_and_trigger_autosave(user_id: str, current_count: int, threshold: int = 10) -> int:
    """
    Checks if autosave should be triggered.
    Returns new_count (0 if triggered, else current_count).
    """
    # Increment counter
    new_count = current_count + 1
    print(f"[AutoSave] User message count: {new_count}/{threshold}")
    
    if new_count >= threshold:
        print(f"[AutoSave] Triggering auto-save for {user_id} after {new_count} messages...")
        success, message = perform_memory_update(user_id)
        
        if success:
            print(f"[AutoSave] ✓ Auto-save successful: {message}")
            return 0  # Reset
        else:
            print(f"[AutoSave] ✗ Auto-save failed: {message}")
            # Keep count to retry next time? Or reset?
            # Original logic kept count to retry.
            return new_count 
            
    return new_count
