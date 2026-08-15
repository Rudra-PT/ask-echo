/** SourceCard — renders a single retrieved Pinecone chunk as a citation card. */
export function SourceCard({ source }) {
  const mimeLabel = {
    'application/pdf': '📄 PDF',
    'image/jpeg':      '🖼 JPEG',
    'image/png':       '🖼 PNG',
  }[source.mime_type] ?? source.mime_type ?? '📎';

  // Support both new (file_name) and legacy (source_filename) keys
  const displayName = source.file_name || source.source_filename || 'Unknown source';
  const page        = source.page_number;
  const pct         = source.score != null ? Math.round(source.score * 100) : null;

  return (
    <article className="source-card">
      <div className="source-card-header">
        {/* Rank badge */}
        <span className="source-rank">{source.rank}</span>

        {/* Filename */}
        <span className="source-filename" title={displayName}>
          {displayName}
        </span>

        {/* Score */}
        {pct != null && (
          <span className="source-score">{pct}% match</span>
        )}
      </div>

      {/* Page number pill — shown only when available */}
      {page != null && (
        <div className="source-page-row">
          <span className="source-page-pill">Page {page}</span>
        </div>
      )}

      {/* Text preview */}
      {source.text_preview && (
        <p className="source-preview">{source.text_preview}</p>
      )}

      {/* MIME type badge */}
      <span className="source-mime">{mimeLabel}</span>
    </article>
  );
}
