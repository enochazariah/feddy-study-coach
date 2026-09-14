import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiClient, getApiErrorMessage } from '../api/client';
import '../styles/tutor-chat.css';

// Define the shape of our chat messages
interface Message {
  role: 'user' | 'agent';
  content: string;
}

function AssistantMarkdown({ value }: { value: string }) {
  return (
    <div className="message-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        urlTransform={(url) => /^https?:\/\//i.test(url) ? url : ""}
        components={{
          a: ({ href, children }) => href ? (
            <a href={href} target="_blank" rel="noreferrer">{children}</a>
          ) : <span>{children}</span>,
          table: ({ children }) => (
            <div className="message-markdown__table-wrap">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {value}
      </ReactMarkdown>
    </div>
  );
}

export function TutorChat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'agent', content: "Hi! I'm Feddy, your AI study coach. What are we working on today?" }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the newest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    // 1. Add user message to UI immediately
    const userMsg = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setError(null);
    setIsLoading(true);

    try {
      // 2. Call the Django API
      const history = messages.map((item) => ({
        role: item.role === "agent" ? "assistant" as const : "user" as const,
        content: item.content,
      }));
      const response = await apiClient.chatWithTutor(userMsg, history);
      // 3. Add Feddy's response to the UI
      setMessages(prev => [...prev, { role: 'agent', content: response }]);
    } catch (error) {
      console.error('Feddy chat request failed:', error);
      setError(getApiErrorMessage(error, 'Feddy is currently offline. Please try again later.'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="tutor-chat">
      <header className="tutor-chat__header">
        <div>
          <p className="tutor-chat__eyebrow">Study companion</p>
          <h1>Feddy Study Coach</h1>
        </div>
        <span className="tutor-chat__status"><span /> Online</span>
      </header>

      {error && <div className="tutor-chat__error" role="alert">{error}</div>}

      <div className="tutor-chat__window" aria-live="polite" aria-busy={isLoading}>
        {messages.map((msg, idx) => (
          <div key={idx} className={`message-row message-row--${msg.role}`}>
            <div className={`message-bubble message-bubble--${msg.role}`}>
              <span className="message-label">{msg.role === 'user' ? 'You' : 'Feddy'}</span>
              {msg.role === 'agent'
                ? <AssistantMarkdown value={msg.content} />
                : msg.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="message-row message-row--agent">
            <div className="message-bubble message-bubble--agent thinking-indicator">
              <span className="message-label">Feddy</span>
              <span>Feddy is thinking</span><span className="thinking-dots" aria-hidden="true">...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} className="tutor-chat__form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Feddy a question..."
          className="tutor-chat__input"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="btn-primary tutor-chat__send"
        >
          Send <span aria-hidden="true">&rarr;</span>
        </button>
      </form>
    </main>
  );
}

export default TutorChat;