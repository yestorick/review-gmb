import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronLeft, ChevronRight, Copy, MessageSquarePlus, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';

const shortDate = (iso) => new Date(iso).toLocaleDateString('en-GB').replaceAll('/', '-');
const PAGE_SIZES = [10, 25, 50];

export default function Reviews() {
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [selected, setSelected] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const load = async () => {
    try {
      setData((await api.get('/reviews')).data);
      setSelected([]);
    } catch (x) { toast.error(errText(x)); }
  };
  useEffect(() => { load(); }, []);

  const reviews = data?.reviews || [];
  const pageCount = Math.max(1, Math.ceil(reviews.length / pageSize));
  const current = useMemo(() => reviews.slice((page - 1) * pageSize, page * pageSize), [reviews, page, pageSize]);
  useEffect(() => { if (page > pageCount) setPage(1); }, [pageCount, page]);

  const goToPage = (n) => { setPage(n); setSelected([]); };

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const pageIds = current.map((r) => r.id);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.includes(id));
  const togglePage = () => setSelected((s) => (allOnPage ? s.filter((id) => !pageIds.includes(id)) : [...new Set([...s, ...pageIds])]));

  const copy = async (text, message) => {
    await navigator.clipboard.writeText(text);
    toast.success(message);
  };
  const copySelected = async () => {
    const texts = reviews.filter((r) => selected.includes(r.id)).map((r) => r.text).join('\n\n');
    await navigator.clipboard.writeText(texts);
    toast.success(`${selected.length} reviews copied`);
  };
  const deleteSelected = async () => {
    if (!window.confirm(`Delete ${selected.length} selected reviews? This cannot be undone.`)) return;
    try {
      const r = await api.post('/reviews/bulk-delete', { ids: selected });
      toast.success(`${r.data.deleted} reviews deleted`);
      load();
    } catch (x) { toast.error(errText(x)); }
  };
  const save = async (id) => {
    try {
      await api.put(`/reviews/${id}`, { text: editing.text });
      setEditing(null);
      toast.success('Review updated');
      load();
    } catch (x) { toast.error(errText(x)); }
  };
  const remove = async (id) => {
    if (!window.confirm('Delete this review? This cannot be undone.')) return;
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
      <div className="page-head">
        <div>
          <h1 className="page-title" data-testid="reviews-heading">Reviews List ({data?.total ?? 0})</h1>
          <p className="page-help">Copy any review for a customer, or share your link and let them pick one.</p>
        </div>
        <Link className="btn btn-primary" to="/reviews/new" data-testid="add-new-button"><Plus size={18} /> ADD NEW</Link>
      </div>

      {b && (
        <div className="link-banner">
          <span>Your review link:</span>
          <a href={b.public_url} target="_blank" rel="noreferrer" data-testid="public-link">{b.public_url}</a>
          <button className="icon-btn" onClick={() => copy(b.public_url, 'Link copied')} data-testid="copy-link-button"><Copy size={18} /></button>
          {b.is_active
            ? <span className="status-pill on" data-testid="link-status">ACTIVE</span>
            : <Link to="/settings" className="status-pill off" data-testid="link-status">ADD GOOGLE LINK</Link>}
        </div>
      )}

      <div className="stat-row">
        <div className="stat"><b data-testid="stat-total">{data?.total ?? 0}</b><span>Total reviews</span></div>
        <div className="stat"><b data-testid="stat-available">{data?.available ?? 0}</b><span>Available</span></div>
        <div className="stat"><b data-testid="stat-used">{data?.used ?? 0}</b><span>Used by customers</span></div>
      </div>

      {selected.length > 0 && (
        <div className="bulk-bar" data-testid="bulk-bar">
          <strong data-testid="bulk-count">{selected.length} selected</strong>
          <button className="btn btn-ghost" onClick={copySelected} data-testid="bulk-copy-button"><Copy size={16} /> Copy all</button>
          <button className="btn btn-ghost danger" onClick={deleteSelected} data-testid="bulk-delete-button"><Trash2 size={16} /> Delete all</button>
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
                      <td><input type="checkbox" checked={selected.includes(r.id)} onChange={() => toggle(r.id)} aria-label="Select review" data-testid={`review-checkbox-${i}`} /></td>
                      <td>{(page - 1) * pageSize + i + 1}</td>
                      <td><span className="chip">{r.category}</span></td>
                      <td className="review-text">
                        {editing?.id === r.id ? (
                          <div className="field">
                            <textarea data-testid={`review-edit-input-${i}`} value={editing.text} onChange={(e) => setEditing({ ...editing, text: e.target.value })} />
                            <div>
                              <button className="btn btn-primary" onClick={() => save(r.id)} data-testid={`review-save-${i}`}><Check size={16} /> Save</button>
                              <button className="text-btn" style={{ marginLeft: 12 }} onClick={() => setEditing(null)}>Cancel</button>
                            </div>
                          </div>
                        ) : r.text}
                      </td>
                      <td><span className={`badge ${r.status}`} data-testid={`review-status-${i}`}>{r.status === 'used' ? 'USED' : 'AVAILABLE'}</span></td>
                      <td>{shortDate(r.created_at)}</td>
                      <td>
                        <div className="row-actions">
                          <button className="icon-btn" title="Write a new one" disabled={busyId === r.id} onClick={() => regenerate(r.id)} data-testid={`review-regenerate-${i}`}>
                            <RefreshCw size={17} className={busyId === r.id ? 'spin' : ''} />
                          </button>
                          <button className="icon-btn" title="Copy review" onClick={() => copy(r.text, 'Review copied')} data-testid={`review-copy-${i}`}><Copy size={17} /></button>
                          <button className="icon-btn" title="Edit" onClick={() => setEditing({ id: r.id, text: r.text })} data-testid={`review-edit-${i}`}>
                            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
                          </button>
                          <button className="icon-btn danger" title="Delete" onClick={() => remove(r.id)} data-testid={`review-delete-${i}`}><Trash2 size={17} /></button>
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
            <strong>No reviews yet</strong>
            <span>Tap ADD NEW, fill a short form, and we will write your reviews for you.</span>
            <div style={{ marginTop: 18 }}><Link className="btn btn-primary" to="/reviews/new"><Plus size={18} /> ADD NEW</Link></div>
          </div>
        )}
      </div>
    </>
  );
}
