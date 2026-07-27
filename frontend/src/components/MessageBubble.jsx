import { SourceCard } from './SourceCard.jsx';
import { EchoEchoLogo } from './EchoEchoLogo.jsx';








export function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      <div className={`avatar ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? '👤' : <EchoEchoLogo size={20} />}
      </div>

      <div className="bubble-group">
        <div className="bubble">{message.content}</div>

        {}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="sources-section">
            <p className="sources-label">
              {message.sources.length} source{message.sources.length !== 1 ? 's' : ''} cited
            </p>
            <div className="source-cards">
              {message.sources.map((src) => (
                <SourceCard key={src.id} source={src} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


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
