import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Brain, Send, Sparkles } from 'lucide-react';
import { getStoredToken } from '@/src/auth/AuthContext';
import { authHeaders } from '@/src/services/apiClient';

interface AIAssistantPanelProps {
  open: boolean;
  onClose: () => void;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
  sources?: string[];
}

interface SSESourcesEvent {
  type: 'sources';
  sources: string[];
}

interface SSETokenEvent {
  type: 'token';
  text: string;
}

interface SSEDoneEvent {
  type: 'done';
}

interface SSERefusalEvent {
  type: 'refusal';
}

interface SSEErrorEvent {
  type: 'error';
  text: string;
}

type SSEEvent = SSESourcesEvent | SSETokenEvent | SSEDoneEvent | SSERefusalEvent | SSEErrorEvent;

function parseSSELine(line: string): SSEEvent | null {
  if (!line.startsWith('data: ')) return null;
  try {
    return JSON.parse(line.slice(6));
  } catch {
    return null;
  }
}

function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-md`}>
      <div className={`max-w-[85%] rounded-xl px-3 py-2 text-body-sm leading-relaxed ${isUser ? 'bg-primary text-on-primary rounded-br-sm' : 'bg-surface-container-higher text-on-surface rounded-bl-sm'}`}>
        <p className="whitespace-pre-wrap break-words">{msg.text}</p>
        {!isUser && msg.sources && msg.sources.length > 0 && (
          <div className="mt-1.5 pt-1.5 border-t border-outline-variant/40">
            <p className="text-[10px] text-on-surface-variant">
              Source: {msg.sources.join(', ')}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AIAssistantPanel({ open, onClose }: AIAssistantPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const token = getStoredToken();
    if (!token) {
      setError('Please log in to use the AI Assistant.');
      return;
    }

    setError(null);
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setLoading(true);

    const assistantMessage: Message = { role: 'assistant', text: '' };
    setMessages((prev) => [...prev, assistantMessage]);

    let aborted = false;

    try {
      const response = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ message: text }),
      });

      if (response.status === 503) {
        const body = await response.json().catch(() => ({ detail: 'AI Assistant is temporarily unavailable' }));
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: 'assistant',
            text: body.detail || 'AI Assistant is temporarily unavailable.',
          };
          return next;
        });
        setLoading(false);
        return;
      }

      if (!response.ok) {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: 'assistant', text: `Request failed (${response.status}). Please try again.` };
          return next;
        });
        setLoading(false);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let hasSources = false;
      let isRefusal = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done || aborted) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          const event = parseSSELine(trimmed);
          if (!event) continue;

          switch (event.type) {
            case 'sources':
              hasSources = true;
              setMessages((prev) => {
                const next = [...prev];
                if (next.length > 0) {
                  next[next.length - 1] = { ...next[next.length - 1], sources: event.sources };
                }
                return next;
              });
              break;
            case 'token':
              setMessages((prev) => {
                const next = [...prev];
                if (next.length > 0) {
                  next[next.length - 1] = { ...next[next.length - 1], text: next[next.length - 1].text + event.text };
                }
                return next;
              });
              break;
            case 'done':
              break;
            case 'refusal':
              isRefusal = true;
              break;
            case 'error':
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { role: 'assistant', text: event.text || 'An error occurred.' };
                return next;
              });
              break;
          }
        }
      }

      if (isRefusal) {
        const refusalMsg = messages.findLast((m) => m.role === 'assistant')?.text || "I can answer questions about ergonomic thresholds, alerts, how the system works, and your session history. Try asking about your latest session, recent risk levels, or a specific worker.";
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: 'assistant', text: refusalMsg };
          return next;
        });
      }
    } catch (err) {
      if (aborted) return;
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: 'assistant',
          text: err instanceof TypeError && err.message.includes('fetch')
            ? 'AI Assistant is temporarily unavailable. Please check your connection.'
            : 'An unexpected error occurred.',
        };
        return next;
      });
    } finally {
      if (!aborted) setLoading(false);
    }
  }, [input, loading]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-50" onClick={onClose} />
      <div className="fixed top-0 right-0 bottom-0 z-50 w-96 bg-surface-container border-l border-outline-variant shadow-2xl flex flex-col">
        <div className="flex items-center justify-between p-lg border-b border-outline-variant">
          <div className="flex items-center gap-md">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Brain className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-title-md font-bold text-on-surface">AI Safety Assistant</h3>
              <p className="text-[10px] text-on-surface-variant">Knowledge-base Q&A</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-container-higher text-on-surface-variant transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {messages.length === 0 && !error ? (
          <div className="flex-1 overflow-y-auto p-lg flex flex-col items-center justify-center text-center text-on-surface-variant">
            <Sparkles className="w-10 h-10 mb-md opacity-20" />
            <p className="text-body-sm font-medium text-on-surface mb-1">Ask me anything about ergonomics</p>
            <p className="text-[11px] leading-relaxed text-center max-w-[220px]">
              I'm grounded in the ErgoVigilance knowledge base — thresholds, alerts, recommendations, and product features.
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-lg">
            {messages.map((msg, i) => (
              <ChatMessage key={i} msg={msg} />
            ))}
            {loading && (
              <div className="flex justify-start mb-md">
                <div className="max-w-[85%] rounded-xl px-3 py-2 bg-surface-container-higher text-on-surface rounded-bl-sm">
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            {error && (
              <div className="flex justify-center mb-md">
                <p className="text-body-sm text-error">{error}</p>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}

        <div className="border-t border-outline-variant p-lg">
          <div className="flex items-center gap-sm">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="Ask about ergonomics..."
              disabled={loading}
              className="flex-1 bg-surface-container-higher text-on-surface rounded-lg px-3 py-2 text-body-sm outline-none placeholder:text-on-surface-variant/50 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="p-2 rounded-lg bg-primary text-on-primary hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
