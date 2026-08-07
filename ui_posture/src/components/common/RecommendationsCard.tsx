import { Lightbulb, AlertTriangle, User, Users, Briefcase } from 'lucide-react';
import { EmptyState } from '@/src/components/common';
import { useRecommendations } from '@/src/hooks/useRecommendations';
import type { RecommendationItem } from '@/src/types/api';

const PRIORITY_COLORS: Record<string, string> = {
  Low: '#22c55e',
  Medium: '#f97316',
  High: '#ef4444',
  Critical: '#dc2626',
};

const PRIORITY_BG: Record<string, string> = {
  Low: 'rgba(34,197,94,0.08)',
  Medium: 'rgba(249,115,22,0.08)',
  High: 'rgba(239,68,68,0.08)',
  Critical: 'rgba(220,38,38,0.12)',
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
  const color = PRIORITY_COLORS[rec.priority] || '#6b7280';
  const bg = PRIORITY_BG[rec.priority] || 'rgba(107,114,128,0.08)';

  return (
    <div
      className="rounded-lg px-md py-sm border transition-all duration-300"
      style={{ backgroundColor: bg, borderColor: `${color}30` }}
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

export default function RecommendationsCard() {
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
            backgroundColor: PRIORITY_BG[bundle.highest_priority] || 'rgba(107,114,128,0.08)',
            borderColor: `${PRIORITY_COLORS[bundle.highest_priority] || '#6b7280'}40`,
          }}
        >
          <span
            className="font-bold text-sm tracking-wider"
            style={{ color: PRIORITY_COLORS[bundle.highest_priority] || '#6b7280' }}
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
