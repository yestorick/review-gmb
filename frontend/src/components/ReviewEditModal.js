import { useState } from 'react';
import { Check, X } from 'lucide-react';
import { api, errText } from '../api';

export const ReviewEditModal = ({ review, onClose, onSaved }) => {
  const [text, setText] = useState(review.text);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (text.trim().length < 10) return setError('A review needs at least 10 characters');
    setBusy(true);
    setError('');
    try {
      await api.put(`/reviews/${review.id}`, { text: text.trim() });
      onSaved();
      onClose();
    } catch (x) { setError(errText(x)); } finally { setBusy(false); }
  };

  return (
    <div className="modal-scrim" onClick={onClose} data-testid="review-edit-modal">
      <form className="modal modal-wide" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <button type="button" className="icon-btn modal-close" onClick={onClose} data-testid="review-edit-modal-close"><X size={18} /></button>
        <h2>Edit this review</h2>
        <p>Change any words you like. Customers will see exactly what you save here.</p>
        <div className="field" style={{ marginTop: 16 }}>
          <label htmlFor="review-text">Review<span className="hint">{text.trim().length} characters</span></label>
          <textarea id="review-text" autoFocus rows={7} value={text} onChange={(e) => { setText(e.target.value); setError(''); }} data-testid="review-edit-modal-input" />
          {error && <span className="inline-error" data-testid="review-edit-modal-error">{error}</span>}
        </div>
        <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="text-btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" type="submit" disabled={busy} data-testid="review-edit-modal-save"><Check size={16} /> {busy ? 'Saving…' : 'Save review'}</button>
        </div>
      </form>
    </div>
  );
};
