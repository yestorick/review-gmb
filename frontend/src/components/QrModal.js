import { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../api';

export const QrModal = ({ slug, publicUrl, businessName, onClose }) => {
  const [qr, setQr] = useState('');

  useEffect(() => {
    api.get(`/public/${slug}/qr`).then((r) => setQr(r.data.data_url)).catch(() => toast.error('Could not load your QR code'));
  }, [slug]);

  return (
    <div className="modal-scrim" onClick={onClose} data-testid="qr-modal">
      <div className="modal qr-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="icon-btn modal-close" onClick={onClose} data-testid="qr-modal-close"><X size={18} /></button>
        <h2>Your review QR code</h2>
        <p>Print it, stick it on the counter or show it on your phone. Customers scan and post in seconds.</p>

        <div className="qr-frame">
          {qr ? <img src={qr} alt="Review QR code" width={220} height={220} data-testid="qr-modal-image" /> : <div className="qr-skeleton" />}
          <span className="qr-caption">{businessName || 'Scan to leave a review'}</span>
        </div>

        <p className="qr-url" data-testid="qr-modal-url">{publicUrl.replace(/^https?:\/\//, '')}</p>

        <div className="modal-foot" style={{ justifyContent: 'center' }}>
          <a className="btn btn-primary" href={qr || '#'} download="review-qr.png" data-testid="qr-modal-download"><Download size={18} /> Download QR</a>
        </div>
      </div>
    </div>
  );
};
