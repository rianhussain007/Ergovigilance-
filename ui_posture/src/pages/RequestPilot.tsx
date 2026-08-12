import React, { useState } from 'react';
import { Link } from 'react-router';
import { ChevronRight } from 'lucide-react';
import { IndustrialBackdrop } from '@/src/components/common';

export default function RequestPilot() {
  const [formData, setFormData] = useState({
    companyName: '',
    contactName: '',
    email: '',
    role: 'EHS Manager',
    numStations: '',
    message: '',
  });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch('/api/pilot-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: formData.companyName,
          contact_name: formData.contactName,
          email: formData.email,
          role: formData.role,
          num_stations: formData.numStations || null,
          message: formData.message || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Something went wrong');
      }

      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-surface text-on-surface flex items-center justify-center px-8">
        {/* Industrial backdrop — shared with every public page */}
        <IndustrialBackdrop accentLine />
        <div className="relative max-w-3xl w-full bg-surface-container border border-outline-variant rounded-xl p-12 text-center animate-fade-in">
          <h2 className="text-4xl font-bold mb-8">Thank You!</h2>
          <p className="text-xl text-on-surface-variant mb-12 leading-relaxed">
            Your pilot request has been submitted successfully. We will contact you shortly.
          </p>
          <Link to="/" className="inline-flex items-center gap-2 px-10 py-5 rounded-lg bg-primary text-on-primary font-semibold hover:opacity-90 transition-opacity text-lg">
            Back to Home <ChevronRight className="w-6 h-6" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      {/* Industrial backdrop — shared with every public page */}
      <IndustrialBackdrop accentLine />
      <nav className="sticky top-0 z-50 bg-surface/80 backdrop-blur-lg border-b border-outline-variant">
        <div className="max-w-6xl mx-auto px-lg py-md flex items-center justify-between">
          <Link to="/" className="flex items-center gap-sm">
            <img src="/favicon.png" alt="ErgoVigilance" className="w-10 h-10 rounded-lg" />
            <span className="text-title-lg font-bold text-on-surface">ErgoVigilance</span>
          </Link>
          <Link to="/login" className="flex items-center gap-sm px-md py-sm rounded-lg bg-surface-container-high text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors text-body-sm">
            Log In
          </Link>
        </div>
      </nav>

      <div className="max-w-2xl mx-auto px-lg py-12">
        <div className="mb-8">
          <Link to="/" className="inline-flex items-center gap-2 text-on-surface-variant hover:text-on-surface transition-colors mb-4">
            <ChevronRight className="w-4 h-4 rotate-180" />
            Back to Home
          </Link>
          <h1 className="text-3xl font-bold text-on-surface mb-2">Request a Pilot</h1>
          <p className="text-on-surface-variant">
            Fill out the form below to request a free 2-week pilot of ErgoVigilance for your team.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 text-red-800 border border-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-6">
          <div>
            <label className="block text-body-sm font-medium text-on-surface mb-2">Company Name</label>
            <input
              type="text"
              name="companyName"
              value={formData.companyName}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-lg bg-surface-container-high border border-outline-variant text-on-surface focus:outline-none focus:border-primary transition-colors"
              placeholder="Acme Corporation"
            />
          </div>
          <div>
            <label className="block text-body-sm font-medium text-on-surface mb-2">Contact Name</label>
            <input
              type="text"
              name="contactName"
              value={formData.contactName}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-lg bg-surface-container-high border border-outline-variant text-on-surface focus:outline-none focus:border-primary transition-colors"
              placeholder="Jane Smith"
            />
          </div>
          <div>
            <label className="block text-body-sm font-medium text-on-surface mb-2">Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-lg bg-surface-container-high border border-outline-variant text-on-surface focus:outline-none focus:border-primary transition-colors"
              placeholder="jane@acme.com"
            />
          </div>
          <div>
            <label className="block text-body-sm font-medium text-on-surface mb-2">Role</label>
            <select
              name="role"
              value={formData.role}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 rounded-lg bg-surface-container-high border border-outline-variant text-on-surface focus:outline-none focus:border-primary transition-colors"
            >
              <option value="EHS Manager">EHS Manager</option>
              <option value="Plant Manager">Plant Manager</option>
              <option value="Safety Coordinator">Safety Coordinator</option>
              <option value="Other">Other</option>
            </select>
          </div>
          <div>
            <label className="block text-body-sm font-medium text-on-surface mb-2">Number of Stations/Workers</label>
            <input
              type="text"
              name="numStations"
              value={formData.numStations}
              onChange={handleChange}
              className="w-full px-4 py-3 rounded-lg bg-surface-container-high border border-outline-variant text-on-surface focus:outline-none focus:border-primary transition-colors"
              placeholder="e.g., 10 stations"
            />
          </div>
          <div>
            <label className="block text-body-sm font-medium text-on-surface mb-2">Message (Optional)</label>
            <textarea
              name="message"
              value={formData.message}
              onChange={handleChange}
              rows={4}
              className="w-full px-4 py-3 rounded-lg bg-surface-container-high border border-outline-variant text-on-surface focus:outline-none focus:border-primary transition-colors resize-none"
              placeholder="Tell us about your needs, timeline, etc."
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-on-primary font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {loading ? 'Submitting...' : 'Submit Request'}
              {!loading && <ChevronRight className="w-4 h-4" />}
            </button>
          </div>
        </form>

        <p className="mt-12 text-center text-[11px] text-on-surface-variant/80">
          Heuristic risk thresholds · Not a medical device · Video never leaves your building
        </p>
      </div>
    </div>
  );
}
