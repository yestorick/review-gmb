import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Copy, ExternalLink, Filter, Link2, MessageSquarePlus, Pencil, Plus, QrCode, RefreshCw, Share2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';
import { ReviewEditModal } from '../components/ReviewEditModal';
import { ConfirmModal } from '../components/ConfirmModal';

const shortDate = (iso) => new Date(iso).toLocaleDateString('en-GB').replaceAll('/', '-');
const splitLink = (url) => {
  const bare = url.replace(/^https?:\/\//, '');
  const at = bare.indexOf('/r/');
  return { host: at > -1 ? bare.slice(0, at) : bare, path: at > -1 ? bare.slice(at) : '' };
};
const PAGE_SIZES = [10, 25, 50];

export default function Reviews() {
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [selected, setSelected] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [category, setCategory] = useState('all');
  const [confirming, setConfirming] = useState(null);

  const load = async () => {
    try {
      setData((await api.get('/reviews')).data);
      setSelected([]);
    } catch (x) { toast.error(errText(x)); }
  };
  useEffect(() => { load(); }, []);

  const allReviews = data?.reviews || [];
  const categories = [...new Set(allReviews.map((r) => r.category))];
  const reviews = category === 'all' ? allReviews : allReviews.filter((r) => r.category === category);
  const pageCount = Math.max(1, Math.ceil(reviews.length / pageSize));
  const current = useMemo(() => reviews.slice((page - 1) * pageSize, page * pageSize), [reviews, page, pageSize]);
  useEffect(() => { if (page > pageCount) setPage(1); }, [pageCount, page]);

  const goToPage = (n) => { setPage(n); setSelected([]); };

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const pageIds = current.map((r) => r.id);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.includes(id));
  const togglePage = () => setSelected((s) => (allOnPage ? s.filter((id) => !pageIds.includes(id)) : [...new Set([...s, ...pageIds])]));

  const copy = async (text, message) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(message);
    } catch {
      toast.message('Copy it from here', { description: text });
    }
  };
  const share = async (url) => {
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Leave us a review', text: 'Pick a ready-made review and post it in one tap', url });
        return;
      } catch { /* cancelled */ }
    }
    copy(url, 'Link copied — paste it anywhere');
  };
  const copySelected = async () => {
    const texts = reviews.filter((r) => selected.includes(r.id)).map((r) => r.text).join('\n\n');
    try {
      await navigator.clipboard.writeText(texts);
      toast.success(`${selected.length} reviews copied`);
    } catch {
      toast.message('Copy them from here', { description: texts.slice(0, 400) });
    }
  };
  const deleteSelected = async () => {
    try {
      const r = await api.post('/reviews/bulk-delete', { ids: selected });
      toast.success(`${r.data.deleted} reviews deleted`);
      load();
    } catch (x) { toast.error(errText(x)); }
  };
  const remove = async (id) => {
    try {
      await api.delete(`/reviews/${id}`);
      toast.success('Review deleted');
      load();
    } catch (x) { toast.error(errText(x)); }
  };
  const regenerate = async (id) => {
    setBusyId(id);
    try {
      await api.post(`/reviews/${id}/regenerate`);
      toast.success('New review written');
      load();
    } catch (x) { toast.error(errText(x)); } finally { setBusyId(null); }
  };

  const b = data?.business;

  return (
    <>
      {confirming && (
        <ConfirmModal title={confirming.kind === 'bulk' ? `Delete ${selected.length} reviews?` : 'Delete this review?'}
          body="This cannot be undone. You can always generate fresh reviews afterwards."
          onConfirm={confirming.kind === 'bulk' ? deleteSelected : () => remove(confirming.id)} onClose={() => setConfirming(null)} />
      )}
      {editing && <ReviewEditModal review={editing} onClose={() => setEditing(null)} onSaved={() => { toast.success('Review updated'); load(); }} />}
      <section className="hero-card">
        <div className="hero-top">
          <div>
            <h1 className="hero-title" data-testid="reviews-heading">
              Reviews <span className="count-badge">{category === 'all' ? (data?.total ?? 0) : reviews.length}</span>
            </h1>
            <p className="hero-sub">Share your link or QR — customers tap a review and post it on Google.</p>
          </div>
          <Link className="btn btn-primary" to="/reviews/new" data-testid="add-new-button"><Plus size={18} /> Add new</Link>
        </div>

        {b && (
          <div className="share-box">
            <div className="share-head">
              <span className="share-label"><Link2 size={15} /> Your review link</span>
              {b.is_active
                ? <span className="dot-pill on" data-testid="link-status"><i />Active</span>
                : <Link to="/settings" className="dot-pill off" data-testid="link-status"><i />Add Google link</Link>}
            </div>
            <a className="link-chip" href={b.public_url} target="_blank" rel="noreferrer" data-testid="public-link">
              <span className="link-host">{splitLink(b.public_url).host}</span>
              <span className="link-path">{splitLink(b.public_url).path}</span>
              <ExternalLink size={15} />
            </a>
            <div className="share-actions">
              <button className="chip-btn" onClick={() => copy(b.public_url, 'Link copied')} data-testid="copy-link-button"><Copy size={16} /> Copy link</button>
              <button className="chip-btn" onClick={() => share(b.public_url)} data-testid="share-link-button"><Share2 size={16} /> Share</button>
              <Link className="chip-btn" to="/settings" data-testid="qr-link-button"><QrCode size={16} /> QR code</Link>
            </div>
          </div>
        )}

        <div className="metric-row">
          <div className="metric"><b data-testid="stat-total">{data?.total ?? 0}</b><span>Total</span></div>
          <div className="metric ok"><b data-testid="stat-available">{data?.available ?? 0}</b><span>Ready to use</span></div>
          <div className="metric used"><b data-testid="stat-used">{data?.used ?? 0}</b><span>Posted</span></div>
        </div>
      </section>

      <div className="filter-row">
        <label className="filter-label"><Filter size={16} /> Show category</label>
        <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); setSelected([]); }} data-testid="category-filter-select">
          <option value="all">{`All categories (${allReviews.length})`}</option>
          {categories.map((c) => <option key={c} value={c}>{`${c} (${allReviews.filter((r) => r.category === c).length})`}</option>)}
        </select>
        {category !== 'all' && <button className="text-btn" onClick={() => { setCategory('all'); setPage(1); }} data-testid="clear-filter-button">Show all</button>}
      </div>

      {selected.length > 0 && (
        <div className="bulk-bar" data-testid="bulk-bar">
          <strong data-testid="bulk-count">{selected.length} selected</strong>
          <button className="btn btn-ghost" onClick={copySelected} data-testid="bulk-copy-button"><Copy size={16} /> Copy all</button>
          <button className="btn btn-ghost danger" onClick={() => setConfirming({ kind: 'bulk' })} data-testid="bulk-delete-button"><Trash2 size={16} /> Delete all</button>
          <button className="text-btn" onClick={() => setSelected([])} data-testid="bulk-clear-button">Clear</button>
        </div>
      )}

      <div className="card">
        {reviews.length ? (
          <>
            <div className="table-wrap">
              <table data-testid="reviews-table">
                <thead>
                  <tr>
                    <th><input type="checkbox" checked={allOnPage} onChange={togglePage} aria-label="Select all on this page" data-testid="select-all-checkbox" /></th>
                    <th>Sr. No.</th><th>Category</th><th>Review</th><th>Status</th><th>Created</th><th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {current.map((r, i) => (
                    <tr key={r.id} data-testid={`review-row-${i}`} className={selected.includes(r.id) ? 'row-selected' : ''}>
                      <td className="cell-check"><input type="checkbox" checked={selected.includes(r.id)} onChange={() => toggle(r.id)} aria-label="Select review" data-testid={`review-checkbox-${i}`} /></td>
                      <td className="cell-sr">{(page - 1) * pageSize + i + 1}</td>
                      <td className="cell-cat"><span className="chip">{r.category}</span></td>
                      <td className="review-text">{r.text}</td>
                      <td className="cell-status"><span className={`badge ${r.status}`} data-testid={`review-status-${i}`}>{r.status === 'used' ? 'USED' : 'AVAILABLE'}</span></td>
                      <td className="cell-date">{shortDate(r.created_at)}</td>
                      <td className="cell-actions">
                        <div className="row-actions">
                          <button className="act-btn" disabled={busyId === r.id} onClick={() => regenerate(r.id)} data-testid={`review-regenerate-${i}`}>
                            <RefreshCw size={17} className={busyId === r.id ? 'spin' : ''} /> <span>Rewrite</span>
                          </button>
                          <button className="act-btn" onClick={() => copy(r.text, 'Review copied')} data-testid={`review-copy-${i}`}><Copy size={17} /> <span>Copy</span></button>
                          <button className="act-btn" onClick={() => setEditing(r)} data-testid={`review-edit-${i}`}><Pencil size={17} /> <span>Edit</span></button>
                          <button className="act-btn danger" onClick={() => setConfirming({ kind: 'one', id: r.id })} data-testid={`review-delete-${i}`}><Trash2 size={17} /> <span>Delete</span></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <label>
                Rows per page
                <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); goToPage(1); }} data-testid="page-size-select">
                  {PAGE_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <span data-testid="page-info">Page {page} of {pageCount}</span>
              <button className="icon-btn" disabled={page === 1} onClick={() => goToPage(page - 1)} data-testid="prev-page-button"><ChevronLeft size={18} /></button>
              <button className="icon-btn" disabled={page === pageCount} onClick={() => goToPage(page + 1)} data-testid="next-page-button"><ChevronRight size={18} /></button>
            </div>
          </>
        ) : (
          <div className="empty" data-testid="reviews-empty">
            <MessageSquarePlus size={30} />
            <strong>{category === 'all' ? 'No reviews yet' : `No reviews in "${category}"`}</strong>
            <span>{category === 'all' ? 'Tap ADD NEW, fill a short form, and we will write your reviews for you.' : 'Nothing in this group yet. Tap "Show all" above, or add new reviews for this group.'}</span>
            <div style={{ marginTop: 18 }}><Link className="btn btn-primary" to="/reviews/new"><Plus size={18} /> ADD NEW</Link></div>
          </div>
        )}
      </div>
    </>
  );
}
