import { Brain, ArrowDown, X, CheckCircle, Clock } from 'lucide-react';
import { EmptyState } from '@/src/components/common';
import { useContextSnapshot } from '@/src/hooks/useContextSnapshot';
import type { ContextSnapshot } from '@/src/types/api';

function riskColor(level: string): string {
  switch (level.toLowerCase()) {
    case 'low': return '#22c55e';
    case 'medium': return '#f97316';
    case 'high': return '#ef4444';
    default: return '#94a3b8';
  }
}

function riskLabel(level: string): string {
  const l = level.toLowerCase();
  if (l === 'low') return 'Low';
  if (l === 'medium') return 'Medium';
  if (l === 'high') return 'High';
  return level;
}

function riskFill(level: string): string {
  switch (level.toLowerCase()) {
    case 'low': return 'rgba(34,197,94,0.08)';
    case 'medium': return 'rgba(249,115,22,0.08)';
    case 'high': return 'rgba(239,68,68,0.08)';
    default: return 'rgba(148,163,184,0.08)';
  }
}

function rulaColor(score: number): string {
  if (score <= 2) return '#22c55e';
  if (score <= 4) return '#eab308';
  if (score <= 6) return '#f97316';
  return '#ef4444';
}

function SnapshotContent({ snapshot }: { snapshot: ContextSnapshot }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-x-md gap-y-sm">
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Final Risk</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5">{snapshot.final_risk.toFixed(1)}</p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Risk Level</span>
          <p className="text-body-sm text-on-surface font-medium mt-0.5">{riskLabel(snapshot.risk_level)}</p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Fatigue</span>
          <div className="flex items-center gap-2 mt-0.5">
            <div className="flex-1 h-1.5 bg-surface-container-higher rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, snapshot.fatigue_score)}%`,
                  background: snapshot.fatigue_score > 60
                    ? 'linear-gradient(90deg, #f97316, #ef4444)'
                    : snapshot.fatigue_score > 30
                      ? 'linear-gradient(90deg, #22c55e, #f97316)'
                      : '#22c55e',
                }}
              />
            </div>
            <span className="text-body-sm text-on-surface font-mono w-8 text-right">{snapshot.fatigue_score.toFixed(0)}%</span>
          </div>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Exposure</span>
          <div className="flex items-center gap-2 mt-0.5">
            <div className="flex-1 h-1.5 bg-surface-container-higher rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, snapshot.exposure_score)}%`,
                  background: snapshot.exposure_score > 60
                    ? 'linear-gradient(90deg, #f97316, #ef4444)'
                    : snapshot.exposure_score > 30
                      ? 'linear-gradient(90deg, #22c55e, #f97316)'
                      : '#22c55e',
                }}
              />
            </div>
            <span className="text-body-sm text-on-surface font-mono w-8 text-right">{snapshot.exposure_score.toFixed(0)}%</span>
          </div>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Confidence</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5">{snapshot.confidence_modifier.toFixed(1)}%</p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Context Modifier</span>
          <p className={`text-body-sm font-mono mt-0.5 ${snapshot.context_modifier > 0 ? 'text-orange-400' : snapshot.context_modifier < 0 ? 'text-green-400' : 'text-on-surface'}`}>
            {snapshot.context_modifier > 0 ? '+' : ''}{snapshot.context_modifier.toFixed(1)}
          </p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Session</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5 truncate">{snapshot.session_id}</p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Frame</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5">#{snapshot.frame_number}</p>
        </div>
        {snapshot.rula_informed_score != null && (
          <div>
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider flex items-center gap-1">
              RULA Score
              <span className="text-[8px] italic font-normal normal-case tracking-normal opacity-50">informed</span>
            </span>
            <p className="text-body-sm font-mono mt-0.5" style={{ color: snapshot.rula_is_partial ? '#f59e0b' : rulaColor(snapshot.rula_informed_score) }}>
              {snapshot.rula_informed_score}/7
            </p>
            {snapshot.rula_is_partial && (
              <div className="flex items-center gap-1.5 mt-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1">
                <span className="text-amber-400 text-[10px]">⚠</span>
                <span className="text-[10px] font-medium text-amber-400">
                  Unreliable &mdash; insufficient landmark data
                </span>
              </div>
            )}
          </div>
        )}
        {snapshot.calibrated_band != null && (
          <div>
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider flex items-center gap-1">
              Calibrated Model
              <span className="text-[8px] italic font-normal normal-case tracking-normal opacity-50">REBA-informed</span>
            </span>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-body-sm font-mono" style={{ color: riskColor(snapshot.calibrated_band) }}>
                {riskLabel(snapshot.calibrated_band)}
              </p>
              {snapshot.calibrated_confidence != null && (
                <span className="text-[10px] text-on-surface-variant font-mono">
                  {Math.round(snapshot.calibrated_confidence * 100)}% conf
                </span>
              )}
            </div>
            {snapshot.calibrated_agrees != null && (
              <div
                className={`flex items-center gap-1.5 mt-1 rounded-md border px-2 py-1 ${
                  snapshot.calibrated_agrees
                    ? 'border-green-500/30 bg-green-500/10'
                    : 'border-amber-500/30 bg-amber-500/10'
                }`}
              >
                {snapshot.calibrated_agrees ? (
                  <CheckCircle className="w-3 h-3 text-green-400 shrink-0" />
                ) : (
                  <X className="w-3 h-3 text-amber-400 shrink-0" />
                )}
                <span className={`text-[10px] font-medium ${snapshot.calibrated_agrees ? 'text-green-400' : 'text-amber-400'}`}>
                  {snapshot.calibrated_agrees
                    ? 'Model agrees with rule-based risk'
                    : 'Model disagrees — review posture'}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      <div
        className="rounded-lg px-md py-sm text-center border"
        style={{
          backgroundColor: riskFill(snapshot.risk_level),
          borderColor: `${riskColor(snapshot.risk_level)}40`,
        }}
      >
        <span
          className="font-bold text-sm tracking-wider"
          style={{ color: riskColor(snapshot.risk_level) }}
        >
          {riskLabel(snapshot.risk_level)}
        </span>
        <span className="text-[10px] text-on-surface-variant ml-2">FINAL CONTEXT RISK</span>
      </div>

      {snapshot.unavailable_features && snapshot.unavailable_features.length > 0 && (
        <div className="rounded-lg px-md py-sm border border-amber-500/30 bg-amber-500/10">
          <div className="flex items-center gap-2">
            <span className="text-amber-400 text-sm">⚠</span>
            <span className="text-[11px] font-medium text-amber-400">
              {snapshot.unavailable_features.includes('knee_angle') || snapshot.unavailable_features.includes('trunk_flexion')
                ? 'Lower body out of frame — reposition camera'
                : 'Some features unavailable — limited assessment'}
            </span>
          </div>
          <p className="text-[9px] text-amber-400/70 mt-1">
            Unavailable: {snapshot.unavailable_features.join(', ')}
          </p>
        </div>
      )}

      {snapshot.active_rules.length > 0 && (
        <div>
          <span className="text-[9px] uppercase tracking-widest text-on-surface-variant font-bold">Active Rules</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {snapshot.active_rules.map((rule) => (
              <span key={rule} className="text-[9px] font-mono bg-purple-500/10 text-purple-400 px-1.5 py-0.5 rounded">
                {rule}
              </span>
            ))}
          </div>
        </div>
      )}

      {snapshot.reason && (
        <p className="text-[10px] text-on-surface-variant leading-relaxed italic border-t border-outline-variant/30 pt-sm">
          {snapshot.reason}
        </p>
      )}
    </>
  );
}

export default function ContextAwareRiskCard() {
  const { snapshot, loading } = useContextSnapshot();

  if (loading) {
    return (
      <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center gap-sm mb-md">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
            Context-Aware Risk
          </span>
        </div>
        <div className="space-y-sm">
          <div className="h-4 bg-surface-container-higher rounded animate-pulse" />
          <div className="h-4 bg-surface-container-higher rounded animate-pulse w-3/4" />
          <div className="h-4 bg-surface-container-higher rounded animate-pulse w-1/2" />
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center gap-sm mb-md">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
            Context-Aware Risk
          </span>
        </div>
        <EmptyState
          title="No active session"
          message="Start a monitoring session to see context-aware risk assessment."
        />
      </div>
    );
  }

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-sm">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
            Context-Aware Risk
          </span>
        </div>
        <span className="text-[9px] font-mono text-on-surface-variant">
          {new Date(snapshot.captured_at).toLocaleTimeString()}
        </span>
      </div>

      <SnapshotContent snapshot={snapshot} />
    </div>
  );
}
