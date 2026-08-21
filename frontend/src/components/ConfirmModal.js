import { AlertTriangle } from 'lucide-react';

export const ConfirmModal = ({ title, body, confirmLabel = 'Delete', onConfirm, onClose }) => (
  <div className="modal-scrim" onClick={onClose} data-testid="confirm-modal">
    <div className="modal" onClick={(e) => e.stopPropagation()}>
      <div className="modal-icon danger"><AlertTriangle size={24} /></div>
      <h2 data-testid="confirm-modal-title">{title}</h2>
      <p>{body}</p>
      <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
        <button className="text-btn" onClick={onClose} data-testid="confirm-modal-cancel">Cancel</button>
        <button className="btn btn-danger" onClick={() => { onConfirm(); onClose(); }} data-testid="confirm-modal-confirm">{confirmLabel}</button>
      </div>
    </div>
  </div>
);
