import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './ChromaAdminPage.css';

interface CollectionInfo {
  name: string;
  count: number;
  metadata: Record<string, any>;
}

interface ChromaStats {
  persist_directory: string;
  total_collections: number;
  total_documents: number;
  collections: CollectionInfo[];
}

interface Document {
  id: string;
  document: string | null;
  metadata: Record<string, any> | null;
}

interface DocumentsResponse {
  total: number;
  offset: number;
  limit: number;
  documents: Document[];
}

interface SearchResult {
  id: string;
  document: string | null;
  metadata: Record<string, any> | null;
  distance: number;
  similarity: number;
}

const ChromaAdminPage: React.FC = () => {
  const [stats, setStats] = useState<ChromaStats | null>(null);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [totalDocs, setTotalDocs] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  const LIMIT = 20;

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/chroma/stats');
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);

      if (data.collections && data.collections.length > 0) {
        const defaultCollection = data.collections.find((c: CollectionInfo) => c.name === 'carmen_docs') || data.collections[0];
        setSelectedCollection(defaultCollection.name);
        fetchDocuments(defaultCollection.name, 0);
      }
    } catch (err) {
      setError('Failed to load ChromaDB statistics');
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async (collectionName: string, newOffset: number) => {
    try {
      const response = await fetch(
        `/api/admin/chroma/collections/${collectionName}/documents?offset=${newOffset}&limit=${LIMIT}`
      );
      if (!response.ok) throw new Error('Failed to fetch documents');
      const data: DocumentsResponse = await response.json();
      setDocuments(data.documents);
      setTotalDocs(data.total);
      setOffset(newOffset);
      setSearchResults(null);
    } catch (err) {
      setError('Failed to load documents');
    }
  };

  const handleCollectionSelect = (name: string) => {
    setSelectedCollection(name);
    setOffset(0);
    setSearchResults(null);
    setSearchQuery('');
    fetchDocuments(name, 0);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim() || !selectedCollection) return;

    try {
      setSearching(true);
      const response = await fetch(
        `/api/admin/chroma/collections/${selectedCollection}/search?q=${encodeURIComponent(searchQuery)}&top_k=20`
      );
      if (!response.ok) throw new Error('Search failed');
      const data: SearchResult[] = await response.json();
      setSearchResults(data);
    } catch (err) {
      setError('Search failed');
    } finally {
      setSearching(false);
    }
  };

  const clearSearch = () => {
    setSearchResults(null);
    setSearchQuery('');
    if (selectedCollection) {
      fetchDocuments(selectedCollection, 0);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!selectedCollection || !confirm('Are you sure you want to delete this document?')) return;

    try {
      const response = await fetch(
        `/api/admin/chroma/collections/${selectedCollection}/documents/${docId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) throw new Error('Delete failed');

      if (searchResults) {
        setSearchResults(searchResults.filter(r => r.id !== docId));
      } else {
        fetchDocuments(selectedCollection, offset);
      }
      fetchStats();
      setSelectedDoc(null);
    } catch (err) {
      setError('Failed to delete document');
    }
  };

  const totalPages = Math.ceil(totalDocs / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  const truncateText = (text: string | null, maxLength: number) => {
    if (!text) return '-';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <div className="chroma-admin-page">
      {/* Header */}
      <div className="header">
        <div className="header-content">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
          </svg>
          <div>
            <div className="header-title">ChromaDB Admin</div>
            <div className="header-subtitle">Browse and manage vector database</div>
          </div>
        </div>

        <div className="header-actions">
          <Link to="/stats" className="nav-link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 20V10M12 20V4M6 20v-6" />
            </svg>
            <span>Stats</span>
          </Link>
          <Link to="/" className="nav-link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            <span>Chat</span>
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="content">
        {error && (
          <div className="error-banner">
            {error}
            <button onClick={() => setError(null)} className="error-close">&times;</button>
          </div>
        )}

        {loading ? (
          <div className="loading-state">Loading ChromaDB data...</div>
        ) : (
          <>
            {/* Stats Cards */}
            {stats && (
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label">Collections</div>
                  <div className="stat-value stat-value-blue">{stats.total_collections}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Total Documents</div>
                  <div className="stat-value stat-value-green">{stats.total_documents.toLocaleString()}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Storage Path</div>
                  <div className="stat-path">{stats.persist_directory}</div>
                </div>
              </div>
            )}

            {/* Main Panel */}
            <div className="main-panel">
              {/* Collections Sidebar */}
              <div className="collections-sidebar">
                <div className="panel-header">Collections</div>
                <div className="collections-list">
                  {stats?.collections.map((col) => (
                    <div
                      key={col.name}
                      onClick={() => handleCollectionSelect(col.name)}
                      className={`collection-item ${selectedCollection === col.name ? 'active' : ''}`}
                    >
                      <div className="collection-name">{col.name}</div>
                      <div className="collection-count">{col.count.toLocaleString()} docs</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Documents Panel */}
              <div className="documents-panel">
                <div className="panel-header panel-header-with-actions">
                  <span>
                    {searchResults
                      ? `Search Results (${searchResults.length})`
                      : `Documents (${totalDocs.toLocaleString()})`
                    }
                  </span>

                  {/* Search */}
                  <div className="search-bar">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      placeholder="Semantic search..."
                      className="search-input"
                    />
                    {searchResults ? (
                      <button onClick={clearSearch} className="search-btn clear-btn">
                        Clear
                      </button>
                    ) : (
                      <button onClick={handleSearch} disabled={searching} className="search-btn">
                        {searching ? '...' : 'Search'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Documents Table */}
                <div className="documents-table-container">
                  <table className="documents-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Content</th>
                        <th>Source</th>
                        {searchResults && <th>Similarity</th>}
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(searchResults || documents).map((item) => {
                        const doc = 'similarity' in item ? item : item;
                        const similarity = 'similarity' in item ? (item as SearchResult).similarity : null;

                        return (
                          <tr key={doc.id} onClick={() => setSelectedDoc(doc)} className="doc-row">
                            <td className="doc-id">{truncateText(doc.id, 20)}</td>
                            <td className="doc-content">{truncateText(doc.document, 100)}</td>
                            <td className="doc-source">
                              {truncateText(doc.metadata?.source || doc.metadata?.section || '-', 30)}
                            </td>
                            {searchResults && (
                              <td className="doc-similarity">
                                <span className="similarity-badge">
                                  {((similarity || 0) * 100).toFixed(1)}%
                                </span>
                              </td>
                            )}
                            <td className="doc-actions">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteDocument(doc.id);
                                }}
                                className="delete-btn"
                                title="Delete document"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                                </svg>
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {!searchResults && totalPages > 1 && (
                  <div className="pagination">
                    <button
                      onClick={() => selectedCollection && fetchDocuments(selectedCollection, offset - LIMIT)}
                      disabled={offset === 0}
                      className="page-btn"
                    >
                      Previous
                    </button>
                    <span className="page-info">
                      Page {currentPage} of {totalPages}
                    </span>
                    <button
                      onClick={() => selectedCollection && fetchDocuments(selectedCollection, offset + LIMIT)}
                      disabled={currentPage >= totalPages}
                      className="page-btn"
                    >
                      Next
                    </button>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Document Detail Modal */}
      {selectedDoc && (
        <div className="modal-overlay" onClick={() => setSelectedDoc(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Document Details</h3>
              <button onClick={() => setSelectedDoc(null)} className="modal-close">&times;</button>
            </div>
            <div className="modal-content">
              <div className="detail-row">
                <label>ID:</label>
                <code>{selectedDoc.id}</code>
              </div>

              {selectedDoc.metadata && Object.keys(selectedDoc.metadata).length > 0 && (
                <div className="detail-row">
                  <label>Metadata:</label>
                  <pre className="metadata-json">
                    {JSON.stringify(selectedDoc.metadata, null, 2)}
                  </pre>
                </div>
              )}

              <div className="detail-row">
                <label>Content:</label>
                <div className="doc-full-content">
                  {selectedDoc.document || 'No content'}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button
                onClick={() => handleDeleteDocument(selectedDoc.id)}
                className="btn-danger"
              >
                Delete Document
              </button>
              <button onClick={() => setSelectedDoc(null)} className="btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChromaAdminPage;
