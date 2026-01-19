from app.ui.gradio_app import create_demo
from dotenv import load_dotenv, find_dotenv

if __name__ == "__main__":
    # Load env vars
    load_dotenv(find_dotenv())
    
    demo = create_demo()
    demo.launch(share=False)
