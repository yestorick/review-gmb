import { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../api';

export const QrModal = ({ slug, businessName, onClose }) => {
  const [qr, setQr] = useState('');

  useEffect(() => {
    api.get(`/public/${slug}/qr`).then((r) => setQr(r.data.data_url)).catch(() => toast.error('Could not load your QR code'));
  }, [slug]);

  return (
    <div className="modal-scrim" onClick={onClose} data-testid="qr-modal">
      <div className="modal qr-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="icon-btn modal-close" onClick={onClose} data-testid="qr-modal-close"><X size={18} /></button>
        <h2>Your review QR code</h2>

        <div className="qr-frame">
          {qr ? <img src={qr} alt="Review QR code" width={168} height={168} data-testid="qr-modal-image" /> : <div className="qr-skeleton" />}
          <span className="qr-caption">{businessName || 'Scan to leave a review'}</span>
        </div>

        <a className={`btn btn-primary qr-download${qr ? '' : ' disabled'}`} href={qr || undefined} download="review-qr.png" aria-disabled={!qr} data-testid="qr-modal-download">
          <Download size={18} /> {qr ? 'Download QR' : 'Preparing…'}
        </a>
        <p className="qr-hint">Print it or show it on your phone — customers scan and post in seconds.</p>
      </div>
    </div>
  );
};
