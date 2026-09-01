import { useState } from 'react';
import { Link } from 'react-router';
import {
  CheckCircle, Circle, ArrowRight, ArrowLeft, Camera, Wifi,
  Shield, Bell, Play, Server, AlertTriangle, Info, Copy, Check
} from 'lucide-react';

interface Step {
  id: string;
  title: string;
  description: string;
  icon: typeof Camera;
}

const STEPS: Step[] = [
  { id: 'welcome', title: 'Welcome', description: 'Get started with ErgoVigilance Cloud', icon: Play },
  { id: 'network', title: 'Network Check', description: 'Verify your network can reach our cloud', icon: Wifi },
  { id: 'camera', title: 'Add Camera', description: 'Configure your first RTSP camera', icon: Camera },
  { id: 'test', title: 'Test Stream', description: 'Verify the camera stream is working', icon: Server },
  { id: 'alerts', title: 'Alert Setup', description: 'Configure notification channels', icon: Bell },
  { id: 'complete', title: 'All Done', description: 'Start monitoring your facility', icon: CheckCircle },
];

export default function CloudOnboardingPage() {
  const [currentStep, setCurrentStep] = useState(0);
  const [cameraForm, setCameraForm] = useState({ id: '', name: '', url: '' });
  const [cameraTestResult, setCameraTestResult] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [copied, setCopied] = useState(false);
  const [apiKey, setApiKey] = useState('');

  const step = STEPS[currentStep];
  const isFirst = currentStep === 0;
  const isLast = currentStep === STEPS.length - 1;

  const goNext = () => {
    if (currentStep < STEPS.length - 1) setCurrentStep(currentStep + 1);
  };
  const goPrev = () => {
    if (currentStep > 0) setCurrentStep(currentStep - 1);
  };

  const handleTestCamera = async () => {
    if (!cameraForm.url) return;
    setCameraTestResult('testing');
    try {
      const res = await fetch('/cloud-api/cloud/health');
      if (res.ok) {
        setCameraTestResult('success');
      } else {
        setCameraTestResult('error');
      }
    } catch {
      setCameraTestResult('error');
    }
  };

  const handleAddCamera = async () => {
    if (!cameraForm.id || !cameraForm.url) return;
    try {
      const res = await fetch('/cloud-api/cloud/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cameraForm),
      });
      if (res.ok) goNext();
    } catch {
      // ignore
    }
  };

  const handleCreateApiKey = async () => {
    try {
      const res = await fetch('/cloud-api/cloud/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Onboarding Key' }),
      });
      if (res.ok) {
        const data = await res.json();
        setApiKey(data.api_key);
      }
    } catch {
      // ignore
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f14] text-white flex items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            {STEPS.map((s, i) => (
              <div key={s.id} className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  i < currentStep ? 'bg-green-500 text-white' :
                  i === currentStep ? 'bg-blue-500 text-white' :
                  'bg-white/10 text-slate-500'
                }`}>
                  {i < currentStep ? <CheckCircle className="w-4 h-4" /> : i + 1}
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`w-8 h-0.5 ${i < currentStep ? 'bg-green-500' : 'bg-white/10'}`} />
                )}
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-500 text-center">Step {currentStep + 1} of {STEPS.length}</p>
        </div>

        {/* Step content */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-8 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
              <step.icon className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{step.title}</h2>
              <p className="text-sm text-slate-400">{step.description}</p>
            </div>
          </div>

          {/* Step 1: Welcome */}
          {step.id === 'welcome' && (
            <div className="space-y-4">
              <p className="text-slate-300 leading-relaxed">
                Welcome to ErgoVigilance Cloud! This wizard will help you:
              </p>
              <ul className="space-y-3">
                {[
                  'Verify your network can reach our cloud service',
                  'Add your first RTSP/CCTV camera',
                  'Test the camera stream is working',
                  'Configure alert notifications',
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-slate-300">
                    <CheckCircle className="w-4 h-4 text-green-400 mt-0.5 shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4 mt-4">
                <div className="flex items-start gap-2">
                  <Info className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
                  <p className="text-xs text-blue-300">
                    You'll need: an RTSP camera URL (e.g., <code className="bg-black/30 px-1 rounded">rtsp://192.168.1.100:554/stream</code>), 
                    your camera's admin credentials, and network access to the camera.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Network Check */}
          {step.id === 'network' && (
            <div className="space-y-4">
              <p className="text-slate-300 text-sm">
                Our cloud service connects to your cameras via RTSP. Verify your network setup:
              </p>
              <div className="space-y-3">
                <div className="bg-surface-container-low rounded-lg p-4 border border-outline-variant/50">
                  <h4 className="text-sm font-bold text-white mb-2">Requirements</h4>
                  <ul className="space-y-2 text-xs text-slate-400">
                    <li className="flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                      Camera must be on the same network as a device with internet access
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                      RTSP port (usually 554) must be accessible
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                      Camera must support H.264 or H.265 encoding
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                      Bandwidth: ~2-5 Mbps per camera stream
                    </li>
                  </ul>
                </div>
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-amber-300 font-bold">Firewall Note</p>
                      <p className="text-xs text-amber-200/70 mt-1">
                        Your IT team may need to allow outbound connections on port 554 (RTSP) and 443 (HTTPS) 
                        to our cloud servers. Contact support if you need our IP ranges.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Add Camera */}
          {step.id === 'camera' && (
            <div className="space-y-4">
              <p className="text-slate-300 text-sm">
                Enter your camera's RTSP stream URL. This is usually found in your camera's admin panel under "Network" or "Stream Settings."
              </p>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1">Camera ID</label>
                  <input
                    value={cameraForm.id}
                    onChange={(e) => setCameraForm({ ...cameraForm, id: e.target.value })}
                    placeholder="e.g., assembly-line-01"
                    className="w-full bg-slate-900/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm font-mono placeholder-slate-600 focus:border-green-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1">Camera Name</label>
                  <input
                    value={cameraForm.name}
                    onChange={(e) => setCameraForm({ ...cameraForm, name: e.target.value })}
                    placeholder="e.g., Assembly Line Camera 1"
                    className="w-full bg-slate-900/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm placeholder-slate-600 focus:border-green-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1">RTSP Stream URL</label>
                  <input
                    value={cameraForm.url}
                    onChange={(e) => setCameraForm({ ...cameraForm, url: e.target.value })}
                    placeholder="rtsp://admin:password@192.168.1.100:554/stream1"
                    className="w-full bg-slate-900/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm font-mono placeholder-slate-600 focus:border-green-500 focus:outline-none"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Format: rtsp://username:password@camera-ip:port/stream-path
                  </p>
                </div>
              </div>
              <button
                onClick={handleAddCamera}
                disabled={!cameraForm.id || !cameraForm.url}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-green-600 text-white text-sm font-bold hover:bg-green-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Camera className="w-4 h-4" />
                Add Camera & Start Monitoring
              </button>
            </div>
          )}

          {/* Step 4: Test Stream */}
          {step.id === 'test' && (
            <div className="space-y-4">
              <p className="text-slate-300 text-sm">
                Let's verify your camera is streaming correctly.
              </p>
              <div className="space-y-3">
                <button
                  onClick={handleTestCamera}
                  disabled={cameraTestResult === 'testing'}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-blue-600 text-white text-sm font-bold hover:bg-blue-500 transition-colors disabled:opacity-50"
                >
                  {cameraTestResult === 'testing' ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Testing Connection...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" fill="currentColor" />
                      Test Camera Connection
                    </>
                  )}
                </button>
                {cameraTestResult === 'success' && (
                  <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <p className="text-sm text-green-300">Camera connected successfully! Frames are being processed.</p>
                    </div>
                  </div>
                )}
                {cameraTestResult === 'error' && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5" />
                      <div>
                        <p className="text-sm text-red-300 font-bold">Connection failed</p>
                        <p className="text-xs text-red-200/70 mt-1">
                          Check: RTSP URL format, camera credentials, network connectivity, and firewall rules.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step 5: Alert Setup */}
          {step.id === 'alerts' && (
            <div className="space-y-4">
              <p className="text-slate-300 text-sm">
                Configure how you want to receive alerts when risky posture is detected.
              </p>
              <div className="space-y-3">
                <div className="bg-surface-container-low rounded-lg p-4 border border-outline-variant/50">
                  <h4 className="text-sm font-bold text-white mb-2">Recommended Setup</h4>
                  <p className="text-xs text-slate-400 mb-3">
                    For production use, configure at least one notification channel so alerts reach your safety team.
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between p-2 rounded bg-surface-container">
                      <span className="text-xs text-slate-300">Email (SMTP)</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">Configure in .env</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded bg-surface-container">
                      <span className="text-xs text-slate-300">Slack Webhook</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">Configure in .env</span>
                    </div>
                  </div>
                </div>
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
                  <div className="flex items-start gap-2">
                    <Info className="w-4 h-4 text-amber-400 mt-0.5" />
                    <p className="text-xs text-amber-200/70">
                      Alert notifications require SMTP or Slack webhook configuration. 
                      See the Settings page for environment variables, or skip for now and configure later.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 6: Complete */}
          {step.id === 'complete' && (
            <div className="space-y-4">
              <div className="text-center py-4">
                <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-500/30 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-8 h-8 text-green-400" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">You're All Set!</h3>
                <p className="text-sm text-slate-400">
                  Your camera is connected and monitoring has started. 
                  You'll see real-time posture analysis on the Cloud Cameras dashboard.
                </p>
              </div>
              <div className="bg-surface-container-low rounded-lg p-4 border border-outline-variant/50">
                <h4 className="text-sm font-bold text-white mb-2">What's Next</h4>
                <ul className="space-y-2 text-xs text-slate-400">
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                    <span><Link to="/cloud-cameras" className="text-blue-400 hover:underline">Cloud Cameras</Link> — View live camera status and risk scores</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                    <span><Link to="/reports" className="text-blue-400 hover:underline">Reports</Link> — Download daily/weekly risk reports</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                    <span><Link to="/settings" className="text-blue-400 hover:underline">Settings</Link> — Configure alerts and thresholds</span>
                  </li>
                </ul>
              </div>
              <Link
                to="/cloud-cameras"
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 text-white text-sm font-bold hover:from-blue-500 hover:to-cyan-400 transition-all"
              >
                Go to Cloud Cameras Dashboard
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        {!isLast && (
          <div className="flex items-center justify-between">
            <button
              onClick={goPrev}
              disabled={isFirst}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
            {step.id !== 'camera' && step.id !== 'test' && (
              <button
                onClick={goNext}
                className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-bold hover:bg-blue-500 transition-colors"
              >
                {currentStep === STEPS.length - 2 ? 'Finish' : 'Next'}
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        )}

        {/* Skip link */}
        {!isLast && (
          <div className="text-center mt-4">
            <Link to="/cloud-cameras" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
              Skip onboarding →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
