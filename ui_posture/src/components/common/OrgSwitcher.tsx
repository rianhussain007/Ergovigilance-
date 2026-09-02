import { useState, useEffect, useRef } from 'react';
import { Building2, ChevronDown, Check } from 'lucide-react';
import { apiFetch } from '@/src/services/apiClient';

interface Organization {
  id: number;
  name: string;
  slug: string;
  plan: string;
  industry: string;
  country: string;
  max_cameras: number;
  max_workers: number;
  created_at: string;
}

interface OrgSwitcherProps {
  currentOrgId?: number | null;
  onOrgChange?: (org: Organization) => void;
}

export function OrgSwitcher({ currentOrgId, onOrgChange }: OrgSwitcherProps = {}) {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchOrganizations();
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchOrganizations = async () => {
    try {
      const resp = await apiFetch('/api/orgs');
      const data = await resp.json();
      setOrgs(data.organizations || []);
    } catch (err) {
      console.error('Failed to fetch organizations:', err);
    } finally {
      setLoading(false);
    }
  };

  const currentOrg = orgs.find(o => o.id === currentOrgId);

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400">
        <Building2 className="w-4 h-4 animate-pulse" />
        <span>Loading...</span>
      </div>
    );
  }

  if (orgs.length <= 1) {
    // Single org or no orgs — just show the name
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300">
        <Building2 className="w-4 h-4 text-cyan-400" />
        <span className="font-medium">{currentOrg?.name || 'No Organization'}</span>
        {currentOrg && (
          <span className="text-xs text-slate-500 bg-white/5 px-1.5 py-0.5 rounded">
            {currentOrg.plan}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-white/5 rounded-lg transition-colors w-full"
      >
        <Building2 className="w-4 h-4 text-cyan-400 flex-shrink-0" />
        <span className="font-medium truncate">{currentOrg?.name || 'Select Organization'}</span>
        {currentOrg && (
          <span className="text-xs text-slate-500 bg-white/5 px-1.5 py-0.5 rounded flex-shrink-0">
            {currentOrg.plan}
          </span>
        )}
        <ChevronDown className={`w-4 h-4 ml-auto transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-slate-800 border border-white/10 rounded-lg shadow-xl overflow-hidden z-50">
          <div className="p-2 text-xs text-slate-500 uppercase tracking-wider border-b border-white/5">
            Switch Organization
          </div>
          {orgs.map((org) => (
            <button
              key={org.id}
              onClick={() => {
                onOrgChange(org);
                setIsOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm hover:bg-white/5 transition-colors ${
                org.id === currentOrgId ? 'bg-white/5' : ''
              }`}
            >
              <Building2 className="w-4 h-4 text-slate-400 flex-shrink-0" />
              <div className="flex-1 text-left">
                <div className="text-slate-200 font-medium">{org.name}</div>
                <div className="text-xs text-slate-500">{org.industry} · {org.country}</div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs text-slate-500 bg-white/5 px-1.5 py-0.5 rounded">
                  {org.plan}
                </span>
                {org.id === currentOrgId && (
                  <Check className="w-4 h-4 text-cyan-400" />
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
