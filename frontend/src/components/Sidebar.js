import { NavLink } from 'react-router-dom';
import { LayoutList, LogOut, Settings, Shapes, UserCircle, X } from 'lucide-react';
import { BrandLockup } from './Logo';

const items = [
  { to: '/reviews', label: 'Reviews', icon: LayoutList, testid: 'nav-reviews' },
  { to: '/categories', label: 'Category', icon: Shapes, testid: 'nav-categories' },
  { to: '/settings', label: 'My Business', icon: Settings, testid: 'nav-settings' },
  { to: '/profile', label: 'My Profile', icon: UserCircle, testid: 'nav-profile' },
];

export const Sidebar = ({ open, close, onLogout }) => (
  <aside className={`sidebar${open ? ' open' : ''}`} data-testid="sidebar">
    <div className="sidebar-brand">
      <BrandLockup />
      <button className="icon-btn sidebar-close" style={{ marginLeft: 'auto' }} onClick={close} data-testid="close-sidebar-button">
        <X size={18} />
      </button>
    </div>
    <nav>
      {items.map(({ to, label, icon: Icon, testid }) => (
        <NavLink key={to} to={to} onClick={close} data-testid={testid} className={({ isActive }) => `side-link${isActive ? ' active' : ''}`}>
          <Icon size={18} /> {label}
        </NavLink>
      ))}
    </nav>
    <div className="sidebar-foot">
      <button className="side-link" onClick={onLogout} data-testid="logout-button">
        <LogOut size={18} /> Logout
      </button>
    </div>
  </aside>
);
