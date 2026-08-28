import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Brain, Send, Sparkles, AlertTriangle, TrendingUp, Shield, Activity, Clock } from 'lucide-react';
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

interface LiveContext {
  has_active_session: boolean;
  session_id?: string;
  risk_level?: string;
  risk_score?: number;
  current_task?: string;
  task_confidence?: number;
  session_duration?: number;
  active_alerts?: Array<{ severity: string; title: string; message: string }>;
  recent_issues?: Array<{ name: string; severity: string; detail: string }>;
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

function ContextBadge({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] font-medium ${color}`}>
      <span className="truncate">{label}</span>
      <span className="font-bold">{value}</span>
    </div>
  );
}

export default function AIAssistantPanel({ open, onClose }: AIAssistantPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveContext, setLiveContext] = useState<LiveContext | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
      // Fetch live context when panel opens
      fetchLiveContext();
    }
  }, [open]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const fetchLiveContext = async () => {
    try {
      const token = getStoredToken();
      if (!token) return;
      const res = await fetch('/api/assistant/context', {
        headers: authHeaders({}),
      });
      if (res.ok) {
        const data = await res.json();
        setLiveContext(data);
      }
    } catch {
      // Silently fail — context is optional
    }
  };

  const handleSend = useCallback(async (overrideText?: string) => {
    const text = (overrideText || input).trim();
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
        const refusalMsg = "I can answer questions about ergonomic thresholds, alerts, how the system works, and your session history. Try asking about your latest session, recent risk levels, or a specific worker.";
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

  const riskColor = (level?: string) => {
    switch ((level || '').toLowerCase()) {
      case 'high': case 'critical': return 'bg-red-500/15 text-red-400 border border-red-500/30';
      case 'medium': return 'bg-amber-500/15 text-amber-400 border border-amber-500/30';
      default: return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
    }
  };

  const quickActions = liveContext?.has_active_session ? [
    { icon: Shield, label: 'Current Risk', question: 'What is the current risk level and why?', color: riskColor(liveContext.risk_level) },
    { icon: Activity, label: 'Current Task', question: `What task is being performed right now? Is the posture safe for this task?`, color: 'bg-blue-500/15 text-blue-400 border border-blue-500/30' },
    { icon: AlertTriangle, label: 'Active Alerts', question: 'What alerts are currently active? What should I do about them?', color: 'bg-orange-500/15 text-orange-400 border border-orange-500/30' },
    { icon: TrendingUp, label: 'Risk Trend', question: 'Is the risk improving or worsening over this session?', color: 'bg-purple-500/15 text-purple-400 border border-purple-500/30' },
  ] : [
    { icon: Shield, label: 'RULA Scores', question: 'What do RULA scores mean? How are they calculated?', color: 'bg-blue-500/15 text-blue-400 border border-blue-500/30' },
    { icon: Activity, label: 'Alert Thresholds', question: 'What are the alert thresholds? When does the system trigger an alert?', color: 'bg-amber-500/15 text-amber-400 border border-amber-500/30' },
    { icon: AlertTriangle, label: 'System Features', question: 'What features does ErgoVigilance provide? How does it work?', color: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' },
    { icon: TrendingUp, label: 'Best Practices', question: 'What are the best ergonomic practices for assembly line workers?', color: 'bg-purple-500/15 text-purple-400 border border-purple-500/30' },
  ];

  return (
    <>
      <div className="fixed inset-0 z-50" onClick={onClose} />
      <div className="fixed top-0 right-0 bottom-0 z-50 w-96 bg-surface-container border-l border-outline-variant shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-lg border-b border-outline-variant">
          <div className="flex items-center gap-md">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Brain className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-title-md font-bold text-on-surface">AI Safety Assistant</h3>
              <p className="text-[10px] text-on-surface-variant">Context-aware ergonomics Q&A</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-container-higher text-on-surface-variant transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Live Context Bar */}
        {liveContext?.has_active_session && (
          <div className="px-lg py-2 border-b border-outline-variant bg-surface-container-low flex flex-wrap gap-1.5">
            <ContextBadge label="Risk:" value={liveContext.risk_level || '—'} color={riskColor(liveContext.risk_level)} />
            <ContextBadge label="Task:" value={liveContext.current_task || '—'} color="bg-slate-500/15 text-slate-400 border border-slate-500/30" />
            {liveContext.session_duration != null && liveContext.session_duration > 0 && (
              <ContextBadge label="Duration:" value={`${Math.round(liveContext.session_duration)}s`} color="bg-slate-500/15 text-slate-400 border border-slate-500/30" />
            )}
            {liveContext.active_alerts && liveContext.active_alerts.length > 0 && (
              <ContextBadge label="Alerts:" value={`${liveContext.active_alerts.length}`} color="bg-red-500/15 text-red-400 border border-red-500/30" />
            )}
          </div>
        )}

        {messages.length === 0 && !error ? (
          <div className="flex-1 overflow-y-auto p-lg flex flex-col items-center justify-center text-center text-on-surface-variant">
            <Sparkles className="w-10 h-10 mb-md opacity-20" />
            <p className="text-body-sm font-medium text-on-surface mb-1">
              {liveContext?.has_active_session ? 'Ask about the current session' : 'Ask me anything about ergonomics'}
            </p>
            <p className="text-[11px] leading-relaxed text-center max-w-[240px] mb-lg">
              {liveContext?.has_active_session
                ? `Monitoring ${liveContext.current_task || 'a worker'} — I can explain the current risk, suggest corrections, or answer threshold questions.`
                : "I'm grounded in the ErgoVigilance knowledge base — thresholds, alerts, recommendations, and product features."}
            </p>

            {/* Quick Action Buttons */}
            <div className="grid grid-cols-2 gap-2 w-full max-w-[280px]">
              {quickActions.map((action, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(action.question)}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-left transition-all hover:scale-[1.02] ${action.color}`}
                >
                  <action.icon className="w-3.5 h-3.5 shrink-0" />
                  <span className="text-[11px] font-medium">{action.label}</span>
                </button>
              ))}
            </div>
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
              placeholder={liveContext?.has_active_session ? "Ask about current risk, task, or alerts..." : "Ask about ergonomics..."}
              disabled={loading}
              className="flex-1 bg-surface-container-higher text-on-surface rounded-lg px-3 py-2 text-body-sm outline-none placeholder:text-on-surface-variant/50 disabled:opacity-50"
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="p-2 rounded-lg bg-primary text-on-primary hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          {liveContext?.has_active_session && messages.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {quickActions.slice(0, 2).map((action, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(action.question)}
                  className="text-[10px] px-2 py-1 rounded-full bg-surface-container-higher text-on-surface-variant hover:text-on-surface transition-colors"
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
