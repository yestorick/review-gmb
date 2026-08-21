import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, Link2, QrCode, Sparkles } from 'lucide-react';
import { api } from '../api';

const steps = [
  { icon: Link2, title: 'Step 1 — Add your Google link', body: 'Open My Business and paste your Google review link. That is the only setup we need from you.' },
  { icon: Sparkles, title: 'Step 2 — Let us write your reviews', body: 'Tap ADD NEW, fill a short form (keywords, tone, how many) and we write ready-to-post reviews for you.' },
  { icon: QrCode, title: 'Step 3 — Share your QR code', body: 'Print the QR or send the link. Your customer taps a review, it is copied, and they post it on Google.' },
];
export const Walkthrough = ({ onDone }) => {
  const nav = useNavigate();
  const [i, setI] = useState(0);
  const { icon: Icon, title, body } = steps[i];

  const finish = async (goTo) => {
    await api.post('/onboarding/complete').catch(() => {});
    onDone();
    if (goTo) nav(goTo);
  };

  return (
    <div className="modal-scrim" data-testid="walkthrough">
      <div className="modal">
        <div className="dots">{steps.map((_, n) => <span key={n} className={n === i ? 'on' : ''} data-testid={`walkthrough-dot-${n}`} />)}</div>
        <div className="modal-icon"><Icon size={26} /></div>
        <h2 data-testid="walkthrough-title">{title}</h2>
        <p>{body}</p>
        <div className="modal-foot">
          <button className="text-btn" onClick={() => finish()} data-testid="walkthrough-skip">Skip</button>
          {i < steps.length - 1 ? (
            <button className="btn btn-primary" onClick={() => setI(i + 1)} data-testid="walkthrough-next">Next <ArrowRight size={16} /></button>
          ) : (
            <button className="btn btn-primary" onClick={() => finish('/settings')} data-testid="walkthrough-finish"><Check size={16} /> Start setup</button>
          )}
        </div>
      </div>
    </div>
  );
};
