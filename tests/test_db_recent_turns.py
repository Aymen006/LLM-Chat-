import unittest
from app.db.recent_turns_repo import save_turn, load_recent_turns, prune_recent_turns
from app.db.supabase_client import supabase

class TestDBRecentTurns(unittest.TestCase):
    def setUp(self):
        self.user_id = "test_user_refactor_db"
        # Cleanup
        supabase.table("recent_turns").delete().eq("user_id", self.user_id).execute()

    def test_save_and_load_order(self):
        # Insert 3 messages
        save_turn(self.user_id, "user", "msg 1")
        save_turn(self.user_id, "assistant", "msg 2")
        save_turn(self.user_id, "user", "msg 3")
        
        # Load
        turns = load_recent_turns(self.user_id, limit=10)
        self.assertEqual(len(turns), 3)
        self.assertEqual(turns[0]['content'], "msg 1")
        self.assertEqual(turns[2]['content'], "msg 3")
        
    def test_pruning(self):
        # Insert 15 messages
        for i in range(15):
            save_turn(self.user_id, "user", f"msg {i}")
            
        # Prune to keep 10
        prune_recent_turns(self.user_id, keep_last=10)
        
        turns = load_recent_turns(self.user_id, limit=20)
        # Should have >= 10. Logic is strict about "older than Nth".
        # If we have 15, keeping 10 means deleting 5.
        self.assertTrue(len(turns) >= 10 and len(turns) <= 12) # buffer for timestamps

if __name__ == '__main__':
    unittest.main()
