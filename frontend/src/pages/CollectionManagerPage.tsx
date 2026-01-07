import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './CollectionManagerPage.css';

interface Collection {
  id: string;
  name: string;
  domain: string;
  source_type: string;
  description: string;
  created_at: string;
  updated_at: string;
  document_count: number;
}

interface ImportJob {
  id: string;
  collection_name: string;
  source_type: string;
  status: string;
  progress: number;
  total_items: number;
  processed_items: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface Domain {
  id: string;
  name: string;
  description: string;
}

interface DatabaseTable {
  name: string;
  row_count: number;
}

interface DatabaseColumn {
  name: string;
  type: string;
  nullable: boolean;
  is_text: boolean;
  is_key: boolean;
}

interface SavedConnection {
  id: string;
  name: string;
  db_type: string;
  host: string;
  port: number;
  user: string;
  database: string;
  created_at: string;
}

interface TablePreview {
  columns: string[];
  rows: Record<string, unknown>[];
  total_count: number;
}

// Default domains in case API fails to load
const DEFAULT_DOMAINS: Domain[] = [
  { id: 'budget', name: 'Budget & Financial', description: 'Budget data and financial planning' },
  { id: 'usali', name: 'USALI Accounting', description: 'Hotel financial accounting (USALI standards)' },
  { id: 'general_docs', name: 'General Documentation', description: 'General Carmen Cloud documentation' },
  { id: 'faq', name: 'FAQ', description: 'Frequently asked questions' },
  { id: 'hotel_operations', name: 'Hotel Operations', description: 'Hotel operations and hospitality management' },
  { id: 'custom', name: 'Custom', description: 'Custom domain type' },
];

const CollectionManagerPage: React.FC = () => {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [importJobs, setImportJobs] = useState<ImportJob[]>([]);
  const [domains, setDomains] = useState<Domain[]>(DEFAULT_DOMAINS);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'collections' | 'import' | 'database' | 'jobs'>('collections');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Database connection state
  const [dbConfig, setDbConfig] = useState({
    db_type: 'mariadb',
    host: '127.0.0.1',
    port: 3336,
    user: 'root',
    password: '',
    database: 'carmen',
  });
  const [dbConnected, setDbConnected] = useState(false);
  const [dbConnecting, setDbConnecting] = useState(false);
  const [dbTables, setDbTables] = useState<DatabaseTable[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableColumns, setTableColumns] = useState<DatabaseColumn[]>([]);
  const [tablePreview, setTablePreview] = useState<TablePreview | null>(null);
  const [dbImportConfig, setDbImportConfig] = useState({
    collection_name: '',
    domain: 'usali',
    description: '',
    content_columns: [] as string[],
    metadata_columns: [] as string[],
    where_clause: '',
    save_connection: false,
    connection_name: '',
  });
  const [dbImporting, setDbImporting] = useState(false);
  const [loadingTable, setLoadingTable] = useState(false);
  const [savedConnections, setSavedConnections] = useState<SavedConnection[]>([]);

  // Create collection form
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newCollection, setNewCollection] = useState({
    name: '',
    domain: 'general_docs',
    description: '',
  });

