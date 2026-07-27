/** SourceCard — renders a single Pinecone result citation */
export function SourceCard({ source }) {
  const mimeLabel = {
    'application/pdf': '📄 PDF',
    'image/jpeg':      '🖼 JPEG',
    'image/png':       '🖼 PNG',
  }[source.mime_type] ?? source.mime_type;

  const pct = Math.round(source.score * 100);

  return (
    <article className="source-card">
      <div className="source-card-header">
        <span className="source-rank">{source.rank}</span>
        <span className="source-filename" title={source.source_filename}>
          {source.source_filename}
        </span>
        <span className="source-score">{pct}% match</span>
      </div>
      <p className="source-preview">{source.text_preview}</p>
      <span className="source-mime">{mimeLabel}</span>
    </article>
  );
}
