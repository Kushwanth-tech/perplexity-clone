import os
import io
import time
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
import PyPDF2

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
# Enable CORS for cross-origin frontend requests
CORS(app)

# Initialize Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# Candidate models in order of priority
AVAILABLE_MODELS = [
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
    'gemma-3-4b-it'
]

# Store uploaded document context per thread
pdf_contexts = {}

def extract_document_text(file):
    filename = file.filename.lower()
    try:
        data = file.read()
        if filename.endswith('.pdf'):
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        elif filename.endswith('.docx'):
            with zipfile.ZipFile(io.BytesIO(data)) as docx:
                xml_content = docx.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                return "".join(tree.itertext()).strip()
        else:
            # TXT, Markdown, CSV, etc.
            return data.decode('utf-8', errors='ignore').strip()
    except Exception as e:
        print(f"Extraction error for {filename}: {e}")
        return ""

def extract_source_info(item):
    url = item.get('url') or item.get('href', '')
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '') if parsed.netloc else 'web'
    home_page = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else url
    return {
        'title': (item.get('title') or domain).strip(),
        'snippet': (item.get('body') or '').strip(),
        'url': url,
        'domain': domain,
        'home_page': home_page
    }

def search_web(query, max_results=4):
    """Perform real-time web search for current events and queries."""
    try:
        from ddgs import DDGS
        ddg = DDGS()
        results = []
        clean_q = query.strip()

        # Check if query likely pertains to live scores, recent news, or current events
        keywords = ['latest', 'match', 'score', 'today', 'news', 'result', 'live', 
                    'update', 'current', 'vs', 'yesterday', 'who won', 't20', 'ipl', 
                    'weather', 'stock', 'price', 'winner', 'schedule']
        is_news = any(k in clean_q.lower() for k in keywords)

        if is_news:
            try:
                news_items = list(ddg.news(clean_q, max_results=max_results))
                for item in news_items:
                    results.append(extract_source_info(item))
            except Exception as e:
                print(f"DDGS news search exception: {e}")

        # If news returned nothing or for general informational queries, use web text search
        if not results:
            text_items = list(ddg.text(clean_q, max_results=max_results))
            for item in text_items:
                results.append(extract_source_info(item))

        return results[:max_results]
    except Exception as e:
        print(f"Web search error: {e}")
        return []

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    global pdf_contexts
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    thread_id = request.form.get('thread_id', 'default')
    
    if not file or file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    doc_text = extract_document_text(file)
    if doc_text:
        # Cap text length to prevent context window overflow
        if len(doc_text) > 35000:
            doc_text = doc_text[:35000] + "\n\n[... Note: Document truncated to fit model context ...]"
        
        pdf_contexts[thread_id] = {
            "filename": file.filename,
            "content": doc_text
        }
        return jsonify({
            "message": "Document uploaded and processed successfully",
            "filename": file.filename
        })
    else:
        return jsonify({"error": "Could not extract text from document (file may be empty, image-only, or unsupported)."}), 400

@app.route('/api/chat', methods=['POST'])
def chat():
    global pdf_contexts
    try:
        if not client:
            return jsonify({"error": "GEMINI_API_KEY is not configured in .env"}), 500

        data = request.get_json(silent=True) or {}
        prompt = (data.get('prompt') or '').strip()
        history = data.get('history', [])
        thread_id = data.get('thread_id', 'default')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        doc_data = pdf_contexts.get(thread_id)
        greetings = {'hi', 'hii', 'hiii', 'hello', 'hey', 'heyy', 'good morning', 'good evening', 'good afternoon', 'how are you'}
        is_greeting = prompt.lower().rstrip('!?. ') in greetings

        sources = []
        full_prompt = prompt

        if doc_data and doc_data.get('content'):
            # Document Q&A Mode
            filename = doc_data.get('filename', 'Attached Document')
            content = doc_data.get('content', '')
            full_prompt = f"""[DOCUMENT CONTEXT:
File: "{filename}"
Content:
---
{content}
---
Instructions:
The user says: "{prompt}".
Answer, summarize, or explain based on the document text provided above.
If the user's message is a simple greeting like "hii", acknowledge the greeting politely and let them know you're ready to answer questions about "{filename}".
]"""

        elif not is_greeting:
            # Perplexity Web Search Mode
            print(f"Searching web for: {prompt}")
            web_results = search_web(prompt, max_results=4)
            if web_results:
                sources = web_results
                context_str = "\n\n".join([
                    f"[{i+1}] {r['title']}\nSnippet: {r['snippet']}\nURL: {r['url']}"
                    for i, r in enumerate(web_results)
                ])
                full_prompt = f"""[LIVE WEB SEARCH RESULTS:
{context_str}

Instructions:
Answer the user's query: "{prompt}" thoroughly, cleanly, and directly using the search results above.
- Synthesize the most relevant information with well-structured markdown (headings, bullets, or tables when appropriate).
- Cite your sources in the text using bracketed numbers like [1], [2] immediately following the facts derived from them.
- Do NOT output a separate "### Sources" list or URLs at the end of your response, as the interface automatically displays dedicated source cards.
]"""

        contents = history + [{"role": "user", "parts": [{"text": full_prompt}]}]

        # Try models with automatic fallback on quota exhaustion or errors
        last_error = None
        for model_name in AVAILABLE_MODELS:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
                    
                    response_text = ""
                    try:
                        response_text = response.text or ""
                    except Exception:
                        pass
                    
                    if not response_text and response.candidates:
                        cand = response.candidates[0]
                        if cand.content and cand.content.parts:
                            response_text = "".join(
                                [p.text for p in cand.content.parts if hasattr(p, 'text') and p.text]
                            )

                    if response_text:
                        return jsonify({
                            "response": response_text,
                            "model": model_name,
                            "sources": sources
                        })
                    else:
                        return jsonify({
                            "response": "The model produced an empty response or content was filtered by safety guidelines.",
                            "sources": sources
                        })

                except Exception as e:
                    err_str = str(e)
                    last_error = e
                    print(f"Model {model_name} (Attempt {attempt+1}) error: {err_str[:120]}")
                    
                    # If 429 or 503, brief wait then try fallback
                    if ("429" in err_str or "503" in err_str or "UNAVAILABLE" in err_str) and attempt == 0:
                        time.sleep(1)
                        continue
                    break

        raise last_error if last_error else Exception("All models failed to respond.")

    except Exception as e:
        print(f"Error in /api/chat: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_context():
    global pdf_contexts
    data = request.get_json(silent=True) or {}
    thread_id = data.get('thread_id', 'default')
    if thread_id in pdf_contexts:
        del pdf_contexts[thread_id]
        return jsonify({"message": f"Context cleared for thread {thread_id}"})
    return jsonify({"message": f"No active context found for thread {thread_id}"})

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
