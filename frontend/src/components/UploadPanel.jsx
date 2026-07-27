import { useRef, useState } from 'react';
import { uploadDocument } from '../api.js';

const ACCEPTED = '.pdf,.jpg,.jpeg,.png';
const ACCEPTED_MIME = new Set(['application/pdf', 'image/jpeg', 'image/png']);








export function UploadPanel({ onUploadSuccess }) {
  const [file, setFile]       = useState(null);
  const [dragOver, setDrag]   = useState(false);
  const [uploading, setUpl]   = useState(false);
  const [log, setLog]         = useState([]);   
  const inputRef              = useRef(null);
  const logId                 = useRef(0);

  function addLog(type, text) {
    const id = ++logId.current;
    setLog((prev) => [...prev.slice(-4), { id, type, text }]);
  }

  function handleFile(f) {
    if (!f) return;
    if (!ACCEPTED_MIME.has(f.type)) {
      addLog('error', `"${f.name}" is not a PDF, JPEG, or PNG.`);
      return;
    }
    setFile(f);
  }

  function onInputChange(e) {
    handleFile(e.target.files?.[0]);
    
    e.target.value = '';
  }

  function onDrop(e) {
    e.preventDefault();
    setDrag(false);
    handleFile(e.dataTransfer.files?.[0]);
  }

  async function handleUpload() {
    if (!file || uploading) return;
    setUpl(true);
    addLog('loading', `Uploading "${file.name}"…`);

    try {
      const result = await uploadDocument(file);
      addLog(
        'success',
        `✓ ${result.chunks_extracted} chunk${result.chunks_extracted !== 1 ? 's' : ''} indexed from "${result.filename}"`
      );
      onUploadSuccess?.(result);
      setFile(null);
    } catch (err) {
      addLog('error', err.message);
    } finally {
      setUpl(false);
    }
  }

  const logIcons = { success: '✓', error: '✕', loading: '⋯' };

  return (
    <div className="upload-panel">
      {}
      <div
        className={`drop-zone${dragOver ? ' drag-over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Select or drop a document file"
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          onChange={onInputChange}
          aria-hidden="true"
          tabIndex={-1}
          style={{ pointerEvents: 'none' }}
        />
        <span className="drop-zone-icon">📎</span>
        <span className="drop-zone-label">
          {dragOver ? 'Drop it here' : 'Click or drag a file'}
        </span>
        <span className="drop-zone-sub">PDF · JPEG · PNG</span>
      </div>

      {}
      {file && (
        <div className="upload-file-row">
          <span className="upload-file-name" title={file.name}>{file.name}</span>
          <button
            className="upload-file-clear"
            onClick={() => setFile(null)}
            aria-label="Remove selected file"
          >
            ×
          </button>
        </div>
      )}

      {}
      <button
        className="upload-btn"
        onClick={handleUpload}
        disabled={!file || uploading}
        aria-busy={uploading}
      >
        {uploading
          ? <><span className="spinner" aria-hidden="true" /> Ingesting…</>
          : '↑ Ingest Document'}
      </button>

      {}
      {log.length > 0 && (
        <div className="upload-log" aria-live="polite" aria-atomic="false">
          {log.map((entry) => (
            <div key={entry.id} className={`upload-log-item ${entry.type}`}>
              <span className="log-icon">{logIcons[entry.type]}</span>
              <span className="log-text">{entry.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
