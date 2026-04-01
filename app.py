import os
import io
import time
import random
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
import PyPDF2

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
# Enable CORS so the frontend can communicate with this API
CORS(app)

# Initialize Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Store PDF context per thread
pdf_contexts = {}

def extract_text_from_pdf(file):
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Extraction Error: {str(e)}")
        return ""

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    global pdf_contexts
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    thread_id = request.form.get('thread_id', 'default')
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and file.filename.endswith('.pdf'):
        pdf_content = extract_text_from_pdf(file)
        if pdf_content:
            pdf_contexts[thread_id] = pdf_content
            return jsonify({"message": "PDF uploaded and processed successfully", "filename": file.filename})
        else:
            return jsonify({"error": "Failed to extract text from PDF"}), 500
    
    return jsonify({"error": "Invalid file type. Please upload a PDF."}), 400

@app.route('/api/chat', methods=['POST'])
def chat():
    global pdf_contexts
    try:
        data = request.json
        prompt = data.get('prompt')
        history = data.get('history', [])
        thread_id = data.get('thread_id', 'default')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        # Implement flexible RAG by injecting PDF context
        full_prompt = prompt
        pdf_context = pdf_contexts.get(thread_id, "")
        if pdf_context:
            print(f"DEBUG: Using PDF context for thread {thread_id} (Length: {len(pdf_context)})")
            full_prompt = f"""[SYSTEM: A document is currently uploaded and active in this chat.
Document text:
---
{pdf_context}
---
Instructions:
1. If the user's question is about the document, or implies the document (e.g., "answer these", "summarize", "what is this about"), use the document text to answer.
2. If the user is just saying a casual greeting (e.g., "hii", "hello"), or asking a completely unrelated question (e.g., "what is the capital of France?"), IGNORE the document entirely and just answer naturally as a normal chat assistant. Do not mention that their greeting or question is not in the document.
]

User: {prompt}
"""

        # Implement Exponential Backoff for 429 and 503 errors
        max_retries = 5
        retry_delay = 2  # Starting delay in seconds
        
        for i in range(max_retries):
            try:
                # Using gemma-3-4b-it as it still has available free quota
                response = client.models.generate_content(
                    model='gemma-3-4b-it',
                    contents=history + [{"role": "user", "parts": [{"text": full_prompt}]}]
                )
                return jsonify({ "response": response.text })
                
            except Exception as e:
                err_msg = str(e)
                # Check for 429 (Resource Exhausted) or 503 (Unavailable)
                if ("429" in err_msg or "503" in err_msg or "UNAVAILABLE" in err_msg) and i < max_retries - 1:
                    wait_time = retry_delay * (2 ** i) + random.uniform(0, 1)
                    print(f"RETRYING: Hit {err_msg[:20]}... Retrying in {wait_time:.2f}s... (Attempt {i+1})")
                    time.sleep(wait_time)
                else:
                    raise e

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_context():
    global pdf_contexts
    data = request.json or {}
    thread_id = data.get('thread_id', 'default')
    if thread_id in pdf_contexts:
        del pdf_contexts[thread_id]
    return jsonify({"message": f"Context cleared for thread {thread_id}"})

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
