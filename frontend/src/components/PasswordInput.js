import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export const PasswordInput = ({ testid, ...props }) => {
  const [show, setShow] = useState(false);
  return (
    <div className="password-wrap">
      <input type={show ? 'text' : 'password'} data-testid={testid} {...props} />
      <button type="button" className="eye-btn" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'} data-testid={`${testid}-toggle`}>
        {show ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
};
