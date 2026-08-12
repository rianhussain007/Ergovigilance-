import React, { useEffect, useState } from 'react';
import { AlertTriangle, X, ShieldCheck, Info, Clock, TrendingUp } from 'lucide-react';

interface AlertToastProps {
  id: string;
  type: 'error' | 'warning' | 'info' | 'success';
  title: string;
  message: string;
  duration?: number;
  onClose?: () => void;
  onClick?: () => void;
}

const TOAST_CONFIG = {
  error: {
    bg: 'bg-gradient-to-r from-red-500/20 to-red-500/10',
    border: 'border-red-500/30',
    icon: AlertTriangle,
    iconColor: 'text-red-500',
    progress: 'bg-red-500',
    pulse: true,
  },
  warning: {
    bg: 'bg-gradient-to-r from-orange-500/20 to-orange-500/10',
    border: 'border-orange-500/30',
    icon: AlertTriangle,
    iconColor: 'text-orange-500',
    progress: 'bg-orange-500',
    pulse: true,
  },
  info: {
    bg: 'bg-gradient-to-r from-blue-500/20 to-blue-500/10',
    border: 'border-blue-500/30',
    icon: Info,
    iconColor: 'text-blue-500',
    progress: 'bg-blue-500',
    pulse: false,
  },
  success: {
    bg: 'bg-gradient-to-r from-green-500/20 to-green-500/10',
    border: 'border-green-500/30',
    icon: ShieldCheck,
    iconColor: 'text-green-500',
    progress: 'bg-green-500',
    pulse: false,
  },
};

export function AlertToast({
  id,
  type,
  title,
  message,
  duration = 6000,
  onClose,
  onClick,
}: AlertToastProps) {
  const [isVisible, setIsVisible] = useState(true);
  const [progress, setProgress] = useState(100);
  const config = TOAST_CONFIG[type];
  const Icon = config.icon;

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev <= 0) {
          clearInterval(interval);
          return 0;
        }
        return prev - (100 / (duration / 50));
      });
    }, 50);

    return () => clearInterval(interval);
  }, [duration]);

  useEffect(() => {
    if (progress <= 0) {
      setIsVisible(false);
      setTimeout(() => onClose?.(), 300);
    }
  }, [progress, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(() => onClose?.(), 300);
  };

  if (!isVisible) return null;

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 w-80 ${config.bg} border ${config.border} rounded-xl shadow-2xl backdrop-blur-sm transform transition-all duration-300 ${
        isVisible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
      }`}
      onClick={onClick}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${config.bg}`}>
            <Icon className={`w-4 h-4 ${config.iconColor} ${config.pulse ? 'animate-pulse' : ''}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-on-surface">{title}</p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleClose();
                }}
                className="p-1 rounded-lg hover:bg-surface-container-higher text-on-surface-variant transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
            <p className="text-xs text-on-surface-variant mt-1 line-clamp-2">{message}</p>
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="mt-3 h-0.5 bg-surface-container-higher rounded-full overflow-hidden">
          <div
            className={`h-full ${config.progress} transition-all duration-100 ease-linear`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export default AlertToast;
