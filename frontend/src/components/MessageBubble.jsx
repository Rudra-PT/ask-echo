/**
 * MessageBubble.jsx
 * ─────────────────
 * Renders a single chat message with:
 *   • react-markdown for full markdown formatting (bold, lists, code, etc.)
 *   • Inline [Source: file.pdf, Page X] patterns replaced with styled pills
 *   • Source citation cards below the bubble (from Pinecone metadata)
 *   • TypingIndicator for the loading state
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SourceCard } from './SourceCard.jsx';
import { EchoEchoLogo } from './EchoEchoLogo.jsx';

// ── Citation pill ─────────────────────────────────────────────────────────────
// Matches patterns like:
//   [Source: filename.pdf, Page 3]
//   [Source: report.pdf, Page 12]
const CITATION_RE = /\[Source:\s*([^,\]]+),\s*Page\s*(\d+)\]/g;

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
    <span className="citation-pill" title={`${fileName}, Page ${page}`}>
      <span className="citation-pill-icon">📄</span>
      <span className="citation-pill-text">
        {fileName}
        <span className="citation-pill-page">p.{page}</span>
      </span>
    </span>
  );
}

// ── Custom react-markdown renderers ───────────────────────────────────────────
// We override the <p> renderer so citation patterns inside paragraphs get
// converted to pills. All other markdown elements render normally.
function markdownComponents() {
  return {
    // Replace citation patterns inside paragraph text nodes
    p({ children }) {
      const processed = processChildren(children);
      return <p>{processed}</p>;
    },
    // Style inline code
    code({ inline, children, ...props }) {
      if (inline) {
        return <code className="md-inline-code" {...props}>{children}</code>;
      }
      return (
        <pre className="md-code-block">
          <code {...props}>{children}</code>
        </pre>
      );
    },
    // Open links in new tab safely
    a({ href, children }) {
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className="md-link">
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
            // User messages: plain text (no markdown needed)
            <span>{message.content}</span>
          ) : (
            // Assistant messages: full markdown + citation pills
            <div className="md-body">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents()}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Source citation cards — shown below the bubble */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="sources-section">
            <p className="sources-label">
              {message.sources.length} source{message.sources.length !== 1 ? 's' : ''} cited
            </p>
            <div className="source-cards">
              {message.sources.map((src) => (
                <SourceCard key={src.id || src.rank} source={src} />
              ))}
            </div>
          </div>
        )}
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
