import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Chat from '@chatui/core';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatContext } from '../context/ChatContext';

const SUGGESTIONS = [
  {
    text: "ขอดูรายการหนี้ค้างชำระ (AR Aging) ที่เกินกำหนด 30 วัน",
    icon: "📊",
  },
  {
    text: "มีบิลค่าใช้จ่าย (AP) ใบไหนที่รออนุมัติการจ่ายเงินบ้าง?",
    icon: "📋",
  },
  {
    text: "ขอวิธีแก้ไขกรณีมียอดหนี้ค้างชำระ (AR) เกิน 90 วัน",
    icon: "💡",
  },
  {
    text: "มีข้อผิดพลาด (Error) หรือปัญหา (Issue) อะไรที่พบในระบบ PMS บ้าง?",
    icon: "⚠️",
  },
  {
    text: "ขอดูรายงานสรุปค่าใช้จ่าย (Expense Report) ประจำเดือนล่าสุด",
    icon: "📈",
  },
  {
    text: "ช่วยแนะนำวิธีเพิ่มประสิทธิภาพการจัดการหนี้ค้างชำระ",
    icon: "🎯",
  },
];

// Suggestion Carousel Component
interface SuggestionCarouselProps {
  suggestions: typeof SUGGESTIONS;
  onSelect: (text: string) => void;
}

