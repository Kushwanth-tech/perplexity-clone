import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents="Hello, say 'Test Passed' if you can read this."
    )
    print(f"RESPONSE: {response.text}")
except Exception as e:
    print(f"ERROR: {str(e)}")
