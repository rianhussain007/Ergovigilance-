interface ReportButtonProps {
  label: string;
  color: 'primary' | 'orange' | 'blue' | 'green';
}

const colorMap: Record<string, { border: string; text: string; hover: string }> = {
  primary: { border: 'border-primary/30', text: 'text-primary', hover: 'hover:bg-primary/5' },
  orange: { border: 'border-orange-500/30', text: 'text-orange-400', hover: 'hover:bg-orange-500/5' },
  blue: { border: 'border-blue-500/30', text: 'text-blue-400', hover: 'hover:bg-blue-500/5' },
  green: { border: 'border-green-500/30', text: 'text-green-400', hover: 'hover:bg-green-500/5' },
};

export function ReportButton({ label, color }: ReportButtonProps) {
  const c = colorMap[color] || colorMap.primary;
  return (
    <button
      className={`flex items-center justify-center gap-sm bg-surface-container border ${c.border} ${c.text} px-lg py-md rounded-lg font-body-md font-bold ${c.hover} transition-all`}
    >
      {label}
    </button>
  );
}
