import { createContext, useContext, useState } from 'react';
import translations from '../i18n/translations';

const LangContext = createContext(null);

export function LangProvider({ children }) {
  const [lang, setLang] = useState('en');
  const isRtl = lang === 'ar';
  const T = translations[lang];
  const toggle = () => setLang((l) => (l === 'en' ? 'ar' : 'en'));

  return (
    <LangContext.Provider value={{ lang, T, isRtl, toggle }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  return useContext(LangContext);
}
