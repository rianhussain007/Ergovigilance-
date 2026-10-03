import { useEffect, useId, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Style the confirm action as destructive (red) and focus Cancel first. */
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * In-app confirmation dialog.
 *
 * Replaces `window.confirm` in product code (guarded by
 * scripts/ux_guards.mjs): the native dialog cannot be styled or themed, is
 * blocked in some kiosk/PWA shells, and gives screen-reader users no context
 * about which record they are about to change. This is a real modal dialog —
 * labelled, Escape-cancellable, focus moved in and restored on close.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    // Destructive actions focus Cancel — a stray Enter must not delete data.
    const target = panelRef.current?.querySelector<HTMLElement>(
      destructive ? '[data-confirm-cancel]' : '[data-confirm-action]',
    );
    target?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onCancel();
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      restoreFocusRef.current?.focus?.();
    };
  }, [open, destructive, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        aria-hidden="true"
        className="absolute inset-0"
        onClick={() => !busy && onCancel()}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-md rounded-2xl border border-outline-variant bg-surface-container p-lg shadow-2xl"
      >
        <div className="flex items-start gap-md">
          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
              destructive ? 'bg-red-500/10' : 'bg-primary/10'
            }`}
          >
            <AlertTriangle className={`h-5 w-5 ${destructive ? 'text-red-400' : 'text-primary'}`} />
          </div>
          <div className="space-y-xs">
            <h2 id={titleId} className="text-title-md font-bold text-on-surface">
              {title}
            </h2>
            <p className="text-body-sm text-on-surface-variant">{message}</p>
          </div>
        </div>

        <div className="mt-lg flex justify-end gap-sm">
          <button
            type="button"
            data-confirm-cancel
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg border border-outline-variant px-md py-sm text-body-sm text-on-surface-variant transition-colors hover:bg-surface-container-higher hover:text-on-surface disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            data-confirm-action
            onClick={onConfirm}
            disabled={busy}
            className={`rounded-lg px-md py-sm text-body-sm font-bold transition-colors disabled:opacity-50 ${
              destructive
                ? 'bg-red-500/90 text-white hover:bg-red-500'
                : 'bg-primary text-on-primary hover:bg-primary/90'
            }`}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmDialog;
