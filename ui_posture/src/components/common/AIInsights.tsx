import { Brain, TrendingUp, TrendingDown, Activity, AlertTriangle, Sparkles, Lightbulb } from 'lucide-react';
import type { ContextSnapshot } from '@/src/types/api';
import type { RecommendationsBundleResponse } from '@/src/types/api';

const iconOptions = [AlertTriangle, TrendingUp, TrendingDown, Activity, Sparkles, Lightbulb];

export function AIInsights({ snapshot, recData }: { snapshot: ContextSnapshot | null; recData: RecommendationsBundleResponse }) {
  const items: { icon: typeof Brain; color: string; bg: string; title: string; desc: string }[] = [];

  if (snapshot?.reason) {
    items.push({
      icon: Lightbulb,
      color: 'text-cyan-400',
      bg: 'bg-cyan-500/10',
      title: `Context — ${snapshot.risk_level}`,
      desc: snapshot.reason,
    });
  }

  if (recData?.bundle?.recommendations) {
    for (const rec of recData.bundle.recommendations.slice(0, 4)) {
      const Icon = iconOptions[items.length % iconOptions.length];
      const color = rec.priority === 'HIGH' ? 'text-red-400' : rec.priority === 'MEDIUM' ? 'text-orange-400' : 'text-green-400';
      const bg = rec.priority === 'HIGH' ? 'bg-red-500/10' : rec.priority === 'MEDIUM' ? 'bg-orange-500/10' : 'bg-green-500/10';
      items.push({ icon: Icon, color, bg, title: rec.title, desc: rec.description });
    }
  }

  if (items.length === 0) {
    return (
      <div className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <div className="flex items-center gap-md mb-md">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center"><Brain className="w-5 h-5 text-primary" /></div>
          <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">AI Insights</h3>
        </div>
        <p className="text-body-sm text-on-surface-variant">No insights available yet. Start a monitoring session.</p>
      </div>
    );
  }

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
      <div className="flex items-center gap-md mb-md">
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center"><Brain className="w-5 h-5 text-primary" /></div>
        <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">AI Insights</h3>
      </div>
      {items.map((item, i) => {
        const Icon = item.icon;
        return (
          <div key={i} className={`flex gap-md p-sm rounded-lg ${item.bg} border border-transparent`}>
            <Icon className={`w-5 h-5 ${item.color} shrink-0 mt-0.5`} />
            <div className="min-w-0">
              <p className="text-body-sm font-medium text-on-surface">{item.title}</p>
              <p className="text-[11px] text-on-surface-variant mt-0.5 leading-tight">{item.desc}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
