import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ThemeProvider } from './hooks/useTheme';
import { ToastProvider } from './hooks/useToast';
import { AuthProvider } from './auth/AuthContext';
import { SettingsProvider } from './hooks/useSettings';
import { AlertsProvider } from './hooks/useAlertsContext';
import { I18nProvider } from './i18n';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <I18nProvider>
          <AuthProvider>
            <SettingsProvider>
              <AlertsProvider>
                <App />
              </AlertsProvider>
            </SettingsProvider>
          </AuthProvider>
        </I18nProvider>
      </ToastProvider>
    </ThemeProvider>
  </StrictMode>,
);
