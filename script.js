
document.addEventListener('DOMContentLoaded', () => {

    // State management
    let chatHistory = [];
    let isFileAttached = false;
    let currentFileName = "";
    
    // Multi-thread management
    let currentThreadId = Date.now().toString();
    const MAX_THREADS = 6;


    // DOM Elements
    const searchInput = document.querySelector('.search-input');
    const submitBtn = document.querySelector('.submit-btn');
    const chatMessages = document.getElementById('chat-messages');
    const loadingContainer = document.getElementById('loading-container');
    const newThreadBtn = document.querySelector('.new-thread');
    
    // File Upload Elements
    const fileUpload = document.getElementById('file-upload');
    const attachBtn = document.getElementById('attach-btn');
    const fileChip = document.getElementById('file-chip');
    const fileNameSpan = document.getElementById('file-name');
    const removeFileBtn = document.getElementById('remove-file');

    let isSearching = false;

    function scrollToBottom() {
        const mainContent = document.querySelector('.main-content');
        if (mainContent) {
            mainContent.scrollTo({ top: mainContent.scrollHeight, behavior: 'smooth' });
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });

        searchInput.focus();

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!isSearching) {
                    handleSearch();
                }
            }
        });
    }

    // Base API URL that works across ports (e.g. Live Server on 5500 vs Flask on 5000)
    const API_BASE = (window.location.protocol === 'file:' || (window.location.port && window.location.port !== '5000')) 
        ? 'http://localhost:5000' 
        : '';

    // File Upload Logic
    if (attachBtn && fileUpload) {
        attachBtn.addEventListener('click', () => {
            fileUpload.click();
        });

        fileUpload.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const allowedExts = ['.pdf', '.txt', '.docx', '.md', '.csv', '.json'];
            const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
            if (!allowedExts.includes(fileExt)) {
                alert('Please upload a supported document (.pdf, .txt, .docx, .md, .csv).');
                return;
            }

            const formData = new FormData();
            formData.append('file', file);
            formData.append('thread_id', currentThreadId);

            try {
                loadingContainer.classList.remove('hidden');
                const response = await fetch(`${API_BASE}/api/upload`, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json().catch(() => null);
                loadingContainer.classList.add('hidden');

                if (response.ok && data) {
                    isFileAttached = true;
                    currentFileName = file.name;
                    fileNameSpan.textContent = currentFileName;
                    fileChip.classList.remove('hidden');
                } else {
                    alert((data && data.error) ? data.error : 'Upload failed');
                }
            } catch (error) {
                console.error('Upload error:', error);
                loadingContainer.classList.add('hidden');
                alert('Failed to upload file. Please make sure the server is running at http://localhost:5000');
            }
        });
    }

    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', async () => {
            try {
                await fetch(`${API_BASE}/api/clear`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ thread_id: currentThreadId })
                });
                isFileAttached = false;
                currentFileName = "";
                fileChip.classList.add('hidden');
                fileUpload.value = '';
            } catch (error) {
                console.error('Clear error:', error);
            }
        });
    }


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
                fetch(`${API_BASE}/api/clear`, { 
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
            scrollToBottom();
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
        
        fetch(`${API_BASE}/api/clear`, { 
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
        const messageBlock = document.createElement('div');
        messageBlock.className = 'message-block';
        
        let attachmentHtml = "";
        if (fileName) {
            attachmentHtml = `<div class="message-attachment"><i class="ph ph-file-pdf"></i> ${escapeHtml(fileName)}</div>`;
        }
        
        messageBlock.innerHTML = `<div class="user-message">${escapeHtml(text)}${attachmentHtml}</div>`;
        chatMessages.appendChild(messageBlock);
        scrollToBottom();
    }

    function appendAiMessage(text, sources = []) {
        const messageBlock = document.createElement('div');
        messageBlock.className = 'message-block';
        
        let sourcesHtml = "";
        if (sources && sources.length > 0) {
            sourcesHtml = `
                <div class="sources-section">
                    <div class="sources-title"><i class="ph ph-globe"></i> Sources</div>
                    <div class="sources-row">
                        ${sources.map((s, idx) => {
                            let domain = s.domain || 'web';
                            let homePage = s.home_page || s.url || '#';
                            if (!domain || domain === 'web') {
                                try { domain = new URL(s.url).hostname.replace('www.', ''); } catch (e) { domain = 'source'; }
                            }
                            const faviconUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=32`;
                            return `
                                <div class="source-pill" title="${escapeHtml(s.title || domain)}">
                                    <span class="source-pill-idx">${idx + 1}</span>
                                    <img src="${faviconUrl}" class="source-pill-icon" alt="" onerror="this.style.display='none'">
                                    <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" class="source-pill-link" title="Read: ${escapeHtml(s.title || domain)}">
                                        <span class="source-pill-domain">${escapeHtml(domain)}</span>
                                    </a>
                                    <a href="${escapeHtml(homePage)}" target="_blank" rel="noopener noreferrer" class="source-pill-home" title="Visit ${escapeHtml(domain)} homepage">
                                        <i class="ph ph-arrow-square-out"></i>
                                    </a>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        // Format inline citations [1], [2] as clickable tags
        let rawText = text || "";
        if (sources && sources.length > 0) {
            rawText = rawText.replace(/\[(\d+)\]/g, (match, num) => {
                const sIdx = parseInt(num) - 1;
                if (sources[sIdx]) {
                    const src = sources[sIdx];
                    return `<a href="${src.url}" target="_blank" rel="noopener noreferrer" class="citation-tag" title="${escapeHtml(src.title || src.domain || 'Source')}">${num}</a>`;
                }
                return match;
            });
        }

        // Parse markdown text to HTML format
        const parsedContent = marked.parse(rawText);
        
        messageBlock.innerHTML = `
            <div class="ai-message">
                ${sourcesHtml}
                <div class="result-header">
                    <i class="ph ph-sparkle"></i> Answer
                </div>
                <div class="result-content">${parsedContent}</div>
                <div class="result-actions">
                    <button class="action-btn copy-btn" title="Copy answer">
                        <i class="ph ph-copy"></i> <span>Copy</span>
                    </button>
                    <button class="action-btn speak-btn" title="Listen to answer">
                        <i class="ph ph-speaker-high"></i> <span>Listen</span>
                    </button>
                </div>
            </div>
        `;

        // Wire up copy button
        const copyBtn = messageBlock.querySelector('.copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(text || '').then(() => {
                    copyBtn.innerHTML = `<i class="ph ph-check" style="color:#22c55e;"></i> <span>Copied!</span>`;
                    setTimeout(() => {
                        copyBtn.innerHTML = `<i class="ph ph-copy"></i> <span>Copy</span>`;
                    }, 2000);
                }).catch(() => {});
            });
        }

        // Wire up read aloud button
        const speakBtn = messageBlock.querySelector('.speak-btn');
        if (speakBtn && 'speechSynthesis' in window) {
            let isSpeaking = false;
            speakBtn.addEventListener('click', () => {
                if (isSpeaking) {
                    window.speechSynthesis.cancel();
                    isSpeaking = false;
                    speakBtn.innerHTML = `<i class="ph ph-speaker-high"></i> <span>Listen</span>`;
                } else {
                    window.speechSynthesis.cancel();
                    const cleanSpeechText = (text || '').replace(/[#*`_\[\]]/g, ' ');
                    const utterance = new SpeechSynthesisUtterance(cleanSpeechText);
                    utterance.onend = () => {
                        isSpeaking = false;
                        speakBtn.innerHTML = `<i class="ph ph-speaker-high"></i> <span>Listen</span>`;
                    };
                    window.speechSynthesis.speak(utterance);
                    isSpeaking = true;
                    speakBtn.innerHTML = `<i class="ph ph-stop"></i> <span>Stop</span>`;
                }
            });
        }

        chatMessages.appendChild(messageBlock);
        scrollToBottom();
    }

    async function handleSearch() {
        if (!searchInput || isSearching) return;
        const query = searchInput.value.trim();
        if (!query) return;

        isSearching = true;
        if (submitBtn) submitBtn.disabled = true;
        searchInput.disabled = true;

        // Hide suggestions section once conversation starts
        const tryComputerSection = document.querySelector('.try-computer-section');
        if (tryComputerSection) {
            tryComputerSection.classList.add('hidden');
        }

        // 1. Capture current attachment for this message
        const fileNameToDisplay = isFileAttached ? currentFileName : "";

        // 2. Append User Message with attachment
        appendUserMessage(query, fileNameToDisplay);
        
        // 3. Clear file chip from search input area and reset attachment state
        fileChip.classList.add('hidden');
        isFileAttached = false;
        currentFileName = "";
        if (fileUpload) fileUpload.value = '';
        
        loadingContainer.classList.remove('hidden');
        scrollToBottom();
        searchInput.value = '';
        searchInput.style.height = 'auto';

        try {
            const response = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    prompt: query,
                    history: chatHistory,
                    thread_id: currentThreadId
                }),
            });

            const data = await response.json().catch(() => null);
            loadingContainer.classList.add('hidden');

            if (data && data.response) {
                appendAiMessage(data.response, data.sources || []);
                
                // Set title to first query if new
                let threads = loadThreads();
                let isNew = !threads.find(t => t.id === currentThreadId);
                let title = isNew ? (query.length > 25 ? query.slice(0, 25) + '...' : query) : null;

                chatHistory.push({ role: 'user', parts: [{ text: query }] });
                chatHistory.push({ role: 'model', parts: [{ text: data.response }] });
                
                saveCurrentThread(title);
            } else {
                const errMsg = (data && data.error) ? data.error : 'Failed to get response from server. Make sure server is running on http://localhost:5000';
                throw new Error(errMsg);
            }
        } catch (error) {
            console.error('Search error:', error);
            loadingContainer.classList.add('hidden');
            
            let userMessage = "Error: " + error.message;
            if (error.message.includes("429") || error.message.toLowerCase().includes("quota")) {
                userMessage = "⚠️ Rate limit reached (429). The model is currently busy or out of daily credits. Please try again in 1 minute.";
            } else if (error.message.includes("503") || error.message.toLowerCase().includes("unavailable")) {
                userMessage = "⚠️ Server Overloaded (503). Gemini is currently experiencing high demand. Please wait a moment and try again.";
            }
            
            appendAiMessage(userMessage);
        } finally {
            isSearching = false;
            searchInput.disabled = false;
            if (submitBtn) submitBtn.disabled = false;
            searchInput.focus();
        }
    }

    if (submitBtn) {
        submitBtn.addEventListener('click', () => {
            if (!isSearching) handleSearch();
        });
    }

    if (newThreadBtn) {
        newThreadBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            startNewThread();
            try {
                // Clear state
                isFileAttached = false;
                currentFileName = "";
                fileChip.classList.add('hidden');
                fileUpload.value = '';
            } catch (error) {}
            searchInput.focus();
        });
    }

    const suggestionItems = document.querySelectorAll('.suggestion-item');
    suggestionItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            searchInput.value = item.textContent;
            searchInput.style.height = (searchInput.scrollHeight) + 'px';
            handleSearch();
        });
    });

    // Try Computer Tab Switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tryComputerSection = document.querySelector('.try-computer-section');
    
    if (tabBtns.length > 0) {
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // For demonstration: change the suggestions list based on tab
                const list = document.querySelector('.suggestions-list');
                const tabText = btn.textContent.toLowerCase();
                
                if (tabText.includes('business')) {
                    list.innerHTML = `
                        <a href="#" class="suggestion-item">Draft a partnership proposal for a target company</a>
                        <a href="#" class="suggestion-item">Build a financial model for my startup</a>
                        <a href="#" class="suggestion-item">Size the market for my business idea</a>
                        <a href="#" class="suggestion-item">Research my top competitors and break down their strategy</a>
                    `;
                } else if (tabText.includes('organise')) {
                    list.innerHTML = `
                        <a href="#" class="suggestion-item">Plan a 3-day itinerary for Tokyo</a>
                        <a href="#" class="suggestion-item">Create a weekly meal plan for a family of four</a>
                        <a href="#" class="suggestion-item">Set up a budget tracking system</a>
                        <a href="#" class="suggestion-item">Schedule a series of focus work sessions</a>
                    `;
                } else if (tabText.includes('monitor')) {
                    list.innerHTML = `
                        <a href="#" class="suggestion-item">Track the latest developments in AI regulation</a>
                        <a href="#" class="suggestion-item">Monitor tech industry news for today</a>
                        <a href="#" class="suggestion-item">Follow stock market trends for semiconductor companies</a>
                        <a href="#" class="suggestion-item">Summarise the top stories from Hacker News</a>
                    `;
                } else {
                    list.innerHTML = `
                        <a href="#" class="suggestion-item">Write a Python script for web scraping</a>
                        <a href="#" class="suggestion-item">Refactor a React component for better performance</a>
                        <a href="#" class="suggestion-item">Create a CI/CD pipeline using GitHub Actions</a>
                        <a href="#" class="suggestion-item">Debug a memory leak in a Node.js application</a>
                    `;
                }
                
                // Re-bind click events to new suggestion items
                const newSuggestionItems = list.querySelectorAll('.suggestion-item');
                newSuggestionItems.forEach(item => {
                    item.addEventListener('click', (e) => {
                        e.preventDefault();
                        searchInput.value = item.textContent;
                        searchInput.style.height = (searchInput.scrollHeight) + 'px';
                        handleSearch();
                    });
                });
            });
        });
    }

    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            if(!item.classList.contains('new-thread')) {
                navItems.forEach(n => n.classList.remove('active'));
                item.classList.add('active');
            }
        });
    });
});
