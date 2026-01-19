from openai import OpenAI
import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError("Missing OPENAI_API_KEY. Put it in your .env file")

# Strip any quotes that might be included
api_key = api_key.strip('"').strip("'")

# Initialize the OpenAI client
client = OpenAI(api_key=api_key)
