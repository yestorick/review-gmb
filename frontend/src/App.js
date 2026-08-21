import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { Toaster, toast } from 'sonner';
import { api } from './api';
import { Sidebar } from './components/Sidebar';
import { MobileNav } from './components/MobileNav';
import { Walkthrough } from './components/Walkthrough';
import Auth from './pages/Auth';
import AuthCallback from './pages/AuthCallback';
import ResetPassword from './pages/ResetPassword';
import Reviews from './pages/Reviews';
import AddReview from './pages/AddReview';
import Categories from './pages/Categories';
import Settings from './pages/Settings';
import Profile from './pages/Profile';
import PublicReview from './pages/PublicReview';
import './styles.css';
import { BrandLockup } from './components/Logo';

function Shell({ user, setUser, children }) {
  const [open, setOpen] = useState(false);
  const logout = async () => {
    await api.post('/auth/logout');
    setUser(false);
    toast.success('Signed out');
  };
  return (
    <div className="shell">
      {user && !user.onboarding_done && <Walkthrough onDone={() => setUser({ ...user, onboarding_done: true })} />}
      <Sidebar open={open} close={() => setOpen(false)} onLogout={logout} />
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <main className="main">
        <div className="mobile-bar">
          <BrandLockup size={30} />
          <button className="icon-btn" onClick={() => setOpen(true)} data-testid="open-sidebar-button"><Menu size={22} /></button>
        </div>
        {children}
      </main>
      <MobileNav />
    </div>
  );
}

function Router() {
  const location = useLocation();
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const returningFromGoogle = location.hash?.includes('session_id=');

  useEffect(() => {
    if (window.location.hash?.includes('session_id=')) { setChecking(false); return; }
    api.get('/auth/me').then((r) => setUser(r.data)).catch(() => setUser(false)).finally(() => setChecking(false));
  }, []);

  if (returningFromGoogle) return <AuthCallback setUser={setUser} />;

  const loading = <div className="loading-screen">Review Gate GMB</div>;
  const owner = (element) => (checking ? loading : user ? <Shell user={user} setUser={setUser}>{element}</Shell> : <Navigate to="/" replace />);

  return (
    <Routes>
      <Route path="/r/:slug" element={<PublicReview />} />
      <Route path="/reset-password" element={<ResetPassword setUser={setUser} />} />
      <Route path="/" element={checking ? loading : user ? <Navigate to="/reviews" replace /> : <Auth setUser={setUser} />} />
      <Route path="/reviews" element={owner(<Reviews />)} />
      <Route path="/reviews/new" element={owner(<AddReview />)} />
      <Route path="/categories" element={owner(<Categories />)} />
      <Route path="/settings" element={owner(<Settings />)} />
      <Route path="/profile" element={owner(<Profile user={user} />)} />
      <Route path="/change-password" element={<Navigate to="/profile" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Router />
      <Toaster position="bottom-right" />
    </BrowserRouter>
  );
}
