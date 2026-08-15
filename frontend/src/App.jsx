import { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { UploadPanel } from './components/UploadPanel.jsx';
import { ChatWindow } from './components/ChatWindow.jsx';
import { EchoEchoLogo } from './components/EchoEchoLogo.jsx';
import {
  setAuthToken,
  clearAuthToken,
  queryDocuments,
  clearSession,
} from './api.js';

export default function App() {
  // ── Auth state ──────────────────────────────────────────────────────────
  const [user, setUser]           = useState(null);  // { name, email, picture, sub }
  const [authReady, setAuthReady] = useState(false);

  // ── Chat state ──────────────────────────────────────────────────────────
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [clearing, setClearing]   = useState(false);
  const [uploadKey, setUploadKey] = useState(0);

  // ── Sign out ────────────────────────────────────────────────────────────
  function handleSignOut() {
    clearAuthToken();
    setUser(null);
    setAuthReady(false);
    setMessages([]);
    setInput('');
    setUploadKey((k) => k + 1);
  }

  // ── Upload success ──────────────────────────────────────────────────────
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

  // ── Clear session ───────────────────────────────────────────────────────
  async function handleClear() {
    if (clearing || loading) return;
    setClearing(true);
    try {
      await clearSession();
      setMessages([]);
      setInput('');
      setUploadKey((k) => k + 1);
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

  // ── Send query ──────────────────────────────────────────────────────────
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

  // ── Login gate ──────────────────────────────────────────────────────────
  if (!authReady) {
    return (
      <div className="login-screen min-h-screen w-screen flex items-center justify-center bg-[#FAF8F5]">
        <div className="login-card flex flex-col items-center gap-4 p-8 bg-white border border-stone-200 rounded-2xl shadow-lg shadow-stone-200/50 max-w-md w-[90%] text-center">
          <div className="login-logo mb-1">
            <EchoEchoLogo size={48} />
          </div>
          <h1 className="login-title font-sans text-2xl font-bold tracking-wider text-stone-800 m-0">ask-echo</h1>
          <p className="login-subtitle text-sm font-semibold text-amber-600 tracking-wide m-0">Your private, document-grounded AI assistant.</p>
          <p className="login-desc text-xs text-stone-500 leading-relaxed max-w-xs m-0">
            Sign in to upload PDFs and ask questions. Your documents are stored privately — no one else can access them.
          </p>
          <div className="google-signin-wrapper mt-2 flex items-center justify-center">
            <GoogleLogin
              onSuccess={(credentialResponse) => {
                const idToken = credentialResponse.credential;
                if (!idToken) {
                  console.error('No ID token credential received from Google');
                  return;
                }

                // Store raw JWT ID Token for all backend API calls
                setAuthToken(idToken);

                // Decode user claims from the ID Token
                try {
                  const base64Url = idToken.split('.')[1];
                  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                  const jsonPayload = decodeURIComponent(
                    atob(base64)
                      .split('')
                      .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                      .join('')
                  );
                  const profile = JSON.parse(jsonPayload);

                  setUser({
                    name:    profile.name    ?? profile.email ?? 'User',
                    email:   profile.email   ?? '',
                    picture: profile.picture ?? '',
                    sub:     profile.sub     ?? '',
                  });
                } catch (err) {
                  console.error('Failed to decode user profile from ID token:', err);
                  setUser({ name: 'User', email: '', picture: '', sub: '' });
                }

                setAuthReady(true);
              }}
              onError={() => {
                console.error('Google Sign-In failed');
              }}
              shape="pill"
              theme="outline"
              size="large"
              text="signin_with"
            />
          </div>
        </div>
      </div>
    );
  }

  // ── Authenticated app shell ─────────────────────────────────────────────
  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="app-logo">
            <EchoEchoLogo size={32} />
            <h1 className="app-logo-name">ask-echo</h1>
          </div>
          <p className="app-tagline">Your Private PDF Analyzer</p>
        </div>

        {/* User profile strip */}
        {user && (
          <div className="user-strip">
            {user.picture ? (
              <img
                className="user-avatar"
                src={user.picture}
                alt={user.name}
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="user-avatar user-avatar-fallback">
                {user.name?.[0]?.toUpperCase() ?? '?'}
              </div>
            )}
            <div className="user-info">
              <span className="user-name">{user.name}</span>
              <span className="user-email">{user.email}</span>
            </div>
            <button
              className="signout-btn"
              onClick={handleSignOut}
              title="Sign out"
              aria-label="Sign out"
            >
              ↩
            </button>
          </div>
        )}

        <div className="sidebar-body">
          <h2 className="sidebar-section-title">Knowledge Base</h2>

          <UploadPanel key={uploadKey} onUploadSuccess={handleUploadSuccess} />

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
                placeholder="Ask something about your uploaded documents…"
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
            Answers are generated strictly using your private documents.
          </p>
        </footer>
      </main>
    </div>
  );
}
