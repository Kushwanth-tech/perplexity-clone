import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents="Hello, this is a test for 'gemini-flash-latest'. Reply with 'Flash Latest Active'."
    )
    print(f"RESPONSE: {response.text}")
except Exception as e:
    print(f"ERROR: {str(e)}")
