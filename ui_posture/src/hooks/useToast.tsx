import React, { createContext, useCallback, useContext, useState } from 'react';
import { X, CheckCircle, AlertTriangle, Info, AlertOctagon } from 'lucide-react';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  type: ToastType;
  title: string;
  message?: string;
  onClick?: () => void;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (type: ToastType, title: string, message?: string, duration?: number, onClick?: () => void) => void;
  removeToast: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

const iconMap: Record<ToastType, React.ComponentType<{ className?: string }>> = {
  success: CheckCircle,
  error: AlertOctagon,
  info: Info,
  warning: AlertTriangle,
};

const colorMap: Record<ToastType, string> = {
  success: 'border-green-500/30 bg-green-500/10 text-green-400',
  error: 'border-red-500/30 bg-red-500/10 text-red-400',
  info: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  warning: 'border-orange-500/30 bg-orange-500/10 text-orange-400',
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: ToastType, title: string, message?: string, duration?: number, onClick?: () => void) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, type, title, message, onClick }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration ?? 4000);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="fixed left-4 bottom-4 sm:left-6 sm:bottom-6 z-[200] flex flex-col gap-sm" style={{ width: 'min(24rem, calc(100vw - 2rem))', maxWidth: 'calc(100vw - 2rem)' }}>
        {toasts.slice(-2).map((toast) => {
          const Icon = iconMap[toast.type];
          return (
            <div
              key={toast.id}
              onClick={() => { toast.onClick?.(); removeToast(toast.id); }}
              className={`flex w-full items-start gap-md px-md py-sm rounded-lg border ${colorMap[toast.type]} backdrop-blur-md shadow-xl animate-slide-in ${toast.onClick ? 'cursor-pointer' : ''}`}
            >
              <Icon className="w-5 h-5 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-body-sm font-bold">{toast.title}</p>
                {toast.message && <p className="text-[11px] opacity-80 mt-0.5 break-words">{toast.message}</p>}
              </div>
              <button onClick={(e) => { e.stopPropagation(); removeToast(toast.id); }} className="shrink-0 opacity-60 hover:opacity-100 transition-opacity">
                <X className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
