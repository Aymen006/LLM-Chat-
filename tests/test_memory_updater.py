import unittest
from unittest.mock import MagicMock, patch
from app.memory.updater import safe_update_coach_state

class TestMemoryUpdater(unittest.TestCase):
    @patch('app.memory.updater.client')
    @patch('app.memory.updater.update_coach_state')
    def test_validation_retry_logic(self, mock_update, mock_client):
        # Mock first attempt failure (missing keys)
        mock_update.return_value = {"invalid": "json"}
        
        # Mock retry success via direct client call
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        # Use a minimal valid state string
        valid_json_str = '{"user_profile": {"name": "Test", "preferences": {"tone": "direct", "accountability": "high", "constraints": []}}, "goals": [], "current_focus": "", "next_actions": [], "plan": [], "blockers": [], "open_loops": [], "pattern_analysis": {"overall_tone": "neutral", "stress_level": 0, "dominant_emotions": [], "confidence_level": 0, "signals": [], "recurring_patterns": [], "last_session_notes": ""}, "last_emotional_state": {"mood_label": "neutral", "valence": 0, "arousal": 0, "risk_flags": []}, "last_session_summary": "", "updated_at": ""}'
        
        mock_completion.choices[0].message.content = valid_json_str
        mock_client.chat.completions.create.return_value = mock_completion
        
        old_state = {"some": "state"} 
        # Attempt to run update logic
        new_state, success, msg = safe_update_coach_state(old_state, "chunk")
        
        # Assertions
        # The retry path should have triggered and supposedly succeeded if our mock returns valid JSON.
        self.assertTrue(success, f"Failed: {msg}")
        self.assertEqual(new_state["user_profile"]["name"], "Test")
        
        # Verify first attempt was called
        mock_update.assert_called_once()
        # Verify retry via client was called
        mock_client.chat.completions.create.assert_called_once()
        
    @patch('app.memory.updater.update_coach_state')
    def test_successful_first_try(self, mock_update):
        valid_state = {
            "user_profile": {"name": "Test", "preferences": {"tone": "direct", "accountability": "high", "constraints": []}},
            "goals": [],
            "current_focus": "",
            "next_actions": [],
            "plan": [],
            "blockers": [],
            "open_loops": [],
            "pattern_analysis": {
                "overall_tone": "neutral", "stress_level": 0, "dominant_emotions": [], "confidence_level": 0,
                "signals": [], "recurring_patterns": [], "last_session_notes": ""
            },
            "last_emotional_state": {
                "mood_label": "neutral", "valence": 0, "arousal": 0, "risk_flags": []
            },
            "last_session_summary": "",
            "updated_at": ""
        }
        mock_update.return_value = valid_state
        
        result, success, msg = safe_update_coach_state({}, "chunk")
        self.assertTrue(success)
        self.assertEqual(result["user_profile"]["name"], "Test")

if __name__ == '__main__':
    unittest.main()
