import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, ArrowLeftRight, Check, ChevronRight, CircleDollarSign, Clock3, FileCheck2, FileSearch, Files, LoaderCircle, Menu, RefreshCw, Search, ShieldCheck, UploadCloud, X } from "lucide-react";
import { api, DocumentDetail, DocumentSummary, Status } from "./api";

const statusLabel: Record<Status, string> = { queued: "Queued", processing: "Processing", completed: "Ready", needs_review: "Needs review", failed: "Failed" };
const editableFields = ["invoice_number", "invoice_date", "supplier_name", "customer_name", "subtotal", "tax", "total", "currency"];

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function StatusPill({ status }: {status: Status}) {
  return <span className={`status status-${status}`}>{status === "processing" && <LoaderCircle size={12} className="spin" />}{statusLabel[status]}</span>;
}

function App() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [selected, setSelected] = useState<DocumentDetail | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<Awaited<ReturnType<typeof api.compare>> | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mobileMenu, setMobileMenu] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const response = await api.list(query, reviewOnly);
      setDocuments(response.items); setTotal(response.total); setError("");
    } catch (err) { setError((err as Error).message); }
  }, [query, reviewOnly]);

  useEffect(() => { const handle = setTimeout(load, 250); return () => clearTimeout(handle); }, [load]);
  useEffect(() => {
    if (!documents.some((d) => d.status === "queued" || d.status === "processing")) return;
    const handle = setInterval(load, 3500); return () => clearInterval(handle);
  }, [documents, load]);

  const stats = useMemo(() => ({
    ready: documents.filter((d) => d.status === "completed").length,
    review: documents.filter((d) => d.needs_review).length,
    active: documents.filter((d) => ["queued", "processing"].includes(d.status)).length,
  }), [documents]);

  async function handleFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (!files.length) return;
    setUploading(true); setError(""); setNotice("");
    try {
      const response = await api.upload(files);
      setNotice(`${response.accepted.length} document${response.accepted.length === 1 ? "" : "s"} added to processing queue${response.rejected.length ? `; ${response.rejected.length} rejected` : ""}.`);
      if (response.rejected.length) setError(response.rejected.map((item) => `${item.filename}: ${item.reason}`).join(" · "));
      await load();
    } catch (err) { setError((err as Error).message); }
    finally { setUploading(false); }
  }

  async function openDocument(id: string) {
    try { setSelected(await api.get(id)); setError(""); } catch (err) { setError((err as Error).message); }
  }

  function toggleCompare(id: string) {
    setCompareResult(null);
    setCompareIds((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length < 2 ? [...current, id] : [current[1], id]);
  }

  async function runCompare() {
    if (compareIds.length !== 2) return;
    try { setCompareResult(await api.compare(compareIds[0], compareIds[1])); } catch (err) { setError((err as Error).message); }
  }

  return <div className="app-shell">
    <aside className={mobileMenu ? "sidebar open" : "sidebar"}>
      <div className="brand"><div className="brand-mark"><FileSearch size={22}/></div><div><strong>LedgerLens</strong><span>Document intelligence</span></div></div>
      <nav>
        <button className="nav-item active"><Files size={18}/>Documents<span>{total}</span></button>
        <button className="nav-item" onClick={() => setReviewOnly(true)}><ShieldCheck size={18}/>Review queue<span>{stats.review}</span></button>
        <button className="nav-item" onClick={() => {setReviewOnly(false); setQuery(""); inputRef.current?.click();}}><UploadCloud size={18}/>New upload</button>
      </nav>
      <div className="sidebar-foot"><span className="health-dot"/>Processing services online<div>OCR · Extraction · Validation</div></div>
    </aside>

    <main>
      <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileMenu(!mobileMenu)}><Menu size={20}/></button><div><p>Operations workspace</p><h1>Document intelligence</h1></div><div className="top-actions"><button className="ghost-button" onClick={load}><RefreshCw size={15}/>Refresh</button><button className="primary-button" onClick={() => inputRef.current?.click()}><UploadCloud size={16}/>Upload documents</button></div></header>

      <section className="content">
        <div className="hero-row"><div><span className="eyebrow">FINANCIAL OPERATIONS</span><h2>Turn every document into verified data.</h2><p>Extract, validate and cross-check invoices without losing the source evidence.</p></div><div className="stats-strip"><div><Files/><strong>{total}</strong><span>Total</span></div><div><FileCheck2/><strong>{stats.ready}</strong><span>Verified</span></div><div><AlertCircle/><strong>{stats.review}</strong><span>Review</span></div><div><Clock3/><strong>{stats.active}</strong><span>Active</span></div></div></div>

        {(error || notice) && <div className={error ? "toast error" : "toast success"}>{error ? <AlertCircle size={17}/> : <Check size={17}/>}<span>{error || notice}</span><button onClick={() => {setError(""); setNotice("");}}><X size={15}/></button></div>}

        <div className={`dropzone ${dragging ? "dragging" : ""}`} onDragOver={(e) => {e.preventDefault(); setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={(e) => {e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files);}}>
          <input ref={inputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,.xlsx,.xls,.csv" onChange={(e) => e.target.files && handleFiles(e.target.files)} hidden/>
          <div className="upload-icon">{uploading ? <LoaderCircle className="spin"/> : <UploadCloud/>}</div><div><strong>{uploading ? "Uploading documents…" : "Drop financial documents here"}</strong><span>PDF, image, Excel or CSV · multiple files supported · up to 100 MB each</span></div><button className="browse-button" disabled={uploading} onClick={() => inputRef.current?.click()}>Browse files</button>
        </div>

        <div className="table-card">
          <div className="table-tools"><div><h3>Document register</h3><span>{total} documents in this workspace</span></div><div className="filters"><label className="search-box"><Search size={16}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search invoice, supplier, text…"/></label><button className={reviewOnly ? "filter active" : "filter"} onClick={() => setReviewOnly(!reviewOnly)}>Needs review</button></div></div>
          <div className="table-wrap"><table><thead><tr><th className="check-col"></th><th>Document</th><th>Received</th><th>Pages</th><th>Status</th><th>Progress</th><th></th></tr></thead><tbody>
            {documents.map((doc) => <tr key={doc.id}>
              <td><button aria-label="Select for comparison" className={compareIds.includes(doc.id) ? "compare-check checked" : "compare-check"} onClick={() => toggleCompare(doc.id)}>{compareIds.includes(doc.id) && <Check size={12}/>}</button></td>
              <td><button className="doc-name" onClick={() => openDocument(doc.id)}><span className={`file-icon ${doc.extension.slice(1)}`}>{doc.extension.slice(1).toUpperCase()}</span><span><strong>{doc.original_name}</strong><small>{formatBytes(doc.size_bytes)}</small></span></button></td>
              <td>{new Date(doc.created_at).toLocaleDateString(undefined, {month: "short", day: "numeric", year: "numeric"})}</td><td>{doc.page_count ?? "—"}</td><td><StatusPill status={doc.status}/></td>
              <td><div className="progress-cell"><span><i style={{width: `${doc.progress}%`}}/></span><small>{doc.progress}%</small></div></td><td><button className="row-open" onClick={() => openDocument(doc.id)}><ChevronRight size={18}/></button></td>
            </tr>)}
            {!documents.length && <tr><td colSpan={7}><div className="empty"><FileSearch/><strong>No documents found</strong><span>Upload a document or change your search filters.</span></div></td></tr>}
          </tbody></table></div>
        </div>
      </section>
    </main>

    {compareIds.length > 0 && <div className="compare-bar"><ArrowLeftRight size={18}/><span>{compareIds.length}/2 documents selected</span><button disabled={compareIds.length !== 2} onClick={runCompare}>Compare fields</button><button className="icon-button" onClick={() => {setCompareIds([]); setCompareResult(null);}}><X size={17}/></button></div>}
    {selected && <ReviewPanel document={selected} onClose={() => setSelected(null)} onUpdated={(doc) => {setSelected(doc); load();}}/>}
    {compareResult && <ComparePanel result={compareResult} onClose={() => setCompareResult(null)}/>} 
  </div>;
}

function ReviewPanel({document, onClose, onUpdated}: {document: DocumentDetail; onClose: () => void; onUpdated: (doc: DocumentDetail) => void}) {
  const data = document.structured_data || {};
  const [form, setForm] = useState<Record<string, string>>(Object.fromEntries(editableFields.map((field) => [field, data[field] == null ? "" : String(data[field])])));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    setSaving(true); setError("");
    const updates: Record<string, unknown> = {};
    editableFields.forEach((field) => { if (form[field] !== (data[field] == null ? "" : String(data[field]))) updates[field] = form[field] || null; });
    try { onUpdated(await api.correct(document.id, updates)); } catch (err) { setError((err as Error).message); } finally { setSaving(false); }
  }
  async function reprocess() { setSaving(true); try { await api.reprocess(document.id); onClose(); } catch (err) {setError((err as Error).message);} finally {setSaving(false);} }
  return <div className="overlay"><section className="review-panel"><div className="panel-head"><div><span className="eyebrow">DOCUMENT REVIEW</span><h2>{document.original_name}</h2><div><StatusPill status={document.status}/><span>{document.page_count || "—"} pages · {formatBytes(document.size_bytes)}</span></div></div><button className="icon-button" onClick={onClose}><X/></button></div>
    <div className="panel-body">{error && <div className="toast error"><AlertCircle size={16}/>{error}</div>}
      {document.error_message && <div className="failure-box"><AlertCircle/><div><strong>Processing failed</strong><p>{document.error_message}</p><button onClick={reprocess}>Reprocess document</button></div></div>}
      <div className="review-grid"><div className="form-card"><div className="section-title"><h3>Extracted fields</h3><span>Correct values before approval</span></div><div className="field-grid">{editableFields.map((field) => <label key={field}><span>{field.replaceAll("_", " ")} {document.confidence?.[field] != null && <em>{Math.round(document.confidence[field] * 100)}%</em>}</span><input value={form[field]} onChange={(e) => setForm({...form, [field]: e.target.value})}/></label>)}</div></div>
        <div className="issue-card"><div className="section-title"><h3>Validation report</h3><span>{document.validations.length} issue{document.validations.length === 1 ? "" : "s"}</span></div>{document.validations.length ? <div className="issue-list">{document.validations.map((issue) => <div className={`issue ${issue.severity}`} key={issue.id}><AlertCircle size={17}/><div><strong>{issue.message}</strong><span>{issue.field || issue.code}{issue.expected && ` · expected ${issue.expected}`}{issue.actual && ` · found ${issue.actual}`}</span></div></div>)}</div> : <div className="all-clear"><ShieldCheck/><strong>All checks passed</strong><span>Amounts and required fields are consistent.</span></div>}</div>
      </div>
      {Array.isArray(data.line_items) && <div className="line-card"><div className="section-title"><h3>Line items</h3><span>{data.line_items.length} rows extracted</span></div><div className="line-table"><table><thead><tr><th>Description</th><th>Quantity</th><th>Unit price</th><th>Amount</th></tr></thead><tbody>{(data.line_items as Record<string, unknown>[]).map((item, i) => <tr key={i}><td>{String(item.description ?? "—")}</td><td>{String(item.quantity ?? "—")}</td><td>{String(item.unit_price ?? "—")}</td><td>{String(item.amount ?? "—")}</td></tr>)}</tbody></table></div></div>}
      {document.raw_text && <details className="raw-text"><summary>View extracted source text</summary><pre>{document.raw_text}</pre></details>}
    </div><div className="panel-foot"><button className="ghost-button" onClick={reprocess} disabled={saving}><RefreshCw size={15}/>Reprocess</button><div><button className="ghost-button" onClick={onClose}>Cancel</button><button className="primary-button" onClick={save} disabled={saving}>{saving ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>}Save corrections</button></div></div>
  </section></div>;
}

function ComparePanel({result, onClose}: {result: Awaited<ReturnType<typeof api.compare>>; onClose: () => void}) {
  return <div className="overlay"><section className="compare-panel"><div className="panel-head"><div><span className="eyebrow">CROSS-VERIFICATION</span><h2>{result.matches ? "Documents match" : "Differences found"}</h2></div><button className="icon-button" onClick={onClose}><X/></button></div><div className="compare-summary"><div className={result.matches ? "result-orb match" : "result-orb mismatch"}>{result.matches ? <Check/> : <AlertCircle/>}</div><p>{result.comparisons.filter((item) => item.matches).length} of {result.comparisons.length} fields match across both documents.</p></div><div className="comparison-list"><div className="comparison-row header"><span>Field</span><span>Document A</span><span>Document B</span><span>Result</span></div>{result.comparisons.map((item) => <div className="comparison-row" key={item.field}><strong>{item.field.replaceAll("_", " ")}</strong><span>{String(item.left ?? "Missing")}</span><span>{String(item.right ?? "Missing")}</span><span className={item.matches ? "match-text" : "mismatch-text"}>{item.matches ? "Match" : "Different"}</span></div>)}</div></section></div>;
}

export default App;

