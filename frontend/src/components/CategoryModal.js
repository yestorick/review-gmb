import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { api, errText } from '../api';

export const CategoryModal = ({ onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return setError('Please type a name first');
    setBusy(true);
    setError('');
    try {
      const r = await api.post('/categories', { name: name.trim() });
      onCreated(r.data);
      onClose();
    } catch (x) { setError(errText(x)); } finally { setBusy(false); }
  };

  return (
    <div className="modal-scrim" onClick={onClose} data-testid="category-modal">
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <button type="button" className="icon-btn modal-close" onClick={onClose} data-testid="category-modal-close"><X size={18} /></button>
        <h2>Add a category</h2>
        <p>A category is just a simple group, like "haircut", "home delivery" or "first visit".</p>
        <div className="field" style={{ marginTop: 18 }}>
          <label htmlFor="cat-name">Category name</label>
          <input id="cat-name" autoFocus value={name} onChange={(e) => { setName(e.target.value); setError(''); }} placeholder="e.g. haircut" data-testid="category-modal-input" />
          {error && <span className="inline-error" data-testid="category-modal-error">{error}</span>}
        </div>
        <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="text-btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" type="submit" disabled={busy} data-testid="category-modal-save"><Plus size={16} /> {busy ? 'Adding…' : 'Add category'}</button>
        </div>
      </form>
    </div>
  );
};
