import { NavLink } from 'react-router-dom';
import { LayoutList, Plus, Settings, Shapes } from 'lucide-react';

const items = [
  { to: '/reviews', label: 'Reviews', icon: LayoutList, testid: 'tab-reviews' },
  { to: '/reviews/new', label: 'Add New', icon: Plus, testid: 'tab-add', primary: true },
  { to: '/categories', label: 'Category', icon: Shapes, testid: 'tab-categories' },
  { to: '/settings', label: 'Business', icon: Settings, testid: 'tab-settings' },
];

export const MobileNav = () => (
  <nav className="bottom-nav" data-testid="bottom-nav">
    {items.map(({ to, label, icon: Icon, testid, primary }) => (
      <NavLink key={to} to={to} end data-testid={testid} className={({ isActive }) => `bottom-link${isActive ? ' active' : ''}${primary ? ' primary' : ''}`}>
        <Icon size={primary ? 22 : 20} />
        <span>{label}</span>
      </NavLink>
    ))}
  </nav>
);
