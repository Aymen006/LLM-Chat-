import unittest
from unittest.mock import patch
from app.memory.autosave import check_and_trigger_autosave

class TestAutosave(unittest.TestCase):
    @patch('app.memory.autosave.perform_memory_update')
    def test_trigger_logic(self, mock_perform):
        mock_perform.return_value = (True, "Success")
        
        # 9 messages -> 10 (trigger)
        new_count = check_and_trigger_autosave("user", 9, threshold=10)
        self.assertEqual(new_count, 0) # Should reset
        mock_perform.assert_called_once()
        
        mock_perform.reset_mock()
        
        # 5 messages -> 6 (no trigger)
        new_count = check_and_trigger_autosave("user", 5, threshold=10)
        self.assertEqual(new_count, 6)
        mock_perform.assert_not_called()

if __name__ == '__main__':
    unittest.main()
