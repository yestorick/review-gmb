export const Logo = ({ size = 34 }) => (
  <img src="/logo.png" alt="Review Gate GMB" width={size} height={size} className="brand-logo" data-testid="brand-logo" />
);

export const BrandLockup = ({ size = 34 }) => (
  <span className="brand-lockup">
    <Logo size={size} /> <span>Review Gate <em>GMB</em></span>
  </span>
);
