/**
 * MessageBubble.jsx
 * ─────────────────
 * Renders a single chat message with:
 *   • react-markdown for full markdown formatting (bold, lists, code, etc.)
 *   • Inline [Source: file.pdf, Page X] patterns replaced with styled amber pills
 *   • Source citation cards below the bubble (from Pinecone metadata)
 *   • TypingIndicator for the loading state
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { EchoEchoLogo } from './EchoEchoLogo.jsx';

// ── Citation pill ─────────────────────────────────────────────────────────────
const CITATION_RE = /\[Source:\s*([^,\]]+),\s*[Pp]age\s*(\d+)\]/g;

/**
 * Replace all [Source: X, Page N] patterns inside a text node with
 * <CitationPill> components, returning a mixed array of strings + elements.
 */
function parseCitations(text) {
  const parts = [];
  let lastIdx = 0;
  let match;

  CITATION_RE.lastIndex = 0; // reset stateful regex
  while ((match = CITATION_RE.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index));
    }
    parts.push(
      <CitationPill
        key={`${match[1]}-${match[2]}-${match.index}`}
        fileName={match[1].trim()}
        page={match[2]}
      />
    );
    lastIdx = CITATION_RE.lastIndex;
  }
  if (lastIdx < text.length) {
    parts.push(text.slice(lastIdx));
  }
  return parts;
}

/** A styled inline pill for a single citation reference. */
function CitationPill({ fileName, page }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 bg-amber-100 text-amber-900 border border-amber-200/80 px-2 py-0.5 rounded-md text-xs font-medium mx-1 align-baseline shadow-xs select-none"
      title={`${fileName}, Page ${page}`}
    >
      <span className="text-[11px]">📄</span>
      <span className="truncate max-w-[160px] font-medium">{fileName}</span>
      <span className="bg-amber-200/90 text-amber-950 px-1 rounded text-[11px] font-semibold">p.{page}</span>
    </span>
  );
}

// ── Custom react-markdown renderers ───────────────────────────────────────────
function markdownComponents() {
  return {
    p({ children }) {
      return <p className="my-2 leading-relaxed">{processChildren(children)}</p>;
    },
    li({ children }) {
      return <li className="my-1 leading-relaxed">{processChildren(children)}</li>;
    },
    strong({ children }) {
      return <strong className="font-semibold text-stone-900">{processChildren(children)}</strong>;
    },
    h1({ children }) {
      return <h1 className="text-xl font-bold text-stone-900 my-3">{processChildren(children)}</h1>;
    },
    h2({ children }) {
      return <h2 className="text-lg font-bold text-stone-900 my-2.5">{processChildren(children)}</h2>;
    },
    h3({ children }) {
      return <h3 className="text-base font-semibold text-stone-900 my-2">{processChildren(children)}</h3>;
    },
    a({ href, children }) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-amber-700 hover:text-amber-800 font-medium underline underline-offset-2"
        >
          {children}
        </a>
      );
    },
  };
}

/** Recursively process react-markdown children to inject citation pills. */
function processChildren(children) {
  return Array.isArray(children)
    ? children.flatMap((child, i) =>
        typeof child === 'string'
          ? parseCitations(child).map((part, j) =>
              typeof part === 'string' ? part : <span key={`${i}-${j}`}>{part}</span>
            )
          : child
      )
    : typeof children === 'string'
    ? parseCitations(children)
    : children;
}

// ── MessageBubble ─────────────────────────────────────────────────────────────
export function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      <div className={`avatar ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? '👤' : <EchoEchoLogo size={20} />}
      </div>

      <div className="bubble-group">
        <div className="bubble">
          {isUser ? (
            // User messages: plain text
            <span>{message.content}</span>
          ) : (
            // Assistant messages: full markdown + citation pills
            <div className="prose prose-stone max-w-none text-stone-800 leading-relaxed font-sans">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents()}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── TypingIndicator ───────────────────────────────────────────────────────────
export function TypingIndicator() {
  return (
    <div className="message-row assistant">
      <div className="avatar assistant">
        <EchoEchoLogo size={20} />
      </div>
      <div className="typing-bubble" role="status" aria-label="Ask-Echo is thinking">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}