  // Import form
  const [importConfig, setImportConfig] = useState({
    collection_name: '',
    domain: 'general_docs',
    content_columns: '',
    metadata_columns: '',
    delimiter: ',',
    is_usali: false,
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const hasRunningJobsRef = useRef(false);

  // Define fetch functions with useCallback before useEffects
  const fetchCollections = useCallback(async () => {
    const response = await fetch('/api/admin/collections/');
    if (response.ok) {
      const data = await response.json();
      setCollections(data);
    }
  }, []);

  const fetchImportJobs = useCallback(async () => {
    const response = await fetch('/api/admin/collections/import-jobs');
    if (response.ok) {
      const data = await response.json();
      setImportJobs(data);
    }
  }, []);

  const fetchDomains = useCallback(async () => {
    const response = await fetch('/api/admin/collections/domains');
    if (response.ok) {
      const data = await response.json();
      setDomains(data.domains);
    }
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchCollections(),
        fetchImportJobs(),
        fetchDomains(),
      ]);
    } catch {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [fetchCollections, fetchImportJobs, fetchDomains]);

  useEffect(() => {
    fetchData();
    return () => {
      // Cleanup polling on unmount
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [fetchData]);

  // Handle tab changes
  useEffect(() => {
    if (activeTab === 'jobs') {
      // Fetch immediately when switching to jobs tab
      fetchImportJobs();
    } else if (activeTab === 'collections') {
      // Refresh collections when switching to collections tab
      fetchCollections();
    }
  }, [activeTab, fetchImportJobs, fetchCollections]);

  // Separate effect for polling - only depends on whether jobs are running
  useEffect(() => {
    const hasRunning = importJobs.some(job => job.status === 'running' || job.status === 'pending');

    // Only start/stop polling when running state changes
    if (hasRunning && !hasRunningJobsRef.current) {
      // Start polling
      hasRunningJobsRef.current = true;
      pollingRef.current = setInterval(fetchImportJobs, 2000);
    } else if (!hasRunning && hasRunningJobsRef.current) {
      // Stop polling and refresh collections (import completed)
      hasRunningJobsRef.current = false;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      // Refresh collections after jobs complete
      fetchCollections();
    }
  }, [importJobs, fetchImportJobs, fetchCollections]);

  const handleCreateCollection = async () => {
    if (!newCollection.name.trim()) {
      setError('Collection name is required');
      return;
    }

    try {
      const response = await fetch('/api/admin/collections/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCollection),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create collection');
      }

      setSuccess('Collection created successfully');
      setShowCreateModal(false);
      setNewCollection({ name: '', domain: 'general_docs', description: '' });
      fetchCollections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create collection');
    }
  };

  const handleDeleteCollection = async (name: string) => {
    if (!window.confirm(`Are you sure you want to delete collection "${name}"? This will delete all data.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/collections/${name}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete collection');
      }

      setSuccess('Collection deleted');
      fetchCollections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete collection');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleImportCSV = async () => {
    if (!selectedFile) {
      setError('Please select a CSV file');
      return;
    }

    if (!importConfig.collection_name.trim()) {
      setError('Collection name is required');
      return;
    }

    if (!importConfig.content_columns.trim()) {
      setError('At least one content column is required');
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('collection_name', importConfig.collection_name);
      formData.append('domain', importConfig.domain);
      formData.append('content_columns', importConfig.content_columns);
      formData.append('metadata_columns', importConfig.metadata_columns);
      formData.append('delimiter', importConfig.delimiter);
      formData.append('is_usali', String(importConfig.is_usali));

      const response = await fetch('/api/admin/collections/import/csv', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Import failed');
      }

      setSuccess('Import started. Check the Jobs tab for progress.');
      setSelectedFile(null);
      setImportConfig({
        collection_name: '',
        domain: 'general_docs',
        content_columns: '',
        metadata_columns: '',
        delimiter: ',',
        is_usali: false,
      });
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      setActiveTab('jobs');
      fetchImportJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setUploading(false);
    }
  };

  // Database connection handlers
  const handleTestConnection = async () => {
    setDbConnecting(true);
    setError(null);
    try {
      const response = await fetch('/api/admin/collections/database/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dbConfig),
      });

      if (!response.ok) {
        const text = await response.text();
        try {
          const errData = JSON.parse(text);
          throw new Error(errData.detail || errData.message || 'Connection failed');
        } catch {
          throw new Error(text || `Server error: ${response.status}`);
        }
      }

      const data = await response.json();
      if (data.success) {
        setDbConnected(true);
        setSuccess('Connected to database successfully');
        // Fetch tables
        await fetchDbTables();
        // Fetch saved connections
        await fetchSavedConnections();
      } else {
        setError(data.message || 'Connection failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setDbConnecting(false);
    }
  };

  const fetchDbTables = async () => {
    try {
      const response = await fetch('/api/admin/collections/database/tables', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dbConfig),
      });
      if (response.ok) {
        const data = await response.json();
        setDbTables(data.tables);
      }
    } catch (err) {
      console.error('Failed to fetch tables:', err);
    }
  };

  const fetchSavedConnections = async () => {
    try {
      const response = await fetch('/api/admin/collections/database/connections');
      if (response.ok) {
        const data = await response.json();
        setSavedConnections(data);
      }
    } catch (err) {
      console.error('Failed to fetch saved connections:', err);
    }
  };

  const handleSelectTable = async (tableName: string) => {
    setSelectedTable(tableName);
    setLoadingTable(true);
    setDbImportConfig(prev => ({ ...prev, collection_name: tableName }));

    try {
      // Fetch columns
      const colResponse = await fetch('/api/admin/collections/database/columns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...dbConfig, table_name: tableName }),
      });
      if (colResponse.ok) {
        const data = await colResponse.json();
        setTableColumns(data.columns);
        // Auto-select text columns for content, keys for metadata
        const textCols = data.columns.filter((c: DatabaseColumn) => c.is_text).map((c: DatabaseColumn) => c.name);
        const keyCols = data.columns.filter((c: DatabaseColumn) => c.is_key).map((c: DatabaseColumn) => c.name);
        setDbImportConfig(prev => ({
          ...prev,
          content_columns: textCols,
          metadata_columns: keyCols,
        }));
      }

      // Fetch preview
      const previewResponse = await fetch('/api/admin/collections/database/preview?limit=5', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...dbConfig, table_name: tableName }),
      });
      if (previewResponse.ok) {
        const data = await previewResponse.json();
        setTablePreview(data);
      }
    } catch (err) {
      console.error('Failed to fetch table data:', err);
    } finally {
      setLoadingTable(false);
    }
  };

  const handleToggleContentColumn = (colName: string) => {
    setDbImportConfig(prev => ({
      ...prev,
      content_columns: prev.content_columns.includes(colName)
        ? prev.content_columns.filter(c => c !== colName)
        : [...prev.content_columns, colName],
    }));
  };

  const handleToggleMetadataColumn = (colName: string) => {
    setDbImportConfig(prev => ({
      ...prev,
      metadata_columns: prev.metadata_columns.includes(colName)
        ? prev.metadata_columns.filter(c => c !== colName)
        : [...prev.metadata_columns, colName],
    }));
  };

  const handleImportDatabase = async () => {
    if (!selectedTable) {
      setError('Please select a table');
      return;
    }
    if (!dbImportConfig.collection_name.trim()) {
      setError('Collection name is required');
      return;
    }
    if (dbImportConfig.content_columns.length === 0) {
      setError('Please select at least one content column for search');
      return;
    }

    setDbImporting(true);
    try {
      const response = await fetch('/api/admin/collections/import/database', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...dbConfig,
          ...dbImportConfig,
          table_name: selectedTable,
          auto_detect_columns: false, // Use manually selected columns
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Import failed');
      }

      setSuccess('Import started. Check the Jobs tab for progress.');
      await fetchImportJobs(); // Fetch immediately so count updates
      setActiveTab('jobs');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Database import failed');
    } finally {
      setDbImporting(false);
    }
  };

  const handleLoadSavedConnection = async (conn: SavedConnection) => {
    try {
      const response = await fetch(`/api/admin/collections/database/connections/${conn.id}?include_password=true`);
      if (response.ok) {
        const data = await response.json();
        setDbConfig({
          db_type: data.db_type,
          host: data.host,
          port: data.port,
          user: data.user,
          password: data.password || '',
          database: data.database,
        });
      }
    } catch (err) {
      console.error('Failed to load connection:', err);
    }
  };

  const getDomainBadgeColor = (domain: string) => {
    switch (domain) {
      case 'budget': return '#db2777';
      case 'usali': return '#7c3aed';
      case 'general_docs': return '#2563eb';
      case 'faq': return '#059669';
      case 'hotel_operations': return '#d97706';
      default: return '#6b7280';
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = {
      pending: { bg: '#fef3c7', color: '#92400e' },
      running: { bg: '#dbeafe', color: '#1e40af' },
      completed: { bg: '#dcfce7', color: '#166534' },
      failed: { bg: '#fee2e2', color: '#991b1b' },
    };
    return styles[status] || { bg: '#f3f4f6', color: '#374151' };
  };

  return (
    <div className="collection-manager-page">
      {/* Header */}
      <div className="header">
        <div className="header-content">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2z" />
            <path d="M9 7h6M9 12h6M9 17h4" />
          </svg>
          <div>
            <div className="header-title">Collection Manager</div>
            <div className="header-subtitle">Manage knowledge base collections</div>
          </div>
        </div>

        <div className="header-actions">
          <Link to="/admin/chroma" className="nav-link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l4 2" />
            </svg>
            <span>ChromaDB</span>
          </Link>
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
        {/* Alerts */}
        {error && (
          <div className="alert alert-error">
            {error}
            <button onClick={() => setError(null)} className="alert-close">&times;</button>
          </div>
        )}
        {success && (
          <div className="alert alert-success">
            {success}
            <button onClick={() => setSuccess(null)} className="alert-close">&times;</button>
          </div>
        )}

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'collections' ? 'active' : ''}`}
            onClick={() => setActiveTab('collections')}
          >
            Collections ({collections.length})
          </button>
          <button
            className={`tab ${activeTab === 'import' ? 'active' : ''}`}
            onClick={() => setActiveTab('import')}
          >
            Import CSV
          </button>
          <button
            className={`tab ${activeTab === 'database' ? 'active' : ''}`}
            onClick={() => setActiveTab('database')}
          >
            Import Database
          </button>
          <button
            className={`tab ${activeTab === 'jobs' ? 'active' : ''}`}
            onClick={() => setActiveTab('jobs')}
          >
            Jobs ({importJobs.filter(j => j.status === 'running').length} running)
          </button>
        </div>

        {loading ? (
          <div className="loading-state">Loading...</div>
        ) : (
          <>
            {/* Collections Tab */}
            {activeTab === 'collections' && (
              <div className="tab-content">
                <div className="section-header">
                  <h2>Knowledge Base Collections</h2>
                  <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
                    + Create Collection
                  </button>
                </div>

                <div className="collections-grid">
                  {collections.map(col => (
                    <div key={col.id} className="collection-card">
                      <div className="collection-header">
                        <h3>{col.name}</h3>
                        <span
                          className="domain-badge"
                          style={{ background: getDomainBadgeColor(col.domain) }}
                        >
                          {col.domain}
                        </span>
                      </div>
                      <p className="collection-desc">{col.description || 'No description'}</p>
                      <div className="collection-stats">
                        <div className="stat">
                          <span className="stat-value">{col.document_count.toLocaleString()}</span>
                          <span className="stat-label">Documents</span>
                        </div>
                        <div className="stat">
                          <span className="stat-value">{col.source_type}</span>
                          <span className="stat-label">Source</span>
                        </div>
                      </div>
                      <div className="collection-actions">
                        <Link to={`/admin/chroma?collection=${col.name}`} className="btn-secondary btn-sm">
                          Browse
                        </Link>
                        <button
                          className="btn-danger btn-sm"
                          onClick={() => handleDeleteCollection(col.name)}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}

                  {collections.length === 0 && (
                    <div className="empty-state">
                      <p>No collections found. Create one to get started.</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Import Tab */}
            {activeTab === 'import' && (
              <div className="tab-content">
                <div className="import-form">
                  <h2>Import CSV Data</h2>
                  <p className="form-desc">
                    Upload a CSV file to create or update a collection. For USALI accounting data,
                    enable the USALI format option.
                  </p>

                  <div className="form-group">
                    <label>CSV File</label>
                    <input
                      type="file"
                      accept=".csv"
                      ref={fileInputRef}
                      onChange={handleFileSelect}
                      className="file-input"
                    />
                    {selectedFile && (
                      <div className="file-info">
                        Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                      </div>
                    )}
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Collection Name *</label>
                      <input
                        type="text"
                        value={importConfig.collection_name}
                        onChange={e => setImportConfig({ ...importConfig, collection_name: e.target.value })}
                        placeholder="e.g., usali_accounts"
                      />
                    </div>

                    <div className="form-group">
                      <label>Domain *</label>
                      <select
                        value={importConfig.domain}
                        onChange={e => setImportConfig({ ...importConfig, domain: e.target.value })}
                      >
                        {domains.map(d => (
                          <option key={d.id} value={d.id}>{d.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Content Columns * (comma-separated)</label>
                    <input
                      type="text"
                      value={importConfig.content_columns}
                      onChange={e => setImportConfig({ ...importConfig, content_columns: e.target.value })}
                      placeholder="e.g., description, notes"
                    />
                    <small>Columns to use as searchable content</small>
                  </div>

                  <div className="form-group">
                    <label>Metadata Columns (comma-separated)</label>
                    <input
                      type="text"
                      value={importConfig.metadata_columns}
                      onChange={e => setImportConfig({ ...importConfig, metadata_columns: e.target.value })}
                      placeholder="e.g., account_code, category"
                    />
                    <small>Columns to store as metadata for filtering</small>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Delimiter</label>
                      <select
                        value={importConfig.delimiter}
                        onChange={e => setImportConfig({ ...importConfig, delimiter: e.target.value })}
                      >
                        <option value=",">Comma (,)</option>
                        <option value=";">Semicolon (;)</option>
                        <option value="\t">Tab</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={importConfig.is_usali}
                          onChange={e => setImportConfig({ ...importConfig, is_usali: e.target.checked })}
                        />
                        USALI Format
                      </label>
                      <small>Use specialized USALI accounting format</small>
                    </div>
                  </div>

                  <button
                    className="btn-primary btn-lg"
                    onClick={handleImportCSV}
                    disabled={uploading || !selectedFile}
                  >
                    {uploading ? 'Uploading...' : 'Start Import'}
                  </button>
                </div>
              </div>
            )}

            {/* Database Tab */}
            {activeTab === 'database' && (
              <div className="tab-content">
                <div className="import-form wide">
                  <h2>Import from Database</h2>
                  <p className="form-desc">
                    Connect to a MySQL/MariaDB database and import table data into a collection.
                    Text columns will be automatically detected for content search.
                  </p>

                  {/* Saved Connections */}
                  {savedConnections.length > 0 && !dbConnected && (
                    <div className="saved-connections">
                      <label>Saved Connections</label>
                      <div className="saved-connections-list">
                        {savedConnections.map(conn => (
                          <button
                            key={conn.id}
                            className="saved-conn-btn"
                            onClick={() => handleLoadSavedConnection(conn)}
                          >
                            {conn.name} ({conn.host}:{conn.port})
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Connection Form */}
                  {!dbConnected && (
                    <div className="db-connection-form">
                      <div className="form-row">
                        <div className="form-group">
                          <label>Database Type</label>
                          <select
                            value={dbConfig.db_type}
                            onChange={e => setDbConfig({ ...dbConfig, db_type: e.target.value })}
                          >
                            <option value="mariadb">MariaDB</option>
                            <option value="mysql">MySQL</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Host</label>
                          <input
                            type="text"
                            value={dbConfig.host}
                            onChange={e => setDbConfig({ ...dbConfig, host: e.target.value })}
                            placeholder="127.0.0.1"
                          />
                        </div>
                        <div className="form-group form-group-sm">
                          <label>Port</label>
                          <input
                            type="number"
                            value={dbConfig.port}
                            onChange={e => setDbConfig({ ...dbConfig, port: parseInt(e.target.value) || 3306 })}
                          />
                        </div>
                      </div>

                      <div className="form-row">
                        <div className="form-group">
                          <label>User</label>
                          <input
                            type="text"
                            value={dbConfig.user}
                            onChange={e => setDbConfig({ ...dbConfig, user: e.target.value })}
                            placeholder="root"
                          />
                        </div>
                        <div className="form-group">
                          <label>Password</label>
                          <input
                            type="password"
                            value={dbConfig.password}
                            onChange={e => setDbConfig({ ...dbConfig, password: e.target.value })}
                            placeholder="Password"
                          />
                        </div>
                        <div className="form-group">
                          <label>Database</label>
                          <input
                            type="text"
                            value={dbConfig.database}
                            onChange={e => setDbConfig({ ...dbConfig, database: e.target.value })}
                            placeholder="Database name"
                          />
                        </div>
                      </div>

                      <button
                        className="btn-primary"
                        onClick={handleTestConnection}
                        disabled={dbConnecting}
                      >
                        {dbConnecting ? 'Connecting...' : 'Connect'}
                      </button>
                    </div>
                  )}

                  {/* Table Browser */}
                  {dbConnected && (
                    <div className="db-browser">
                      <div className="db-connected-header">
                        <span className="connected-badge">
                          Connected to {dbConfig.database}@{dbConfig.host}:{dbConfig.port}
                        </span>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => {
                            setDbConnected(false);
                            setDbTables([]);
                            setSelectedTable(null);
                            setTableColumns([]);
                            setTablePreview(null);
                          }}
                        >
                          Disconnect
                        </button>
                      </div>

                      <div className="db-browser-layout">
                        {/* Tables List */}
                        <div className="tables-panel">
                          <div className="panel-header">Tables</div>
                          <div className="tables-list">
                            {dbTables.map(table => (
                              <div
                                key={table.name}
                                className={`table-item ${selectedTable === table.name ? 'active' : ''}`}
                                onClick={() => handleSelectTable(table.name)}
                              >
                                <span className="table-name">{table.name}</span>
                                <span className="table-count">{table.row_count.toLocaleString()} rows</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Preview & Import Settings */}
                        {selectedTable && (
                          <div className="columns-panel">
                            <div className="panel-header">
                              Table: {selectedTable}
                            </div>

                            {loadingTable ? (
                              <div className="loading-panel">Loading table data...</div>
                            ) : (
                              <>
                                {/* Column Selection */}
                                {tableColumns.length > 0 && (
                                  <div className="columns-selection">
                                    <div className="column-group">
                                      <h4>Content Columns (for search)</h4>
                                      <div className="columns-checkboxes">
                                        {tableColumns.map(col => (
                                          <label key={col.name} className="column-checkbox">
                                            <input
                                              type="checkbox"
                                              checked={dbImportConfig.content_columns.includes(col.name)}
                                              onChange={() => handleToggleContentColumn(col.name)}
                                            />
                                            <span className={col.is_text ? 'text-col' : ''}>{col.name}</span>
                                            <span className="col-type">{col.type}</span>
                                          </label>
                                        ))}
                                      </div>
                                    </div>
                                    <div className="column-group">
                                      <h4>Metadata Columns (for filtering)</h4>
                                      <div className="columns-checkboxes">
                                        {tableColumns.map(col => (
                                          <label key={col.name} className="column-checkbox">
                                            <input
                                              type="checkbox"
                                              checked={dbImportConfig.metadata_columns.includes(col.name)}
                                              onChange={() => handleToggleMetadataColumn(col.name)}
                                            />
                                            <span className={col.is_key ? 'text-col' : ''}>{col.name}</span>
                                            <span className="col-type">{col.type}</span>
                                          </label>
                                        ))}
                                      </div>
                                    </div>
                                  </div>
                                )}

                                {/* Preview */}
                                {tablePreview && (
                                  <div className="table-preview">
                                    <div className="panel-header">
                                      Preview (first {tablePreview.rows?.length || 0} of {tablePreview.total_count?.toLocaleString()} rows)
                                    </div>
                                    <div className="preview-scroll">
                                      <table className="preview-table">
                                        <thead>
                                          <tr>
                                            {tablePreview.columns?.map((col: string) => (
                                              <th key={col}>{col}</th>
                                            ))}
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {tablePreview.rows?.map((row, idx) => (
                                            <tr key={idx}>
                                              {tablePreview.columns?.map((col) => (
                                                <td key={col}>
                                                  {String(row[col] ?? '').substring(0, 100)}
                                                  {String(row[col] ?? '').length > 100 ? '...' : ''}
                                                </td>
                                              ))}
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  </div>
                                )}

                                {/* Import Settings */}
                                <div className="import-settings">
                                  <div className="form-row">
                                    <div className="form-group">
                                      <label>Collection Name *</label>
                                      <input
                                        type="text"
                                        value={dbImportConfig.collection_name}
                                        onChange={e => setDbImportConfig({ ...dbImportConfig, collection_name: e.target.value })}
                                        placeholder="Collection name"
                                      />
                                    </div>
                                    <div className="form-group">
                                      <label>Domain *</label>
                                      <select
                                        value={dbImportConfig.domain}
                                        onChange={e => setDbImportConfig({ ...dbImportConfig, domain: e.target.value })}
                                      >
                                        {domains.map(d => (
                                          <option key={d.id} value={d.id}>{d.name}</option>
                                        ))}
                                      </select>
                                    </div>
                                  </div>

                                  <div className="form-group">
                                    <label>Description</label>
                                    <input
                                      type="text"
                                      value={dbImportConfig.description}
                                      onChange={e => setDbImportConfig({ ...dbImportConfig, description: e.target.value })}
                                      placeholder="Brief description..."
                                    />
                                  </div>

                                  <div className="form-group">
                                    <label className="checkbox-label">
                                      <input
                                        type="checkbox"
                                        checked={dbImportConfig.save_connection}
                                        onChange={e => setDbImportConfig({ ...dbImportConfig, save_connection: e.target.checked })}
                                      />
                                      Save connection settings
                                    </label>
                                    {dbImportConfig.save_connection && (
                                      <input
                                        type="text"
                                        value={dbImportConfig.connection_name}
                                        onChange={e => setDbImportConfig({ ...dbImportConfig, connection_name: e.target.value })}
                                        placeholder="Connection name"
                                        className="connection-name-input"
                                      />
                                    )}
                                  </div>

                                  <button
                                    className="btn-primary btn-lg"
                                    onClick={handleImportDatabase}
                                    disabled={dbImporting || !selectedTable}
                                  >
                                    {dbImporting ? 'Starting Import...' : 'Start Import'}
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Jobs Tab */}
            {activeTab === 'jobs' && (
              <div className="tab-content">
                <div className="section-header">
                  <h2>Import Jobs</h2>
                  <button className="btn-secondary" onClick={fetchImportJobs}>
                    Refresh
                  </button>
                </div>

                <div className="jobs-list">
                  {importJobs.map(job => {
                    const statusStyle = getStatusBadge(job.status);
                    return (
                      <div key={job.id} className="job-card">
                        <div className="job-header">
                          <div>
                            <h4>{job.collection_name}</h4>
                            <span className="job-type">{job.source_type.toUpperCase()}</span>
                          </div>
                          <span
                            className="status-badge"
                            style={{ background: statusStyle.bg, color: statusStyle.color }}
                          >
                            {job.status}
                          </span>
                        </div>

                        {job.status === 'running' && (
                          <div className="progress-bar">
                            <div
                              className="progress-fill"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                        )}

                        <div className="job-details">
                          <span>
                            {job.processed_items.toLocaleString()} / {job.total_items.toLocaleString()} items
                          </span>
                          {job.started_at && (
                            <span>Started: {new Date(job.started_at).toLocaleString()}</span>
                          )}
                          {job.completed_at && (
                            <span>Completed: {new Date(job.completed_at).toLocaleString()}</span>
                          )}
                        </div>

                        {job.error_message && (
                          <div className="job-error">
                            Error: {job.error_message}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {importJobs.length === 0 && (
                    <div className="empty-state">
                      <p>No import jobs found.</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Create Collection Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Create New Collection</h3>
              <button onClick={() => setShowCreateModal(false)} className="modal-close">&times;</button>
            </div>
            <div className="modal-content">
              <div className="form-group">
                <label>Collection Name *</label>
                <input
                  type="text"
                  value={newCollection.name}
                  onChange={e => setNewCollection({ ...newCollection, name: e.target.value })}
                  placeholder="e.g., hotel_accounting"
                />
              </div>

              <div className="form-group">
                <label>Domain *</label>
                <select
                  value={newCollection.domain}
                  onChange={e => setNewCollection({ ...newCollection, domain: e.target.value })}
                >
                  {domains.map(d => (
                    <option key={d.id} value={d.id}>{d.name} - {d.description}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={newCollection.description}
                  onChange={e => setNewCollection({ ...newCollection, description: e.target.value })}
                  placeholder="Brief description of this collection..."
                  rows={3}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowCreateModal(false)} className="btn-secondary">
                Cancel
              </button>
              <button onClick={handleCreateCollection} className="btn-primary">
                Create Collection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CollectionManagerPage;
