import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ThemeProvider } from './hooks/useTheme';
import { ToastProvider } from './hooks/useToast';
import { DemoProvider } from './demo/DemoProvider';
import { AuthProvider } from './auth/AuthContext';
import { SettingsProvider } from './hooks/useSettings';
import { AlertsProvider } from './hooks/useAlertsContext';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <DemoProvider>
            <SettingsProvider>
              <AlertsProvider>
                <App />
              </AlertsProvider>
            </SettingsProvider>
          </DemoProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  </StrictMode>,
);
