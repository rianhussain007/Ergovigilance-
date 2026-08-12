import { Lightbulb, AlertTriangle, User, Users, Briefcase } from 'lucide-react';
import { EmptyState } from '@/src/components/common';
import { useRecommendations } from '@/src/hooks/useRecommendations';
import type { RecommendationItem } from '@/src/types/api';

// Theme-aware priority colors (light variants defined in index.css).
const PRIORITY_COLORS: Record<string, string> = {
  Low: 'var(--color-chart-green)',
  Medium: 'var(--color-chart-orange)',
  High: 'var(--color-chart-red)',
  Critical: 'var(--color-chart-red)',
};

const PRIORITY_BG: Record<string, string> = {
  Low: 'color-mix(in srgb, var(--color-chart-green) 8%, transparent)',
  Medium: 'color-mix(in srgb, var(--color-chart-orange) 8%, transparent)',
  High: 'color-mix(in srgb, var(--color-chart-red) 8%, transparent)',
  Critical: 'color-mix(in srgb, var(--color-chart-red) 12%, transparent)',
};

const CATEGORY_ICONS: Record<string, typeof Lightbulb> = {
  Posture: Lightbulb,
  Break: AlertTriangle,
  Workstation: Briefcase,
  Training: Users,
  'Supervisor Action': Users,
  'Medical Review': AlertTriangle,
};

function targetIcon(target: string) {
  switch (target) {
    case 'Worker': return <User className="w-3 h-3" />;
    case 'Supervisor': return <Users className="w-3 h-3" />;
    default: return <Users className="w-3 h-3" />;
  }
}

function RecItem({ rec }: { rec: RecommendationItem }) {
  const Icon = CATEGORY_ICONS[rec.category] || Lightbulb;
  const color = PRIORITY_COLORS[rec.priority] || 'var(--color-outline)';
  const bg = PRIORITY_BG[rec.priority] || 'color-mix(in srgb, var(--color-outline) 8%, transparent)';

  return (
    <div
      className="rounded-lg px-md py-sm border transition-all duration-300"
      style={{ backgroundColor: bg, borderColor: `color-mix(in srgb, ${color} 19%, transparent)` }}
    >
      <div className="flex items-start gap-sm">
        <Icon className="w-4 h-4 shrink-0 mt-0.5" style={{ color }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-body-sm text-on-surface font-medium truncate">{rec.title}</span>
            <span
              className="text-[8px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
              style={{ color, backgroundColor: `${color}15` }}
            >
              {rec.priority}
            </span>
          </div>
          <p className="text-[10px] text-on-surface-variant leading-relaxed mt-0.5">{rec.description}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[8px] text-on-surface-variant bg-surface-container-higher px-1 rounded font-mono">
              {rec.category}
            </span>
            <span className="flex items-center gap-1 text-[8px] text-on-surface-variant">
              {targetIcon(rec.target)}
              {rec.target}
            </span>
            {rec.confidence > 0 && (
              <span className="text-[8px] text-on-surface-variant font-mono">
                {(rec.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function RecommendationsCard({ idle = false }: { idle?: boolean }) {
  const { data, loading } = useRecommendations();
  const { bundle, total_generated } = data;

  if (loading) {
    return (
      <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center gap-sm mb-md">
          <Lightbulb className="w-4 h-4 text-yellow-400" />
          <span className="text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
            Recommendations
          </span>
        </div>
        <div className="space-y-sm">
          <div className="h-4 bg-surface-container-higher rounded animate-pulse" />
          <div className="h-4 bg-surface-container-higher rounded animate-pulse w-3/4" />
        </div>
      </div>
    );
  }

  const recs = bundle?.recommendations ?? [];

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-sm">
          <Lightbulb className="w-4 h-4 text-yellow-400" />
          <span className="text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
            Recommendations
          </span>
        </div>
        <span className="text-[9px] bg-surface-container-higher text-on-surface-variant px-2 py-0.5 rounded-full font-mono">
          {total_generated}
        </span>
      </div>

      {bundle && (
        <div
          className="rounded-lg px-md py-sm text-center border transition-all duration-500"
          style={{
            backgroundColor: PRIORITY_BG[bundle.highest_priority] || 'color-mix(in srgb, var(--color-outline) 8%, transparent)',
            borderColor: `color-mix(in srgb, ${PRIORITY_COLORS[bundle.highest_priority] || 'var(--color-outline)'} 25%, transparent)`,
          }}
        >
          <span
            className="font-bold text-sm tracking-wider"
            style={{ color: PRIORITY_COLORS[bundle.highest_priority] || 'var(--color-on-surface-variant)' }}
          >
            {bundle.highest_priority}
          </span>
          <span className="text-[10px] text-on-surface-variant ml-2">HIGHEST PRIORITY</span>
        </div>
      )}

      {recs.length > 0 ? (
        <div className="space-y-sm max-h-64 overflow-y-auto">
          {recs.map((rec) => (
            <RecItem key={rec.id} rec={rec} />
          ))}
        </div>
      ) : idle ? (
        <EmptyState
          title="No recommendations yet"
          message="Start monitoring to see recommendations."
        />
      ) : (
        <EmptyState
          title="No recommendations"
          message="Recommendations will appear here when the engine detects risk conditions."
        />
      )}

      {bundle?.summary && (
        <p className="text-[10px] text-on-surface-variant leading-relaxed italic border-t border-outline-variant/30 pt-sm">
          {bundle.summary}
        </p>
      )}
    </div>
  );
}
