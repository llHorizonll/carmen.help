import React, { useState, useRef, useEffect } from 'react';
import Chat, { Bubble, useMessages } from '@chatui/core';

const SUGGESTIONS = [
  'How do I set up billing?',
  'What is the site policy?',
  'How do I create a new project?',
];

const App: React.FC = () => {
  const { messages, appendMsg, setTyping } = useMessages([]);
  const [isOpen, setIsOpen] = useState(false);

  const handleSend = async (type: string, val: string) => {
    if (type === 'text' && val.trim()) {
      appendMsg({
        type: 'text',
        content: { text: val },
        position: 'right',
      });

      setTyping(true);

      try {
        const response = await fetch('/api/chat/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: val, stream: false }),
        });

        const data = await response.json();

        let responseText = data.answer || data.response || 'I could not process your request.';

        // Add source citations
        if (data.sources && data.sources.length > 0) {
          responseText += '\n\n**Sources:**\n';
          data.sources.forEach((source: any, i: number) => {
            const url = source.source_url || `https://docscarmencloud.vercel.app/${source.id}`;
            responseText += `${i + 1}. [${source.id || 'Documentation'}](${url})\n`;
          });
        }

        appendMsg({
          type: 'text',
          content: { text: responseText },
          position: 'left',
        });
      } catch (error) {
        appendMsg({
          type: 'text',
          content: { text: 'Sorry, I encountered an error. Please try again.' },
          position: 'left',
        });
      }

      setTyping(false);
    }
  };

  const renderMessageContent = (msg: any) => {
    const { content } = msg;
    return <Bubble content={content.text} />;
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
        padding: '16px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
      }}>
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
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#28A745' }}></span>
            Online
          </div>
        </div>
      </div>

      {/* Chat */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Chat
          messages={messages}
          renderMessageContent={renderMessageContent}
          onSend={handleSend}
          placeholder="Type your message..."
          quickReplies={messages.length === 0 ? SUGGESTIONS.map(s => ({ name: s })) : []}
          onQuickReplyClick={handleQuickReply}
        />
      </div>
    </div>
  );
};

export default App;
