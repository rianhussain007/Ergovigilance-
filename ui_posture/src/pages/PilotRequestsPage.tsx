import React, { useEffect, useState } from 'react';
import { apiFetch } from '@/src/services/apiClient';
import { useAuth } from '@/src/auth/AuthContext';
import { Navigate } from 'react-router-dom';

interface PilotRequest {
  id: number;
  company_name: string;
  contact_name: string;
  email: string;
  role: string;
  num_stations: string | null;
  message: string | null;
  created_at: string;
}

export default function PilotRequestsPage() {
  const [requests, setRequests] = useState<PilotRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    const fetchRequests = async () => {
      try {
        const res = await apiFetch('/api/pilot-requests');
        const data = await res.json();
        setRequests(data);
      } catch (err) {
        console.error('Failed to fetch pilot requests:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchRequests();
  }, []);

  if (!user || user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }

  if (loading) {
    return (
      <div className="p-lg">
        <div className="text-on-surface-variant">Loading pilot requests...</div>
      </div>
    );
  }

  return (
    <div className="p-lg space-y-lg">
      <div>
        <h1 className="text-display-md font-bold text-on-surface">Pilot Requests</h1>
        <p className="text-body-md text-on-surface-variant">View all submitted pilot requests.</p>
      </div>

      <div className="space-y-md">
        {requests.length === 0 ? (
          <div className="text-center py-xl text-on-surface-variant">
            No pilot requests yet.
          </div>
        ) : (
          requests.map((req) => (
            <div
              key={req.id}
              className="bg-surface-container border border-outline-variant rounded-xl p-lg"
            >
              <div className="flex items-start justify-between gap-md mb-md">
                <div>
                  <h3 className="text-title-sm font-bold text-on-surface">{req.company_name}</h3>
                  <p className="text-body-sm text-on-surface-variant">{req.contact_name} • {req.email}</p>
                </div>
                <div className="text-right">
                  <span className="text-body-sm font-medium text-primary">{req.role}</span>
                  <p className="text-xs text-on-surface-variant mt-xs">
                    {new Date(req.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
              {req.num_stations && (
                <div className="mb-md">
                  <span className="text-body-sm font-medium text-on-surface">Stations/Workers: </span>
                  <span className="text-body-sm text-on-surface-variant">{req.num_stations}</span>
                </div>
              )}
              {req.message && (
                <div>
                  <span className="text-body-sm font-medium text-on-surface">Message: </span>
                  <p className="text-body-sm text-on-surface-variant mt-xs">{req.message}</p>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
