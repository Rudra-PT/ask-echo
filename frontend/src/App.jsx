import { useState } from 'react';
import { UploadPanel } from './components/UploadPanel.jsx';
import { ChatWindow } from './components/ChatWindow.jsx';
import { EchoEchoLogo } from './components/EchoEchoLogo.jsx';
import { queryDocuments, clearSession } from './api.js';

export default function App() {
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [clearing, setClearing]   = useState(false);
  const [uploadKey, setUploadKey] = useState(0); // bump to reset UploadPanel

  // ── Upload success ────────────────────────────────────────────────────────
  function handleUploadSuccess(result) {
    setMessages((prev) => [
      ...prev,
      {
        id:      `sys-${Date.now()}`,
        role:    'assistant',
        content: `✓ **${result.file_name}** indexed — ${result.chunks_indexed} chunk${result.chunks_indexed !== 1 ? 's' : ''} ready to query.`,
        sources: [],
      },
    ]);
  }

  // ── Clear session ─────────────────────────────────────────────────────────
  async function handleClear() {
    if (clearing || loading) return;
    setClearing(true);
    try {
      await clearSession();
      setMessages([]);           // wipe chat history
      setInput('');
      setUploadKey((k) => k + 1); // remount UploadPanel → resets its state
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id:      `err-${Date.now()}`,
          role:    'assistant',
          content: `⚠ Could not clear session: ${err.message}`,
          sources: [],
        },
      ]);
    } finally {
      setClearing(false);
    }
  }

  // ── Send query ────────────────────────────────────────────────────────────
  async function handleSend(e) {
    if (e) e.preventDefault();
    if (!input.trim() || loading) return;

    const text = input.trim();
    setInput('');

    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content: text, sources: [] },
    ]);
    setLoading(true);

    try {
      const res = await queryDocuments(text);
      setMessages((prev) => [
        ...prev,
        {
          id:      `ai-${Date.now()}`,
          role:    'assistant',
          content: res.answer,
          sources: res.sources || [],
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id:      `error-${Date.now()}`,
          role:    'assistant',
          content: `⚠ ${err.message || 'Failed to retrieve grounded answer.'}`,
          sources: [],
        },
      ]);
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

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
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

          {/* Upload panel — key forces remount on clear */}
          <UploadPanel key={uploadKey} onUploadSuccess={handleUploadSuccess} />

          {/* ── Clear Knowledge Base button ── */}
          <button
            className="clear-kb-btn"
            onClick={handleClear}
            disabled={clearing || loading}
            aria-busy={clearing}
            title="Delete all indexed vectors and reset the chat"
          >
            {clearing ? (
              <><span className="spinner dark" aria-hidden="true" /> Clearing…</>
            ) : (
              <>🗑 Clear Knowledge Base</>
            )}
          </button>
        </div>
      </aside>

      {/* ── Chat main ── */}
      <main className="chat-main">
        <header className="chat-header">
          <div>
            <h2 className="chat-header-title">Echo Chamber</h2>
            <p className="chat-header-subtitle">
              Just Ask Me From The PDF You Uploaded Cause I&apos;m Not That Intelligent
            </p>
          </div>
          <div className="chat-status-dot" title="Active Connection" />
        </header>

        <ChatWindow messages={messages} isLoading={loading} />

        <footer className="chat-input-area">
          <form className="chat-input-form" onSubmit={handleSend}>
            <div className="chat-textarea-wrapper">
              <textarea
                className="chat-textarea"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask something about the uploaded documents…"
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
