import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Chat, { Bubble } from '@chatui/core';
import { useChatContext } from '../context/ChatContext';

const SUGGESTIONS = [
  'How do I reconcile a bank statement in Carmen?',
  'Show me all pending Accounts Payable invoices for approval.',
  'What is the current status of the City Ledger from the PMS?',
];

interface UsageStats {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  response_time_ms: number;
}

const formatResponseTime = (ms: number): string => {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
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
        let sources: any[] = [];
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
                  } else if (data.type === 'usage') {
                    usage = {
                      prompt_tokens: data.prompt_tokens || 0,
                      completion_tokens: data.completion_tokens || 0,
                      total_tokens: data.total_tokens || 0,
                      response_time_ms: data.response_time_ms || 0,
                    };
                  } else if (data.type === 'done') {
                    // Add sources to final message
                    if (sources.length > 0) {
                      fullText += '\n\n**Sources:**\n';
                      sources.forEach((source: any, i: number) => {
                        const url = source.source_url || `https://docscarmencloud.vercel.app/${source.id}`;
                        fullText += `${i + 1}. [${source.id || 'Documentation'}](${url})\n`;
                      });
                      // Update final message with sources in state
                      updateMessage(responseMessageId, fullText);
                    }

                    // Update usage stats
                    if (usage) {
                      setLastUsage(usage);
                      updateMessageUsage(responseMessageId, usage);
                    }
                  } else if (data.type === 'error') {
                    fullText = `Error: ${data.message}`;
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
            content: { text: 'I could not process your request.' },
            position: 'left',
          });
        }
      } catch (error) {
        console.error('Chat error:', error);
        addMessage({
          type: 'text',
          content: { text: 'Sorry, I encountered an error. Please try again.' },
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

  const renderMessageContent = (msg: any) => {
    const { content, position, _id } = msg;
    const isAssistant = position === 'left';
    const usage = _id ? messageUsage[_id] : undefined;

    return (
      <div>
        <Bubble content={content.text} />
        {isAssistant && usage && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginTop: '8px',
            padding: '8px 12px',
            background: '#f8f9fa',
            borderRadius: '8px',
            fontSize: '11px',
            color: '#666',
          }}>
            {/* Clock icon for time */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0066CC" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
              <span style={{ fontWeight: 500, color: '#0066CC' }}>
                {formatResponseTime(usage.response_time_ms)}
              </span>
            </div>

            {/* Token icon */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#28A745" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
              <span style={{ color: '#333' }}>
                <span style={{ fontWeight: 500 }}>{usage.total_tokens.toLocaleString()}</span>
                <span style={{ color: '#999', marginLeft: '4px' }}>
                  ({usage.prompt_tokens.toLocaleString()} + {usage.completion_tokens.toLocaleString()})
                </span>
              </span>
            </div>
          </div>
        )}
      </div>
    );
  };

  const handleQuickReply = (item: any) => {
    handleSend('text', item.name);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        background: '#0066CC',
        color: 'white',
        padding: '12px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            background: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#0066CC',
            fontWeight: 'bold',
          }}>
            CA
          </div>
          <div>
            <div style={{ fontWeight: 600 }}>Carmen AI Assistant</div>
            <div style={{ fontSize: '12px', opacity: 0.9, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: isStreaming ? '#FFC107' : '#28A745',
                animation: isStreaming ? 'pulse 1s infinite' : 'none',
              }}></span>
              {isStreaming ? 'Typing...' : 'Online'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {/* Clear Chat Button */}
          <button
            type="button"
            onClick={handleClearChat}
            style={{
              color: 'white',
              background: 'rgba(255,255,255,0.15)',
              border: 'none',
              padding: '8px 12px',
              borderRadius: '6px',
              fontSize: '14px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Clear chat history"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
            </svg>
          </button>

          {/* Navigation */}
          <Link
            to="/stats"
            style={{
              color: 'white',
              textDecoration: 'none',
              padding: '8px 16px',
              background: 'rgba(255,255,255,0.15)',
              borderRadius: '6px',
              fontSize: '14px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 20V10M12 20V4M6 20v-6" />
            </svg>
            Statistics
          </Link>
        </div>
      </div>

      {/* Chat */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        <style>
          {`
            @keyframes pulse {
              0%, 100% { opacity: 1; }
              50% { opacity: 0.5; }
            }
            @keyframes bounce {
              0%, 60%, 100% { transform: translateY(0); }
              30% { transform: translateY(-8px); }
            }
            .typing-indicator {
              display: flex;
              align-items: center;
              gap: 6px;
              padding: 16px 20px;
              background: #f0f0f0;
              border-radius: 18px;
              width: fit-content;
            }
            .typing-indicator .dot {
              width: 8px;
              height: 8px;
              background: #666;
              border-radius: 50%;
              animation: bounce 1.4s infinite ease-in-out;
            }
            .typing-indicator .dot:nth-child(1) { animation-delay: 0s; }
            .typing-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
            .typing-indicator .dot:nth-child(3) { animation-delay: 0.4s; }
          `}
        </style>
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
          placeholder="Type your message..."
          locale="en-US"
          quickReplies={messages.length === 0 ? SUGGESTIONS.map(s => ({ name: s })) : []}
          onQuickReplyClick={handleQuickReply}
        />

        {/* Usage Stats Bubble */}
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
                  bottom: '50px',
                  right: '0',
                  background: 'white',
                  borderRadius: '12px',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                  padding: '16px',
                  minWidth: '220px',
                  fontSize: '13px',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '12px', color: '#333' }}>
                  Usage Statistics
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#666' }}>Input tokens:</span>
                    <span style={{ fontWeight: 500 }}>{lastUsage.prompt_tokens.toLocaleString()}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#666' }}>Output tokens:</span>
                    <span style={{ fontWeight: 500 }}>{lastUsage.completion_tokens.toLocaleString()}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #eee', paddingTop: '8px' }}>
                    <span style={{ color: '#333', fontWeight: 500 }}>Total tokens:</span>
                    <span style={{ fontWeight: 600, color: '#0066CC' }}>{lastUsage.total_tokens.toLocaleString()}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#666' }}>Response time:</span>
                    <span style={{ fontWeight: 500, color: '#28A745' }}>{formatResponseTime(lastUsage.response_time_ms)}</span>
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

            {/* Bubble Button */}
            <button
              type="button"
              onClick={() => setShowUsageTooltip(!showUsageTooltip)}
              onMouseEnter={() => setShowUsageTooltip(true)}
              onMouseLeave={() => setShowUsageTooltip(false)}
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #0066CC 0%, #0052A3 100%)',
                border: 'none',
                boxShadow: '0 4px 12px rgba(0,102,204,0.3)',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                transition: 'transform 0.2s, box-shadow 0.2s',
              }}
              onFocus={(e) => {
                e.currentTarget.style.transform = 'scale(1.05)';
                e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,102,204,0.4)';
              }}
              onBlur={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,102,204,0.3)';
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
              <span style={{ fontSize: '9px', marginTop: '2px' }}>
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
