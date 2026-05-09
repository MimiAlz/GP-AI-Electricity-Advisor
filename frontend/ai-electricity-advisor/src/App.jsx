import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import arEG from 'antd/locale/ar_EG';
import enUS from 'antd/locale/en_US';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LangProvider, useLang } from './contexts/LangContext';

import AuthPage from './pages/AuthPage';
import AppLayout from './components/AppLayout';
import HouseManagement from './pages/HouseManagement';
// import HouseDisaggregation from './pages/HouseDisaggregation';
import HouseForecast from './pages/HouseForecast';
import NilmOverview from './pages/NilmOverview';
import ProfilePage from './pages/ProfilePage';
import AreaForecast from './pages/AreaForecast';
import BackendTest from './pages/BackendTest';

const THEME = {
  token: {
    colorPrimary: '#302b63',
    borderRadius: 8,
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
  },
};

function AppRoutes() {
  const { isAuthenticated } = useAuth();
  const { lang, isRtl } = useLang();

  const configProps = {
    locale: lang === 'ar' ? arEG : enUS,
    direction: isRtl ? 'rtl' : 'ltr',
    theme: THEME,
  };

  if (!isAuthenticated) {
    return (
      <ConfigProvider {...configProps}>
        <AuthPage />
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider {...configProps}>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Navigate to="/houses" replace />} />
            <Route path="/houses" element={<HouseManagement />} />
            <Route path="/nilm-overview" element={<NilmOverview />} />
            <Route path="/forecast" element={<HouseForecast />} />
            <Route path="/area-forecast" element={<AreaForecast />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/backend-test" element={<BackendTest />} />
            <Route path="*" element={<Navigate to="/houses" replace />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <LangProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </LangProvider>
  );
}
