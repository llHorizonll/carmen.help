import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface UsageStats {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  response_time_ms: number;
}

interface ChatMessage {
  type: string;
  content: { text: string };
  position: 'left' | 'right';
  _id?: string;
}

interface ChatContextType {
  messages: ChatMessage[];
  messageUsage: Record<string, UsageStats>;
  lastUsage: UsageStats | null;
  isStreaming: boolean;
  addMessage: (msg: ChatMessage) => void;
  updateMessage: (messageId: string, content: string) => void;
  updateMessageUsage: (messageId: string, usage: UsageStats) => void;
  setLastUsage: (usage: UsageStats | null) => void;
  setIsStreaming: (streaming: boolean) => void;
  clearChat: () => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messageUsage, setMessageUsage] = useState<Record<string, UsageStats>>({});
  const [lastUsage, setLastUsage] = useState<UsageStats | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages(prev => [...prev, msg]);
  }, []);

  const updateMessage = useCallback((messageId: string, content: string) => {
    setMessages(prev => prev.map(msg =>
      msg._id === messageId
        ? { ...msg, content: { text: content } }
        : msg
    ));
  }, []);

  const updateMessageUsage = useCallback((messageId: string, usage: UsageStats) => {
    setMessageUsage(prev => ({ ...prev, [messageId]: usage }));
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    setMessageUsage({});
    setLastUsage(null);
  }, []);

  return (
    <ChatContext.Provider value={{
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
    }}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChatContext = (): ChatContextType => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
};
