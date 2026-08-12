/**
 * Shared industrial backdrop for the public pages (login, forgot-password,
 * pilot request, landing). One visual language everywhere:
 *   - a faint blueprint dot-grid (theme primary, so it reads in dark + light)
 *   - amber ("steel") glow top-right + primary glow bottom-left
 *   - optional hairline accent across the very top of the viewport
 * All layers are color-mix()'d from theme tokens so the treatment is
 * theme-aware by construction, and `fixed` so any page can drop it in
 * without touching its own layout.
 */
export default function IndustrialBackdrop({ accentLine = false }: { accentLine?: boolean }) {
  return (
    <>
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          backgroundImage:
            'radial-gradient(circle, color-mix(in srgb, var(--color-primary) 9%, transparent) 1px, transparent 1.5px)',
          backgroundSize: '24px 24px',
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            'radial-gradient(900px 520px at 85% -8%, color-mix(in srgb, var(--color-warning) 9%, transparent), transparent 62%),' +
            'radial-gradient(760px 480px at 6% 110%, color-mix(in srgb, var(--color-primary) 12%, transparent), transparent 58%)',
        }}
      />
      {accentLine && (
        <div
          aria-hidden
          className="pointer-events-none fixed top-0 left-1/2 -translate-x-1/2 h-px w-[min(90vw,520px)] bg-gradient-to-r from-transparent via-primary/40 to-transparent"
        />
      )}
    </>
  );
}