const SuggestionCarousel: React.FC<SuggestionCarouselProps> = ({ suggestions, onSelect }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScroll = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
    }
  };

  useEffect(() => {
    checkScroll();
    const el = scrollRef.current;
    if (el) {
      el.addEventListener('scroll', checkScroll);
      return () => el.removeEventListener('scroll', checkScroll);
    }
  }, []);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const scrollAmount = 280;
      scrollRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  return (
    <div className="suggestion-carousel">
      <div className="suggestion-carousel-header">
        <span className="suggestion-carousel-title">💡 คำถามแนะนำ</span>
        <div className="suggestion-carousel-nav">
          <button
            type="button"
            className={`carousel-nav-btn ${!canScrollLeft ? 'disabled' : ''}`}
            onClick={() => scroll('left')}
            disabled={!canScrollLeft}
            aria-label="เลื่อนซ้าย"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          <button
            type="button"
            className={`carousel-nav-btn ${!canScrollRight ? 'disabled' : ''}`}
            onClick={() => scroll('right')}
            disabled={!canScrollRight}
            aria-label="เลื่อนขวา"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        </div>
      </div>
      <div className="suggestion-carousel-track" ref={scrollRef}>
        {suggestions.map((suggestion, idx) => (
          <button
            type="button"
            key={idx}
            className="suggestion-card"
            onClick={() => onSelect(suggestion.text)}
          >
            <span className="suggestion-card-icon">{suggestion.icon}</span>
            <span className="suggestion-card-text">{suggestion.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

interface UsageStats {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  response_time_ms: number;
}

interface SourceInfo {
  id: string;
  content: string;
  score: number;
  source_url?: string;
  domain?: string;
  collection?: string;
  metadata?: Record<string, any>;
}

interface CollectionBreakdown {
  collection: string;
  domain: string;
  count: number;
}

// Domain display names
const DOMAIN_NAMES: Record<string, string> = {
  budget: 'Budget',
  usali: 'USALI',
  hotel_operations: 'Hotel Ops',
  general_docs: 'Docs',
  faq: 'FAQ',
  custom: 'Custom',
};

// Get domain badge class
const getDomainBadgeClass = (domain: string): string => {
  return `domain-badge domain-badge--${domain || 'custom'}`;
};

interface ClarificationOption {
  text: string;
  query: string;
}

const formatResponseTime = (ms: number): string => {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

// Parse clarification options from response
const parseClarifications = (text: string): { cleanText: string; options: ClarificationOption[] } => {
  let options: ClarificationOption[] = [];
  let cleanText = text;

  // Check for [CLARIFY] blocks
  const clarifyMatch = text.match(/\[CLARIFY\]([\s\S]*?)\[\/CLARIFY\]/);
  if (clarifyMatch) {
    const optionsText = clarifyMatch[1];
    const optionLines = optionsText.trim().split('\n').filter(line => line.trim());
    options = optionLines.map(line => {
      const cleaned = line.replace(/^[-•*]\s*/, '').trim();
      return { text: cleaned, query: cleaned };
    });
    cleanText = text.replace(/\[CLARIFY\][\s\S]*?\[\/CLARIFY\]/, '').trim();
  }

  return { cleanText, options };
};

// Custom markdown components
const MarkdownComponents = {
  table: ({ children }: any) => (
    <div style={{ overflowX: 'auto', margin: '16px 0' }}>
      <table>{children}</table>
    </div>
  ),
  img: ({ src, alt }: any) => (
    <img
      src={src}
      alt={alt || 'Image'}
      style={{
        maxWidth: '100%',
        height: 'auto',
        borderRadius: '12px',
        margin: '12px 0',
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
      }}
    />
  ),
  a: ({ href, children }: any) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{ color: 'var(--primary-color)', fontWeight: 500 }}
    >
      {children}
    </a>
  ),
  code: ({ inline, children }: any) => {
    if (inline) {
      return (
        <code style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '13px',
          background: '#f0f2f5',
          padding: '2px 6px',
          borderRadius: '4px',
          color: '#DC3545',
        }}>
          {children}
        </code>
      );
    }
    return (
      <pre style={{
        background: '#1e1e2e',
        color: '#cdd6f4',
        padding: '16px',
        borderRadius: '12px',
        overflow: 'auto',
        margin: '12px 0',
        fontSize: '13px',
      }}>
        <code>{children}</code>
      </pre>
    );
  },
};

const ChatPage: React.FC = () => {
  const {
    messages,
    messageUsage,
    lastUsage,
    isStreaming,
    addMessage,
    updateMessage,
    updateMessageUsage,
    setLastUsage,
    setIsStreaming,
    clearChat,
  } = useChatContext();

  const [showUsageTooltip, setShowUsageTooltip] = useState(false);
  const [typing, setTyping] = useState(false);
  const [waitingForResponse, setWaitingForResponse] = useState(false);
  const currentResponseRef = useRef<{ text: string; messageId: string | null }>({ text: '', messageId: null });

  // Scroll to bottom when messages change
  useEffect(() => {
    const chatContainer = document.querySelector('.MessageList');
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (type: string, val: string) => {
    if (type === 'text' && val.trim()) {
      // Add user message with stable ID
      const userMessageId = `user-${Date.now()}`;
      addMessage({
        type: 'text',
        content: { text: val },
        position: 'right',
        _id: userMessageId,
      });

      setTyping(true);
      setWaitingForResponse(true);
      setLastUsage(null);
      setIsStreaming(true);

      const responseMessageId = `assistant-${Date.now()}`;
      currentResponseRef.current = { text: '', messageId: null };

      try {
        const response = await fetch('/api/chat/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: val, stream: true }),
        });

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        let fullText = '';
        let sources: SourceInfo[] = [];
        let collectionBreakdown: CollectionBreakdown[] = [];
        let domains: string[] = [];
        let usage: UsageStats | null = null;

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));

                  if (data.type === 'chunk') {
                    fullText += data.content;
                    currentResponseRef.current.text = fullText;

                    // Create message on first chunk
                    if (!currentResponseRef.current.messageId) {
                      currentResponseRef.current.messageId = responseMessageId;
                      setWaitingForResponse(false);
                      addMessage({
                        type: 'text',
                        content: { text: fullText },
                        position: 'left',
                        _id: responseMessageId,
                      });
                    } else {
                      // Update message in state for real-time streaming
                      updateMessage(responseMessageId, fullText);
                    }
                  } else if (data.type === 'sources') {
                    sources = data.sources || [];
                    domains = data.domains || [];
                    collectionBreakdown = data.collection_breakdown || [];
                  } else if (data.type === 'usage') {
                    usage = {
                      prompt_tokens: data.prompt_tokens || 0,
                      completion_tokens: data.completion_tokens || 0,
                      total_tokens: data.total_tokens || 0,
                      response_time_ms: data.response_time_ms || 0,
                    };
                  } else if (data.type === 'done') {
                    // Add sources to final message with domain badges
                    if (sources.length > 0) {
                      fullText += '\n\n---\n**อ้างอิง:**\n';
                      sources.forEach((source: SourceInfo) => {
                        const url = source.source_url || `https://docscarmencloud.vercel.app/${source.id}`;
                        const domainLabel = source.domain ? `[${DOMAIN_NAMES[source.domain] || source.domain}] ` : '';
                        fullText += `- ${domainLabel}[${source.id || 'Documentation'}](${url})\n`;
                      });

                      // Add collection breakdown if multiple collections used
                      if (collectionBreakdown.length > 1) {
                        fullText += '\n**แหล่งข้อมูล:**\n';
                        collectionBreakdown.forEach((stat) => {
                          const domainName = DOMAIN_NAMES[stat.domain] || stat.domain;
                          fullText += `- ${stat.collection} (${domainName}): ${stat.count} รายการ\n`;
                        });
                      }

                      // Update final message with sources in state
                      updateMessage(responseMessageId, fullText);
                    }

                    // Update usage stats
                    if (usage) {
                      setLastUsage(usage);
                      updateMessageUsage(responseMessageId, usage);
                    }
                  } else if (data.type === 'error') {
                    fullText = `❌ **Error:** ${data.message}`;
                  }
                } catch (e) {
                  // Skip invalid JSON
                }
              }
            }
          }
        }

        // Fallback if no message was created
        if (!currentResponseRef.current.messageId && !fullText) {
          addMessage({
            type: 'text',
            content: { text: '❌ ไม่สามารถประมวลผลคำขอของคุณได้ กรุณาลองใหม่อีกครั้ง' },
            position: 'left',
          });
        }
      } catch (error) {
        console.error('Chat error:', error);
        addMessage({
          type: 'text',
          content: { text: '❌ เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง' },
          position: 'left',
        });
      } finally {
        setIsStreaming(false);
        setTyping(false);
        setWaitingForResponse(false);
      }
    }
  };

  const handleClearChat = () => {
    clearChat();
  };

  const handleClarificationClick = (query: string) => {
    handleSend('text', query);
  };

  const renderMessageContent = (msg: any) => {
    const { content, position, _id } = msg;
    const isAssistant = position === 'left';
    const usage = _id ? messageUsage[_id] : undefined;

    // Parse clarifications from the message
    const { cleanText, options } = isAssistant
      ? parseClarifications(content.text)
      : { cleanText: content.text, options: [] };

    return (
      <div style={{ maxWidth: '100%' }}>
        {isAssistant ? (
          <div className="markdown-content" style={{
            background: 'white',
            padding: '16px 20px',
            borderRadius: '18px 18px 18px 4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
            border: '1px solid #e4e6eb',
          }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={MarkdownComponents}
            >
              {cleanText}
            </ReactMarkdown>

            {/* Clarification options */}
            {options.length > 0 && (
              <div className="clarification-card">
                <div className="clarification-card-header">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                  กรุณาเลือกข้อมูลที่ต้องการ
                </div>
                <div className="clarification-options">
                  {options.map((opt, idx) => (
                    <button
                      type="button"
                      key={idx}
                      className="clarification-option"
                      onClick={() => handleClarificationClick(opt.query)}
                    >
                      <span className="clarification-option-icon">{idx + 1}</span>
                      {opt.text}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{
            background: 'linear-gradient(135deg, #0066CC 0%, #0052A3 100%)',
            color: 'white',
            padding: '14px 18px',
            borderRadius: '18px 18px 4px 18px',
            fontSize: '15px',
            lineHeight: '1.6',
          }}>
            {content.text}
          </div>
        )}

        {/* Usage stats for assistant messages */}
        {isAssistant && usage && (
          <div className="usage-stats-badge">
            <div className="usage-stat">
              <svg className="usage-stat-icon" viewBox="0 0 24 24" fill="none" stroke="#0066CC" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
              <span className="usage-stat-value" style={{ color: '#0066CC' }}>
                {formatResponseTime(usage.response_time_ms)}
              </span>
            </div>

            <div className="usage-stat">
              <svg className="usage-stat-icon" viewBox="0 0 24 24" fill="none" stroke="#28A745" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
              <span>
                <span className="usage-stat-value">{usage.total_tokens.toLocaleString()}</span>
                <span style={{ color: '#8a8d91', marginLeft: '4px', fontSize: '10px' }}>
                  ({usage.prompt_tokens.toLocaleString()} + {usage.completion_tokens.toLocaleString()})
                </span>
              </span>
            </div>
          </div>
        )}
      </div>
    );
  };

  const handleSuggestionSelect = (text: string) => {
    handleSend('text', text);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#f0f2f5' }}>
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-info">
          <div className="chat-header-avatar">CA</div>
          <div>
            <div className="chat-header-title">Carmen AI Assistant</div>
            <div className="chat-header-status">
              <span className={`status-dot ${isStreaming ? 'status-dot--typing' : 'status-dot--online'}`}></span>
              {isStreaming ? 'กำลังพิมพ์...' : 'ออนไลน์'}
            </div>
          </div>
        </div>

        <div className="chat-header-actions">
          <button
            type="button"
            onClick={handleClearChat}
            className="header-btn"
            title="ล้างประวัติการสนทนา"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
            </svg>
            <span>ล้างแชท</span>
          </button>

          <Link to="/stats" className="header-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 20V10M12 20V4M6 20v-6" />
            </svg>
            <span>สถิติ</span>
          </Link>
        </div>
      </header>

      {/* Chat */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        <Chat
          messages={[
            ...messages.map((msg, idx) => ({
              ...msg,
              _id: msg._id || `msg-${idx}`,
            })),
            // Add typing indicator as a message when waiting
            ...(waitingForResponse ? [{
              type: 'text',
              content: { text: '' },
              position: 'left' as const,
              _id: 'typing-indicator',
            }] : []),
          ]}
          renderMessageContent={(msg: any) => {
            // Render typing indicator
            if (msg._id === 'typing-indicator') {
              return (
                <div className="typing-indicator">
                  <div className="dot"></div>
                  <div className="dot"></div>
                  <div className="dot"></div>
                </div>
              );
            }
            return renderMessageContent(msg);
          }}
          onSend={handleSend}
          placeholder="พิมพ์ข้อความของคุณ..."
          locale="th-TH"
        />

        {/* Custom Suggestion Carousel */}
        {messages.length === 0 && (
          <SuggestionCarousel
            suggestions={SUGGESTIONS}
            onSelect={handleSuggestionSelect}
          />
        )}

        {/* Welcome message when empty */}
        {messages.length === 0 && (
          <div style={{
            position: 'absolute',
            top: '20%',
            left: '50%',
            transform: 'translateX(-50%)',
            textAlign: 'center',
            pointerEvents: 'none',
          }}>
            <div style={{
              width: '80px',
              height: '80px',
              background: 'linear-gradient(135deg, #E6F0FA 0%, #fff 100%)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
              boxShadow: '0 4px 20px rgba(0, 102, 204, 0.15)',
            }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#0066CC" strokeWidth="1.5">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
              </svg>
            </div>
            <h2 style={{
              fontSize: '22px',
              fontWeight: 600,
              color: '#1a1a2e',
              marginBottom: '8px',
            }}>
              สวัสดีครับ! ยินดีต้อนรับ 👋
            </h2>
            <p style={{
              fontSize: '15px',
              color: '#65676b',
              maxWidth: '320px',
              lineHeight: '1.6',
            }}>
              ผมคือ Carmen AI Assistant พร้อมช่วยเหลือคุณ
              <br />เลือกคำถามด้านล่างหรือพิมพ์ข้อความได้เลยครับ
            </p>
          </div>
        )}

        {/* Usage Stats Floating Button */}
        {lastUsage && (
          <div
            style={{
              position: 'absolute',
              bottom: '80px',
              right: '20px',
              zIndex: 100,
            }}
          >
            {/* Tooltip */}
            {showUsageTooltip && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '55px',
                  right: '0',
                  background: 'white',
                  borderRadius: '16px',
                  boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
                  padding: '20px',
                  minWidth: '240px',
                  fontSize: '14px',
                  animation: 'fadeIn 0.2s ease',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '16px', color: '#1a1a2e', fontSize: '15px' }}>
                  📊 สถิติการใช้งาน
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#65676b' }}>Input tokens</span>
                    <span style={{ fontWeight: 600, color: '#1a1a2e' }}>{lastUsage.prompt_tokens.toLocaleString()}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#65676b' }}>Output tokens</span>
                    <span style={{ fontWeight: 600, color: '#1a1a2e' }}>{lastUsage.completion_tokens.toLocaleString()}</span>
                  </div>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderTop: '1px solid #e4e6eb',
                    paddingTop: '12px',
                    marginTop: '4px',
                  }}>
                    <span style={{ color: '#1a1a2e', fontWeight: 500 }}>Total tokens</span>
                    <span style={{ fontWeight: 700, color: '#0066CC', fontSize: '16px' }}>
                      {lastUsage.total_tokens.toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#65676b' }}>เวลาตอบกลับ</span>
                    <span style={{ fontWeight: 600, color: '#28A745' }}>
                      {formatResponseTime(lastUsage.response_time_ms)}
                    </span>
                  </div>
                </div>
                {/* Arrow */}
                <div
                  style={{
                    position: 'absolute',
                    bottom: '-8px',
                    right: '20px',
                    width: '0',
                    height: '0',
                    borderLeft: '8px solid transparent',
                    borderRight: '8px solid transparent',
                    borderTop: '8px solid white',
                  }}
                />
              </div>
            )}

            {/* Floating Button */}
            <button
              type="button"
              onClick={() => setShowUsageTooltip(!showUsageTooltip)}
              onMouseEnter={() => setShowUsageTooltip(true)}
              onMouseLeave={() => setShowUsageTooltip(false)}
              style={{
                width: '52px',
                height: '52px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #0066CC 0%, #0052A3 100%)',
                border: 'none',
                boxShadow: '0 4px 15px rgba(0, 102, 204, 0.35)',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                transition: 'transform 0.2s, box-shadow 0.2s',
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.transform = 'scale(1.08)';
                e.currentTarget.style.boxShadow = '0 6px 20px rgba(0, 102, 204, 0.45)';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
                e.currentTarget.style.boxShadow = '0 4px 15px rgba(0, 102, 204, 0.35)';
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
              <span style={{ fontSize: '9px', marginTop: '2px', fontWeight: 600 }}>
                {formatResponseTime(lastUsage.response_time_ms).replace('ms', '').replace('s', '')}
              </span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatPage;
