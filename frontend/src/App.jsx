import { useState } from 'react';
import { UploadPanel } from './components/UploadPanel.jsx';
import { ChatWindow } from './components/ChatWindow.jsx';
import { EchoEchoLogo } from './components/EchoEchoLogo.jsx';
import { queryDocuments } from './api.js';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');


  function handleUploadSuccess(result) {

    const systemMessage = {
      id: `sys-${Date.now()}`,
      role: 'assistant',
      content: `System: Successfully processed and indexed "${result.filename}" (${result.chunks_extracted} chunks).`,
      sources: []
    };
    setMessages((prev) => [...prev, systemMessage]);
  }

  async function handleSend(e) {
    if (e) e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessageText = input.trim();
    setInput('');
    setErrorMsg('');

    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: userMessageText
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await queryDocuments(userMessageText, 'public', 5);

      const assistantMsg = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        sources: response.sources || []
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message || 'Failed to connect to the backend retrieval service.');

      const errorMsgObj = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err.message || 'Failed to retrieve grounded answer.'}`,
        sources: []
      };
      setMessages((prev) => [...prev, errorMsgObj]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="app-shell">
      { }
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="app-logo">
            <EchoEchoLogo size={32} />
            <h1 className="app-logo-name">ask-echo</h1>
          </div>
          <p className="app-tagline">Just Your PDF Analyzer</p>
        </div>

        <div className="sidebar-body">
          <h2 className="sidebar-section-title">Knowledge Base</h2>
          <UploadPanel onUploadSuccess={handleUploadSuccess} />
        </div>
      </aside>

      { }
      <main className="chat-main">
        <header className="chat-header">
          <div>
            <h2 className="chat-header-title">Echo Chamber</h2>
            <p className="chat-header-subtitle">Just Ask Me From The PDF You Uploaded Cause I'm Not That Intelligent</p>
          </div>
          <div className="chat-status-dot" title="Active Connection" />
        </header>

        { }
        <ChatWindow messages={messages} isLoading={loading} />

        { }
        <footer className="chat-input-area">
          <form className="chat-input-form" onSubmit={handleSend}>
            <div className="chat-textarea-wrapper">
              <textarea
                className="chat-textarea"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask something about the uploaded documents..."
                disabled={loading}
                rows={1}
              />
            </div>
            <button
              type="submit"
              className="send-btn"
              disabled={!input.trim() || loading}
              aria-label="Send query"
            >
              <span className="send-btn-icon">➔</span>
            </button>
          </form>
          <p className="chat-input-hint">
            Answers are generated strictly using your document.
          </p>
        </footer>
      </main>
    </div>
  );
}
