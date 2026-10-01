/**
 * BankEase Chat Widget — streaming SSE-powered Claude Haiku assistant.
 *
 * Architecture:
 *   - Reads engine data from #engine-data JSON block (already on dashboard)
 *   - Sends user message + trimmed history + financials to /chat/stream
 *   - Consumes SSE token stream for instant first-token rendering
 *   - Stores chat history in sessionStorage (survives page navigations)
 *
 * Design: floating bottom-right pill button that expands into a chat panel.
 */

(function () {
    'use strict';

    // ── Config ──────────────────────────────────────────────────────────────
    const MAX_HISTORY_MESSAGES = 12; // 6 turn-pairs
    const STORAGE_KEY = 'bankease_chat_history';

    // ── State ──────────────────────────────────────────────────────────────
    let chatHistory = [];
    let isStreaming = false;
    let isOpen = false;

    // ── Helpers ─────────────────────────────────────────────────────────────
    function getEngineData() {
        const el = document.getElementById('engine-data');
        if (!el) return {};
        try { return JSON.parse(el.textContent); } catch { return {}; }
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        const field = document.querySelector('input[name="csrf_token"]');
        if (field) return field.value;
        return '';
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function loadHistory() {
        try {
            const raw = sessionStorage.getItem(STORAGE_KEY);
            chatHistory = raw ? JSON.parse(raw) : [];
        } catch { chatHistory = []; }
    }

    function saveHistory() {
        try {
            // Trim to max
            if (chatHistory.length > MAX_HISTORY_MESSAGES) {
                chatHistory = chatHistory.slice(-MAX_HISTORY_MESSAGES);
            }
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
        } catch { /* quota exceeded — silently drop */ }
    }

    // ── Simple markdown-ish formatting for chat ────────────────────────────
    function formatMessage(text) {
        return text
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`(.+?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    // ── Build DOM ───────────────────────────────────────────────────────────
    function injectStyles() {
        if (document.getElementById('chat-widget-styles')) return;
        const style = document.createElement('style');
        style.id = 'chat-widget-styles';
        style.textContent = `
            /* ── Chat FAB ─────────────────────────────────────────────── */
            #chat-fab {
                position: fixed; bottom: 24px; right: 24px; z-index: 9999;
                width: 56px; height: 56px; border-radius: 50%;
                background: linear-gradient(135deg, #1a56db, #7c3aed);
                color: #fff; border: none; cursor: pointer;
                box-shadow: 0 4px 20px rgba(26,86,219,0.4);
                display: flex; align-items: center; justify-content: center;
                font-size: 1.5rem;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            #chat-fab:hover {
                transform: scale(1.08);
                box-shadow: 0 6px 28px rgba(26,86,219,0.55);
            }
            #chat-fab.open { display: none; }

            /* ── Chat Panel ───────────────────────────────────────────── */
            #chat-panel {
                position: fixed; bottom: 24px; right: 24px; z-index: 9999;
                width: 380px; max-width: calc(100vw - 32px);
                height: 520px; max-height: calc(100vh - 80px);
                background: #fff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                box-shadow: 0 12px 48px rgba(0,0,0,0.15);
                display: none; flex-direction: column;
                overflow: hidden;
                animation: chatSlideUp 0.25s ease-out;
            }
            #chat-panel.open { display: flex; }
            @keyframes chatSlideUp {
                from { opacity: 0; transform: translateY(16px); }
                to   { opacity: 1; transform: translateY(0); }
            }

            /* Header */
            .chat-header {
                display: flex; align-items: center; justify-content: space-between;
                padding: 14px 16px;
                background: linear-gradient(135deg, #1a56db, #7c3aed);
                color: #fff;
                flex-shrink: 0;
            }
            .chat-header-title {
                font-weight: 700; font-size: 0.95rem;
                display: flex; align-items: center; gap: 8px;
            }
            .chat-header-title .model-badge {
                font-size: 0.65rem; background: rgba(255,255,255,0.2);
                padding: 2px 8px; border-radius: 99px; font-weight: 500;
            }
            .chat-close {
                background: none; border: none; color: #fff;
                font-size: 1.3rem; cursor: pointer; padding: 0 4px;
                opacity: 0.8; transition: opacity 0.15s;
            }
            .chat-close:hover { opacity: 1; }

            /* Messages area */
            .chat-messages {
                flex: 1; overflow-y: auto; padding: 16px;
                display: flex; flex-direction: column; gap: 12px;
                scroll-behavior: smooth;
            }
            .chat-messages::-webkit-scrollbar { width: 5px; }
            .chat-messages::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 4px; }

            /* Message bubbles */
            .chat-msg {
                max-width: 85%; padding: 10px 14px;
                border-radius: 14px; font-size: 0.88rem;
                line-height: 1.55; word-wrap: break-word;
            }
            .chat-msg.user {
                align-self: flex-end;
                background: linear-gradient(135deg, #1a56db, #2563eb);
                color: #fff; border-bottom-right-radius: 4px;
            }
            .chat-msg.assistant {
                align-self: flex-start;
                background: #f3f4f6; color: #111827;
                border-bottom-left-radius: 4px;
            }
            .chat-msg.assistant code {
                background: #e5e7eb; padding: 1px 4px; border-radius: 3px;
                font-size: 0.82em;
            }
            .chat-msg.system {
                align-self: center;
                background: #fef9c3; color: #713f12;
                font-size: 0.8rem; padding: 6px 12px;
                border-radius: 10px;
            }

            /* Typing indicator */
            .chat-typing {
                display: flex; gap: 4px; padding: 8px 14px;
                align-self: flex-start;
            }
            .chat-typing span {
                width: 7px; height: 7px; border-radius: 50%;
                background: #9ca3af;
                animation: typingBounce 1.2s infinite;
            }
            .chat-typing span:nth-child(2) { animation-delay: 0.15s; }
            .chat-typing span:nth-child(3) { animation-delay: 0.3s; }
            @keyframes typingBounce {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-6px); }
            }

            /* Input area */
            .chat-input-area {
                display: flex; align-items: center; gap: 8px;
                padding: 12px 14px;
                border-top: 1px solid #e5e7eb;
                background: #fafafa;
                flex-shrink: 0;
            }
            .chat-input {
                flex: 1; border: 1px solid #d1d5db; border-radius: 10px;
                padding: 9px 14px; font-size: 0.88rem;
                outline: none; resize: none;
                font-family: inherit; line-height: 1.4;
                max-height: 80px; min-height: 38px;
                transition: border-color 0.15s;
            }
            .chat-input:focus { border-color: #1a56db; }
            .chat-input:disabled { background: #f3f4f6; color: #9ca3af; }
            .chat-send {
                width: 38px; height: 38px; border-radius: 50%;
                background: linear-gradient(135deg, #1a56db, #7c3aed);
                color: #fff; border: none; cursor: pointer;
                display: flex; align-items: center; justify-content: center;
                font-size: 1rem;
                transition: opacity 0.15s, transform 0.15s;
                flex-shrink: 0;
            }
            .chat-send:hover { transform: scale(1.05); }
            .chat-send:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

            /* Quick suggestions */
            .chat-suggestions {
                display: flex; flex-wrap: wrap; gap: 6px;
                padding: 0 16px 10px;
            }
            .chat-suggestion {
                font-size: 0.78rem; padding: 5px 12px;
                background: #eff6ff; color: #1a56db;
                border: 1px solid #bfdbfe; border-radius: 99px;
                cursor: pointer; transition: all 0.15s;
                white-space: nowrap;
            }
            .chat-suggestion:hover {
                background: #1a56db; color: #fff; border-color: #1a56db;
            }

            /* Mobile responsive */
            @media (max-width: 480px) {
                #chat-panel {
                    width: calc(100vw - 16px); height: calc(100vh - 80px);
                    bottom: 8px; right: 8px;
                    border-radius: 12px;
                }
            }
        `;
        document.head.appendChild(style);
    }

    function createWidget() {
        injectStyles();

        // FAB button
        const fab = document.createElement('button');
        fab.id = 'chat-fab';
        fab.innerHTML = '💬';
        fab.title = 'Ask BankEase AI';
        fab.setAttribute('aria-label', 'Open chat assistant');
        fab.onclick = () => toggleChat(true);

        // Panel
        const panel = document.createElement('div');
        panel.id = 'chat-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'BankEase AI Chat');
        panel.innerHTML = `
            <div class="chat-header">
                <div class="chat-header-title">
                    🤖 BankEase AI
                    <span class="model-badge">Claude Haiku</span>
                </div>
                <button class="chat-close" aria-label="Close chat" title="Close">&times;</button>
            </div>
            <div class="chat-messages" id="chat-messages"></div>
            <div class="chat-suggestions" id="chat-suggestions"></div>
            <div class="chat-input-area">
                <textarea class="chat-input" id="chat-input"
                    placeholder="Ask about your finances…"
                    rows="1" aria-label="Chat message"></textarea>
                <button class="chat-send" id="chat-send" aria-label="Send message" title="Send">
                    ➤
                </button>
            </div>
        `;

        document.body.appendChild(fab);
        document.body.appendChild(panel);

        // Event bindings
        panel.querySelector('.chat-close').onclick = () => toggleChat(false);

        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('chat-send');

        sendBtn.onclick = () => sendMessage();

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Auto-resize textarea
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 80) + 'px';
        });

        // Load history and render
        loadHistory();
        renderHistory();
        showSuggestions();
    }

    function toggleChat(open) {
        isOpen = open;
        const fab = document.getElementById('chat-fab');
        const panel = document.getElementById('chat-panel');
        if (open) {
            fab.classList.add('open');
            panel.classList.add('open');
            document.getElementById('chat-input').focus();
            scrollToBottom();
        } else {
            fab.classList.remove('open');
            panel.classList.remove('open');
        }
    }

    // ── Rendering ───────────────────────────────────────────────────────────
    function renderHistory() {
        const container = document.getElementById('chat-messages');
        if (!container) return;
        container.innerHTML = '';

        if (chatHistory.length === 0) {
            addSystemMessage("Hi! I'm your BankEase AI assistant. Ask me anything about your financial plan, investments, or market data. 👋");
        }

        for (const msg of chatHistory) {
            appendBubble(msg.role, msg.content, false);
        }
        scrollToBottom();
    }

    function appendBubble(role, content, animate) {
        const container = document.getElementById('chat-messages');
        if (!container) return null;

        const bubble = document.createElement('div');
        bubble.className = `chat-msg ${role}`;

        if (role === 'assistant') {
            bubble.innerHTML = formatMessage(content);
        } else if (role === 'system') {
            bubble.innerHTML = content;
        } else {
            bubble.textContent = content;
        }

        if (animate) {
            bubble.style.opacity = '0';
            bubble.style.transform = 'translateY(8px)';
            container.appendChild(bubble);
            requestAnimationFrame(() => {
                bubble.style.transition = 'opacity 0.2s, transform 0.2s';
                bubble.style.opacity = '1';
                bubble.style.transform = 'translateY(0)';
            });
        } else {
            container.appendChild(bubble);
        }

        scrollToBottom();
        return bubble;
    }

    function addSystemMessage(text) {
        appendBubble('system', text, false);
    }

    function showTypingIndicator() {
        const container = document.getElementById('chat-messages');
        const typing = document.createElement('div');
        typing.className = 'chat-typing';
        typing.id = 'typing-indicator';
        typing.innerHTML = '<span></span><span></span><span></span>';
        container.appendChild(typing);
        scrollToBottom();
    }

    function removeTypingIndicator() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    function scrollToBottom() {
        const container = document.getElementById('chat-messages');
        if (container) {
            requestAnimationFrame(() => {
                container.scrollTop = container.scrollHeight;
            });
        }
    }

    function showSuggestions() {
        const container = document.getElementById('chat-suggestions');
        if (!container || chatHistory.length > 0) {
            if (container) container.style.display = 'none';
            return;
        }

        const suggestions = [
            "How should I invest my surplus?",
            "Explain my tax savings",
            "Is my emergency fund enough?",
            "How's the market today?",
        ];

        container.innerHTML = suggestions.map(s =>
            `<button class="chat-suggestion">${s}</button>`
        ).join('');

        container.querySelectorAll('.chat-suggestion').forEach(btn => {
            btn.onclick = () => {
                document.getElementById('chat-input').value = btn.textContent;
                sendMessage();
                container.style.display = 'none';
            };
        });
    }

    function setInputEnabled(enabled) {
        const input = document.getElementById('chat-input');
        const btn = document.getElementById('chat-send');
        if (input) input.disabled = !enabled;
        if (btn) btn.disabled = !enabled;
    }

    // ── Send + Stream ───────────────────────────────────────────────────────
    async function sendMessage() {
        const input = document.getElementById('chat-input');
        const message = (input.value || '').trim();
        if (!message || isStreaming) return;

        // Hide suggestions
        const suggestions = document.getElementById('chat-suggestions');
        if (suggestions) suggestions.style.display = 'none';

        // Add user bubble
        chatHistory.push({ role: 'user', content: message });
        appendBubble('user', message, true);
        input.value = '';
        input.style.height = 'auto';

        isStreaming = true;
        setInputEnabled(false);
        showTypingIndicator();

        const engineData = getEngineData();

        try {
            const response = await fetch('/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    message: message,
                    history: chatHistory.slice(0, -1), // exclude the message we just pushed
                    financials: engineData,
                    tickers: engineData._tickers || ["RELIANCE.NS", "TCS.NS", "INFY.NS"],
                }),
            });

            removeTypingIndicator();

            if (!response.ok) {
                const err = await response.json().catch(() => ({ error: 'Request failed' }));
                appendBubble('system', `⚠️ ${err.error || 'Something went wrong.'}`, true);
                isStreaming = false;
                setInputEnabled(true);
                return;
            }

            // Create assistant bubble and stream into it
            const bubble = appendBubble('assistant', '', true);
            let fullResponse = '';

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Parse SSE events
                const lines = buffer.split('\n');
                buffer = lines.pop(); // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const payload = line.slice(6).trim();
                    if (!payload) continue;

                    try {
                        const evt = JSON.parse(payload);
                        if (evt.token) {
                            fullResponse += evt.token;
                            bubble.innerHTML = formatMessage(fullResponse);
                            scrollToBottom();
                        }
                        if (evt.done) {
                            // Stream complete
                        }
                        if (evt.error) {
                            fullResponse += `\n⚠️ ${evt.error}`;
                            bubble.innerHTML = formatMessage(fullResponse);
                        }
                    } catch { /* skip malformed events */ }
                }
            }

            // Save to history
            if (fullResponse) {
                chatHistory.push({ role: 'assistant', content: fullResponse });
                saveHistory();
            }

        } catch (err) {
            removeTypingIndicator();
            appendBubble('system', '⚠️ Connection error. Check your network and try again.', true);
            console.error('Chat stream error:', err);
        }

        isStreaming = false;
        setInputEnabled(true);
        document.getElementById('chat-input').focus();
    }

    // ── Init ────────────────────────────────────────────────────────────────
    // Pre-flight: check /chat/health to see if API key is configured.
    // If not, don't render the FAB at all — clear "chat unavailable" state.
    async function init() {
        try {
            const resp = await fetch('/chat/health');
            const data = await resp.json();
            if (data.status === 'no_api_key') {
                console.info('BankEase Chat: ANTHROPIC_API_KEY not configured — chat widget hidden.');
                return; // FAB never appears
            }
        } catch {
            // Health endpoint unreachable — still show FAB, it'll show
            // a graceful error on first message attempt
        }
        createWidget();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
