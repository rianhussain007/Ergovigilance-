import React from 'react';
import type { ErgonomicFeature } from '@/src/types/api';

interface FeatureCardProps {
  feature: ErgonomicFeature;
  isApproximate?: boolean;
}

const statusColor: Record<string, string> = {
  good: 'bg-green-500',
  low: 'bg-blue-500',
  moderate: 'bg-orange-500',
  high: 'bg-red-500',
  unavailable: 'bg-gray-500/50',
  approximate: 'bg-amber-500/70',
};

const statusBarColor: Record<string, string> = {
  good: 'bg-green-500/20 border-green-500/30',
  low: 'bg-blue-500/20 border-blue-500/30',
  moderate: 'bg-orange-500/20 border-orange-500/30',
  high: 'bg-red-500/20 border-red-500/30',
  unavailable: 'bg-surface-container border-outline-variant/30',
  approximate: 'bg-amber-500/10 border-amber-500/30',
};

export const FeatureCard: React.FC<FeatureCardProps> = ({ feature, isApproximate }) => {
  const isUnavailable = feature.status === 'unavailable' || feature.value === null;
  const pct = isUnavailable || isApproximate ? 0 : Math.min(100, ((feature.value - feature.min) / (feature.max - feature.min)) * 100);
  const variant = isApproximate ? 'approximate' : isUnavailable ? 'unavailable' : feature.status;

  return (
    <div className={`rounded-xl p-md border ${isUnavailable ? statusBarColor.unavailable + ' opacity-60' : statusBarColor[variant] || 'bg-surface-container border-outline-variant'}`}>
      <div className="flex items-center justify-between mb-sm">
        <span className="text-body-sm font-medium text-on-surface-variant">{feature.name}</span>
        <span className="font-label-mono text-label-mono text-on-surface flex items-center gap-1">
          {isUnavailable ? 'N/A' : isApproximate ? `~${feature.value}${feature.unit}` : `${feature.value}${feature.unit}`}
          {isApproximate && (
            <span className="text-[9px] text-amber-400/70 italic font-normal" title="Computed via fallback method (image-vertical instead of hip-anchored)">
              approx
            </span>
          )}
        </span>
      </div>
      <div className="h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${isUnavailable ? statusColor.unavailable : statusColor[variant] || 'bg-primary'}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}
