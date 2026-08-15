import { useState } from 'react';
import { useGoogleLogin } from '@react-oauth/google';
import { UploadPanel } from './components/UploadPanel.jsx';
import { ChatWindow } from './components/ChatWindow.jsx';
import { EchoEchoLogo } from './components/EchoEchoLogo.jsx';
import {
  setAuthToken,
  clearAuthToken,
  isAuthenticated,
  queryDocuments,
  clearSession,
} from './api.js';

export default function App() {
  // ── Auth state ──────────────────────────────────────────────────────────
  const [user, setUser]           = useState(null);  // { name, email, picture }
  const [authReady, setAuthReady] = useState(false);

  // ── Chat state ──────────────────────────────────────────────────────────
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [clearing, setClearing]   = useState(false);
  const [uploadKey, setUploadKey] = useState(0);

  // ── Google login ────────────────────────────────────────────────────────
  const googleLogin = useGoogleLogin({
    // We request the ID token (credential) via the code flow, but the
    // simplest path with @react-oauth/google is the implicit flow which
    // gives us an access_token — we then fetch the userinfo endpoint.
    // For sending to our backend we need the id_token, so we use
    // onSuccess with response_type: "id_token" via the credential prop.
    flow: 'implicit',
    onSuccess: async (tokenResponse) => {
      // tokenResponse.access_token is an OAuth2 access token.
      // We need the ID token (JWT) for our backend; fetch it from Google.
      try {
        // Fetch user profile using the access token
        const profileRes = await fetch(
          'https://www.googleapis.com/oauth2/v3/userinfo',
          { headers: { Authorization: `Bearer ${tokenResponse.access_token}` } }
        );
        const profile = await profileRes.json();

        // For backend verification we need the id_token.
        // @react-oauth/google implicit flow returns it in tokenResponse.id_token
        // when we include 'openid' scope (which is the default).
        const idToken = tokenResponse.id_token ?? tokenResponse.access_token;

        setAuthToken(idToken);
        setUser({
          name:    profile.name    ?? profile.email ?? 'User',
          email:   profile.email   ?? '',
          picture: profile.picture ?? '',
          sub:     profile.sub     ?? '',
        });
        setAuthReady(true);
      } catch (err) {
        console.error('Failed to fetch user profile:', err);
      }
    },
    onError: (err) => {
      console.error('Google login error:', err);
    },
    scope: 'openid email profile',
  });

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
      <div className="login-screen">
        <div className="login-card">
          <div className="login-logo">
            <EchoEchoLogo size={48} />
          </div>
          <h1 className="login-title">ask-echo</h1>
          <p className="login-subtitle">Your private, document-grounded AI assistant.</p>
          <p className="login-desc">
            Sign in to upload PDFs and ask questions. Your documents are stored privately — no one else can access them.
          </p>
          <button
            className="google-signin-btn"
            onClick={() => googleLogin()}
            id="google-signin-button"
            aria-label="Sign in with Google"
          >
            <GoogleIcon />
            <span>Sign in with Google</span>
          </button>
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

// ── Google coloured "G" icon ──────────────────────────────────────────────
function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  );
}
