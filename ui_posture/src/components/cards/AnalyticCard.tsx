interface AnalyticCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  accent?: boolean;
  tone?: 'neutral' | 'good' | 'warning' | 'danger';
  isUrgent?: boolean;
}

export function AnalyticCard({ label, value, subtext, accent, tone = 'neutral', isUrgent = false }: AnalyticCardProps) {
  // Check if value is non-zero for urgent metrics
  const numericValue = typeof value === 'number' ? value : parseFloat(value);
  const hasNonZeroUrgent = isUrgent && !isNaN(numericValue) && numericValue > 0;
  
  // Tone styling
  const iconColorClass = tone === 'danger' ? 'text-red-400' : tone === 'warning' ? 'text-orange-400' : tone === 'good' ? 'text-green-400' : '';
  const leftBorderClass = tone === 'danger' ? 'border-l-red-500' : tone === 'warning' ? 'border-l-orange-500' : tone === 'good' ? 'border-l-green-500' : 'border-l-outline-variant';
  const bgClass = hasNonZeroUrgent 
    ? (tone === 'danger' ? 'bg-red-500/10' : tone === 'warning' ? 'bg-orange-500/10' : tone === 'good' ? 'bg-green-500/10' : 'bg-surface-container')
    : 'bg-surface-container';
  const otherBorderClass = tone === 'danger' ? 'border-t border-r border-b border-red-500/30' : tone === 'warning' ? 'border-t border-r border-b border-orange-500/30' : tone === 'good' ? 'border-t border-r border-b border-green-500/30' : 'border-t border-r border-b border-outline-variant';
  const textColorClass = tone === 'danger' ? 'text-red-400' : tone === 'warning' ? 'text-orange-400' : tone === 'good' ? 'text-green-400' : (accent ? 'text-primary' : 'text-on-surface');
  const textSizeClass = isUrgent ? 'text-headline-lg' : 'text-headline-md';
  
  return (
    <div className={`${bgClass} border-l-4 ${leftBorderClass} ${otherBorderClass} rounded-xl p-md`}>
      <span className="font-label-caps text-label-caps text-on-surface-variant block mb-xs uppercase tracking-widest">{label}</span>
      <span className={`${textSizeClass} font-bold ${textColorClass}`}>{value}</span>
      {subtext && <p className="text-body-sm text-on-surface-variant mt-xs">{subtext}</p>}
    </div>
  );
}
