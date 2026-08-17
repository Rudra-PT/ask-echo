import { useEffect, useRef } from 'react';
import { MessageBubble, TypingIndicator } from './MessageBubble.jsx';
import { EchoEchoLogo } from './EchoEchoLogo.jsx';

export function ChatWindow({ messages, isLoading }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="messages-window">
        <div className="empty-state">
          <div className="empty-state-logo-wrapper">
            <EchoEchoLogo size={80} />
          </div>
          <p className="empty-state-title">Ask-Echo is ready</p>
          <p className="empty-state-sub">
            Upload a document using the sidebar, then ask anything about it below.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="messages-window" role="log" aria-live="polite">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {isLoading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
