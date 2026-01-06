import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './StatsPage.css';

interface ChatStats {
  total_sessions: number;
  total_messages: number;
  messages_by_role: {
    user?: number;
    assistant?: number;
  };
  sessions_today: number;
  db_path: string;
}

interface ChatSession {
  id: string;
  user_id: string | null;
  created_at: string;
  updated_at: string;
}

interface ChatMessage {
  id: string;
  role: string;
  content: string;
  sources: any[] | null;
  timestamp: string;
}

const StatsPage: React.FC = () => {
  const [stats, setStats] = useState<ChatStats | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [sessionMessages, setSessionMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
    fetchSessions();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/chat/stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      setError('Failed to load statistics');
    }
  };

  const fetchSessions = async () => {
    try {
      const response = await fetch('/api/chat/sessions?limit=50');
      const data = await response.json();
      setSessions(data.sessions || []);
    } catch (err) {
      setError('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  const fetchSessionMessages = async (sessionId: string) => {
    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}`);
      const data = await response.json();
      setSessionMessages(data.messages || []);
      setSelectedSession(sessionId);
    } catch (err) {
      setError('Failed to load session messages');
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!confirm('Are you sure you want to delete this session?')) return;

    try {
      await fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions(sessions.filter(s => s.id !== sessionId));
      if (selectedSession === sessionId) {
        setSelectedSession(null);
        setSessionMessages([]);
      }
      fetchStats();
    } catch (err) {
      setError('Failed to delete session');
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <div className="stats-page">
      {/* Header */}
      <div className="header">
        <div className="header-content">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 20V10M12 20V4M6 20v-6" />
          </svg>
          <div>
            <div className="header-title">Chat Log Statistics</div>
            <div className="header-subtitle">View conversation history and analytics</div>
          </div>
        </div>

        {/* Back to Chat */}
        <Link to="/" className="back-link">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back to Chat
        </Link>
      </div>

      {/* Content */}
      <div className="content">
        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        {/* Stats Cards */}
        {stats && (
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">Total Sessions</div>
              <div className={`stat-value stat-value-blue`}>
                {stats.total_sessions.toLocaleString()}
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Total Messages</div>
              <div className={`stat-value stat-value-green`}>
                {stats.total_messages.toLocaleString()}
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Sessions Today</div>
              <div className={`stat-value stat-value-orange`}>
                {stats.sessions_today.toLocaleString()}
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Messages by Role</div>
              <div style={{ display: 'flex', gap: '16px', marginTop: '8px' }}>
                <div>
                  <span className="role-label">User: </span>
                  <span className="role-value">{stats.messages_by_role.user || 0}</span>
                </div>
                <div>
                  <span className="role-label">Assistant: </span>
                  <span className="role-value">{stats.messages_by_role.assistant || 0}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Sessions and Messages */}
        <div className={`messages-panel ${selectedSession ? 'with-session' : ''}`}>
          {/* Sessions List */}
          <div className="sessions-list">
            <div className="panel-header">
              Recent Sessions ({sessions.length})
            </div>

            {loading ? (
              <div className="loading-state">
                Loading...
              </div>
            ) : sessions.length === 0 ? (
              <div className="empty-state">
                No sessions found
              </div>
            ) : (
              <div className="sessions-container">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => fetchSessionMessages(session.id)}
                    className={`session-item ${selectedSession === session.id ? 'active' : ''}`}
                  >
                    <div className="session-item-content">
                      <div>
                        <div className="session-id">
                          {session.id.substring(0, 8)}...
                        </div>
                        <div className="session-date">
                          {formatDate(session.updated_at)}
                        </div>
                        {session.user_id && (
                          <div className="session-user">
                            User: {session.user_id}
                          </div>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteSession(session.id);
                        }}
                        className="delete-button"
                        aria-label="Delete session"
                        title="Delete session"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Messages Panel */}
          {selectedSession && (
            <div className="sessions-list">
              <div className="panel-header panel-header-with-actions">
                <span>Conversation ({sessionMessages.length} messages)</span>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedSession(null);
                    setSessionMessages([]);
                  }}
                  className="close-button"
                  aria-label="Close conversation"
                  title="Close conversation"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="messages-container">
                {sessionMessages.map((message) => (
                  <div
                    key={message.id}
                    className={`message ${message.role}`}
                  >
                    <div className="message-meta">
                      {message.role === 'user' ? 'User' : 'Assistant'} - {formatDate(message.timestamp)}
                    </div>
                    <div className={`message-bubble ${message.role}`}>
                      {truncateText(message.content, 500)}
                    </div>
                    {message.sources && message.sources.length > 0 && (
                      <div className="message-sources">
                        {message.sources.length} source(s) cited
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StatsPage;
