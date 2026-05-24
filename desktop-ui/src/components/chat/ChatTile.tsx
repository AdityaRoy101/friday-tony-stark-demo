import { useRef, useEffect, useMemo } from 'react';
import { useChat, useTranscriptions } from '@livekit/components-react';
import { ConnectionState } from 'livekit-client';
import type { FridayDebugState } from '../../lib/types';
import { formatTimestamp } from '../../lib/utils';
import ChatMessageInput from './ChatMessageInput';

interface ChatTileProps {
  connectionState: ConnectionState;
  debug?: FridayDebugState;
}

interface VisibleMessage {
  id: string;
  type: 'user' | 'agent' | 'system';
  content: string;
  timestamp: number;
  name: string;
  source: 'chat' | 'transcript' | 'debug';
}

function messageKey(message: Pick<VisibleMessage, 'type' | 'content'>): string {
  return `${message.type}:${message.content.trim().toLowerCase()}`;
}

function isUserIdentity(identity?: string): boolean {
  return Boolean(identity && (identity.startsWith('user-') || identity.includes('desktop')));
}

export default function ChatTile({ connectionState, debug }: ChatTileProps) {
  const { chatMessages, send, isSending } = useChat();
  const transcriptions = useTranscriptions();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isConnected = connectionState === ConnectionState.Connected;

  const messages = useMemo(() => {
    const chat: VisibleMessage[] = chatMessages.map((msg) => ({
      id: msg.id,
      type: msg.from?.isLocal ? 'user' : 'agent',
      content: msg.message,
      timestamp: Number(msg.timestamp) || Date.now(),
      name: msg.from?.isLocal ? 'You' : msg.from?.name || msg.from?.identity || 'Agent',
      source: 'chat',
    }));

    const transcript: VisibleMessage[] = transcriptions.map((msg, index) => {
      const identity = msg.participantInfo?.identity;
      const isUser = isUserIdentity(identity);
      return {
      id: `${msg.streamInfo.id}-${index}`,
        type: isUser ? 'user' : 'agent',
      content: msg.text,
        timestamp: Date.now() + index,
        name: isUser ? 'You' : 'Friday',
        source: 'transcript',
      };
    });

    const debugMessages: VisibleMessage[] = (debug?.conversationItems ?? []).map((item) => ({
      id: item.id,
      type: item.role,
      content: item.text,
      timestamp: item.timestamp,
      name: item.role === 'user' ? 'You' : item.role === 'agent' ? 'Friday' : 'System',
      source: 'debug',
    }));

    const seen = new Set<string>();
    return [...chat, ...transcript, ...debugMessages]
      .filter((message) => message.content.trim())
      .sort((a, b) => a.timestamp - b.timestamp)
      .filter((message) => {
        const key = messageKey(message);
        if (seen.has(key)) {
          return false;
        }
        seen.add(key);
        return true;
      });
  }, [chatMessages, transcriptions, debug?.conversationItems]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (content: string) => {
    await send(content);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-3 p-2">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-zinc-600 text-sm">
            {isConnected ? 'Connected. Speak or type a message to Friday.' : `Room is ${connectionState}. Waiting for LiveKit connection...`}
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.type === 'user' ? 'justify-end' : msg.type === 'agent' ? 'justify-start' : 'justify-center'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.type === 'user'
                  ? 'bg-indigo-600 text-white'
                  : msg.type === 'agent'
                  ? 'bg-zinc-800 text-zinc-100'
                  : 'bg-transparent text-zinc-500 text-xs italic'
              }`}
            >
              {msg.type !== 'system' && (
                <div className="mb-1 flex items-center justify-between gap-3 text-xs opacity-70">
                  <span>{msg.name}</span>
                  {msg.source === 'transcript' && <span>speech</span>}
                </div>
              )}
              <div className="whitespace-pre-wrap break-words">{msg.content}</div>
              <div className={`text-xs mt-1 ${msg.type === 'user' ? 'text-indigo-200' : 'text-zinc-500'}`}>
                {formatTimestamp(msg.timestamp)}
              </div>
            </div>
          </div>
        ))}
        {debug?.partialTranscript && (
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-lg border border-indigo-700/50 bg-indigo-950/40 px-3 py-2 text-sm text-indigo-100">
              <div className="mb-1 text-xs text-indigo-300">Listening</div>
              <div className="break-words">{debug.partialTranscript}</div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <ChatMessageInput onSend={handleSendMessage} disabled={isSending || !isConnected} />
    </div>
  );
}
