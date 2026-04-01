import os

filepath = 'script.js'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. State setup
state_insert = """
    // State management
    let chatHistory = [];
    let isFileAttached = false;
    let currentFileName = "";
    
    // Multi-thread management
    let currentThreadId = Date.now().toString();
    const MAX_THREADS = 6;
"""
content = content.replace("    // State management\n    let chatHistory = [];\n    let isFileAttached = false;\n    let currentFileName = \"\";", state_insert)

# 2. Thread logic functions
thread_logic = """
    function loadThreads() {
        const saved = localStorage.getItem('perplexity_threads');
        return saved ? JSON.parse(saved) : [];
    }

    function saveThreads(threads) {
        localStorage.setItem('perplexity_threads', JSON.stringify(threads));
        renderRecentThreads();
    }
    
    function saveCurrentThread(title) {
        let threads = loadThreads();
        let existingIndex = threads.findIndex(t => t.id === currentThreadId);
        
        const threadData = {
            id: currentThreadId,
            title: title || (threads[existingIndex] ? threads[existingIndex].title : "New Chat"),
            history: chatHistory,
            html: chatMessages.innerHTML,
            updatedAt: Date.now()
        };
        
        if (existingIndex >= 0) {
            threads[existingIndex] = threadData;
        } else {
            threads.unshift(threadData);
            if (threads.length > MAX_THREADS) {
                const oldest = threads.pop();
                fetch('http://localhost:5000/api/clear', { 
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ thread_id: oldest.id })
                }).catch(()=>{});
            }
        }
        
        threads.sort((a,b) => b.updatedAt - a.updatedAt);
        saveThreads(threads);
    }

    function switchThread(id) {
        const threads = loadThreads();
        const thread = threads.find(t => t.id === id);
        if (thread) {
            currentThreadId = thread.id;
            chatHistory = thread.history || [];
            chatMessages.innerHTML = thread.html || '';
            renderRecentThreads();
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'auto' });
        }
    }

    function renderRecentThreads() {
        const listDiv = document.getElementById('recent-threads-list');
        const emptyMsg = document.getElementById('recent-threads-empty');
        const threads = loadThreads();
        
        if (!listDiv || !emptyMsg) return;
        
        if (threads.length === 0) {
            emptyMsg.classList.remove('hidden');
            listDiv.innerHTML = '';
            return;
        }
        
        emptyMsg.classList.add('hidden');
        listDiv.innerHTML = threads.map(t => `
            <div class="thread-item ${t.id === currentThreadId ? 'active' : ''}" data-id="${t.id}">
                <div class="thread-item-title"><i class="ph ph-chat-teardrop-text" style="font-size: 14px; margin-right: 6px;"></i> ${t.title}</div>
                <button class="delete-thread-btn" title="Delete conversation"><i class="ph ph-trash"></i></button>
            </div>
        `).join('');
        
        listDiv.querySelectorAll('.thread-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if(!e.target.closest('.delete-thread-btn')) {
                    switchThread(item.dataset.id);
                }
            });
            
            const delBtn = item.querySelector('.delete-thread-btn');
            if(delBtn) {
                delBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteThread(item.dataset.id);
                });
            }
        });
    }

    function deleteThread(id) {
        let threads = loadThreads();
        threads = threads.filter(t => t.id !== id);
        saveThreads(threads);
        
        fetch('http://localhost:5000/api/clear', { 
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ thread_id: id })
        }).catch(()=>{});

        if (currentThreadId === id) {
            startNewThread();
        }
    }
    
    function startNewThread() {
        currentThreadId = Date.now().toString();
        chatMessages.innerHTML = '';
        chatHistory = [];
        renderRecentThreads();
    }
    
    // Initial render
    renderRecentThreads();

    function appendUserMessage(text, fileName = "") {
"""
content = content.replace("    function appendUserMessage(text, fileName = \"\") {", thread_logic)

# 3. Handle upload thread_id
content = content.replace("formData.append('file', file);", "formData.append('file', file);\n            formData.append('thread_id', currentThreadId);")

# 4. Handle search thread_id & save history
search_req = """
                body: JSON.stringify({ 
                    prompt: query,
                    history: chatHistory,
                    thread_id: currentThreadId
                }),
"""
content = content.replace("body: JSON.stringify({ \n                    prompt: query,\n                    history: chatHistory\n                }),", search_req.strip())

save_step = """
            if (data.response) {
                appendAiMessage(data.response);
                
                // Set title to first query if new
                let threads = loadThreads();
                let isNew = !threads.find(t => t.id === currentThreadId);
                let title = isNew ? query : null;

                chatHistory.push({ role: 'user', parts: [{ text: query }] });
                chatHistory.push({ role: 'model', parts: [{ text: data.response }] });
                
                saveCurrentThread(title);
            }
"""
old_save_step = """
            if (data.response) {
                appendAiMessage(data.response);
                chatHistory.push({ role: 'user', parts: [{ text: query }] });
                chatHistory.push({ role: 'model', parts: [{ text: data.response }] });
            }
"""
content = content.replace(old_save_step.strip(), save_step.strip())

# 5. Handle New Thread button
new_thread_old = """
    if (newThreadBtn) {
        newThreadBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            chatMessages.innerHTML = '';
            chatHistory = [];
            try {
                await fetch('http://localhost:5000/api/clear', { method: 'POST' });
"""
new_thread_new = """
    if (newThreadBtn) {
        newThreadBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            startNewThread();
            try {
                // Clear state
"""
content = content.replace(new_thread_old.strip(), new_thread_new.strip())


with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Modifications complete.")
