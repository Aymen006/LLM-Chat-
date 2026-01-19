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
