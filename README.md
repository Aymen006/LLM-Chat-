# AI Coaching Chatbot

A production-ready AI coaching assistant built with Gradio, OpenAI (GPT-5 Nano), and Supabase.

## Architecture

The project is structured as a modular Python application:

```
app/
├── db/          # Database repositories (Supabase)
├── llm/         # Logic for OpenAI interaction & Prompts
├── memory/      # State management, Auto-save, & Updater logic
├── ui/          # Gradio interface definition
└── utils/       # shared utilities (logging, validation)
```

## Setup & specific Environment Variables

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Copy `.env.example` to `.env` and fill in:
   - `OPENAI_API_KEY`: Your OpenAI key
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_ANON_KEY`: Your Supabase anonymous key

## Running the Application

To start the local development server:

```bash
python3 -m app.main
```

The app will launch at `http://127.0.0.1:7860`.

## Features

- **Long-term Memory**: Persists user goals, plans, and blockers in `coach_state` table.
- **Context Injection**: Injects the last 20 conversation turns from `recent_turns` table.
- **Auto-Save**: Triggers memory update analysis every 10 user messages.
- **Manual Update**: "Update Memory" button available for immediate sync.
- **Robust Persistence**: State survives server restarts.

## Testing

Run the unit test suite:

```bash
python -m unittest discover tests
```
