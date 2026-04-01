import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

models_to_test = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-pro-latest",
    "gemma-3-4b-it"
]

for m in models_to_test:
    try:
        print(f"Testing {m}...")
        response = client.models.generate_content(
            model=m,
            contents="Say hi."
        )
        print(f"SUCCESS with {m}! Response: {response.text}")
        break
    except Exception as e:
        print(f"ERROR on {m}: {str(e)[:100]}")
