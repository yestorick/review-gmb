import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { Toaster, toast } from 'sonner';
import { api } from './api';
import { Sidebar } from './components/Sidebar';
import Auth from './pages/Auth';
import Reviews from './pages/Reviews';
import AddReview from './pages/AddReview';
import Categories from './pages/Categories';
import Settings from './pages/Settings';
import ChangePassword from './pages/ChangePassword';
import PublicReview from './pages/PublicReview';
import './styles.css';

function Shell({ setUser, children }) {
  const [open, setOpen] = useState(false);
  const logout = async () => {
    await api.post('/auth/logout');
    setUser(false);
    toast.success('Signed out');
  };
  return (
    <div className="shell">
      <Sidebar open={open} close={() => setOpen(false)} onLogout={logout} />
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <main className="main">
        <div className="mobile-bar">
          <span className="sidebar-brand" style={{ border: 'none', padding: 0 }}><span className="brand-mark">R</span> ReviewBoost</span>
          <button className="icon-btn" onClick={() => setOpen(true)} data-testid="open-sidebar-button"><Menu size={22} /></button>
        </div>
        {children}
      </main>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api.get('/auth/me').then((r) => setUser(r.data)).catch(() => setUser(false)).finally(() => setChecking(false));
  }, []);

  const owner = (element) => (user ? <Shell setUser={setUser}>{element}</Shell> : <Navigate to="/" replace />);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/r/:slug" element={<PublicReview />} />
        <Route path="/" element={checking ? <div className="loading-screen">ReviewBoost</div> : user ? <Navigate to="/reviews" replace /> : <Auth setUser={setUser} />} />
        <Route path="/reviews" element={checking ? <div className="loading-screen">ReviewBoost</div> : owner(<Reviews />)} />
        <Route path="/reviews/new" element={checking ? <div className="loading-screen">ReviewBoost</div> : owner(<AddReview />)} />
        <Route path="/categories" element={checking ? <div className="loading-screen">ReviewBoost</div> : owner(<Categories />)} />
        <Route path="/settings" element={checking ? <div className="loading-screen">ReviewBoost</div> : owner(<Settings />)} />
        <Route path="/change-password" element={checking ? <div className="loading-screen">ReviewBoost</div> : owner(<ChangePassword />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster position="bottom-right" />
    </BrowserRouter>
  );
}
