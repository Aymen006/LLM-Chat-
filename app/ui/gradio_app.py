import gradio as gr
import json
from app.db.coach_state_repo import get_or_create_coach_state
from app.db.recent_turns_repo import save_turn_pair, load_recent_turns
from app.llm.prompts import COACH_SYSTEM_PROMPT
from app.llm.responder import get_message_completion
from app.memory.updater import perform_memory_update
from app.memory.autosave import check_and_trigger_autosave

# Check version
major_version = int(gr.__version__.split('.')[0])
print(f"Gradio Version: {gr.__version__}")

def load_user_state(user_id):
    """
    Loads user state from database. Resets message counter on new session.
    Returns: (user_id, chatbot_history, conv_history, status, user_msg_count)
    """
    if not user_id or user_id.strip() == "":
        return None, [], [], "Please enter a User ID to start.", 0
    
    user_id = user_id.strip()
    state = get_or_create_coach_state(user_id)
    goals_preview = state.get('goals', [])[:3]
    goals_text = f" Goals: {goals_preview}" if goals_preview else ""
    # Reset counter to 0 on new session
    return user_id, [], [], f"✓ Loaded state for user: {user_id}.{goals_text}", 0

def process_message(user_message, history, user_id, conv_history, user_msg_count):
    """
    Processes user message and handles auto-save trigger every 10 user messages.
    Returns: (chatbot_history, conv_history, msg_input_clear, user_msg_count)
    """
    if not user_id:
        return history, conv_history, "⚠ Please load a User ID first.", user_msg_count
    if not user_message or user_message.strip() == "":
        return history, conv_history, "", user_msg_count
    
    coach_state = get_or_create_coach_state(user_id)
    messages = [{"role": "system", "content": COACH_SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": f"COACH_STATE:\n{json.dumps(coach_state, indent=2)}"})
    messages.append({"role": "assistant", "content": "I've reviewed the COACH_STATE."})
    
    # PHASE 2: Load recent turns from DB for context
    # User Requirement: Inject RECENT_TURNS as a separate context message
    db_history = load_recent_turns(user_id, limit=20)
    if db_history:
        recent_turns_json = json.dumps(db_history, indent=2)
        messages.append({"role": "user", "content": f"RECENT_TURNS:\n{recent_turns_json}"})
        messages.append({"role": "assistant", "content": "I have reviewed the RECENT_TURNS."})
    else:
        messages.append({"role": "user", "content": "RECENT_TURNS: []"})
        messages.append({"role": "assistant", "content": "I have reviewed the RECENT_TURNS."})
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = get_message_completion(messages)
    except Exception as e:
        return history, conv_history, f"Error: {str(e)}", user_msg_count
    
    # Internal history unused but kept for interface compatibility if needed
    new_conv_history = [] 
    
    # For Gradio: Messages format
    if history is None: history = []
    new_history = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response}
    ]
    
    # PHASE 2: Save turns to DB
    save_turn_pair(user_id, user_message, response)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 6: AUTO-TRIGGER MEMORY UPDATE EVERY 10 USER MESSAGES
    # ═══════════════════════════════════════════════════════════════════════════
    
    new_count = check_and_trigger_autosave(user_id, user_msg_count, threshold=10)
    
    return new_history, new_conv_history, "", new_count

def update_memory(user_id, conv_history):
    """
    Manual memory update triggered by the 'Update Memory' button.
    Uses the shared perform_memory_update() pipeline.
    """
    success, message = perform_memory_update(user_id)
    return message

def create_demo():
    with gr.Blocks(title="AI Coach") as demo:
        gr.Markdown("# AI Coaching Assistant (v5-Refactored)")
        gr.Markdown("Enter your User ID to load your coaching state.")
        
        current_user_id = gr.State(value=None)
        conversation_history = gr.State(value=[])
        user_msg_count = gr.State(value=0)  # Counter for auto-save trigger
        
        with gr.Row():
            user_id_input = gr.Textbox(label="User ID", placeholder="Enter your name or ID...")
            load_btn = gr.Button("Load State", variant="primary")
        status_text = gr.Textbox(label="Status", interactive=False)
        
        chatbot = gr.Chatbot(label="Conversation", height=400)
            
        msg_input = gr.Textbox(label="Your message", placeholder="Type your message here...")
        
        with gr.Row():
            send_btn = gr.Button("Send", variant="primary")
            save_btn = gr.Button("💾 Update Memory", variant="secondary")
        gr.Markdown("*Memory auto-saves every 10 messages. Click 'Update Memory' to save manually.*")
        
        load_btn.click(
            fn=load_user_state, 
            inputs=[user_id_input], 
            outputs=[current_user_id, chatbot, conversation_history, status_text, user_msg_count]
        )
        send_btn.click(
            fn=process_message, 
            inputs=[msg_input, chatbot, current_user_id, conversation_history, user_msg_count], 
            outputs=[chatbot, conversation_history, msg_input, user_msg_count]
        )
        msg_input.submit(
            fn=process_message, 
            inputs=[msg_input, chatbot, current_user_id, conversation_history, user_msg_count], 
            outputs=[chatbot, conversation_history, msg_input, user_msg_count]
        )
        save_btn.click(
            fn=update_memory, 
            inputs=[current_user_id, conversation_history], 
            outputs=[status_text]
        )
    return demo
