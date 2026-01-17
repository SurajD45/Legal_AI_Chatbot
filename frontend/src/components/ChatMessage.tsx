import React from 'react';
import { User, Bot, BookOpen } from 'lucide-react';
import type { Message } from '../types';

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center">
          <Bot className="w-5 h-5 text-white" />
        </div>
      )}

      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-primary-600 text-white rounded-br-sm'
              : 'bg-gray-100 text-gray-900 rounded-bl-sm'
          }`}
        >
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-2 w-full">
            <div className="flex items-center gap-1 text-sm text-gray-600">
              <BookOpen className="w-4 h-4" />
              <span className="font-medium">Sources:</span>
            </div>
            {message.sources.map((source, idx) => (
              <div
                key={idx}
                className="bg-white border border-gray-200 rounded-lg p-3 text-sm"
              >
                <div className="font-semibold text-primary-700">
                  Section {source.section}
                  {source.title && `: ${source.title}`}
                </div>
                <div className="text-gray-600 text-xs mt-1">
                  Relevance: {(source.score * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        )}

        <span className="text-xs text-gray-500 mt-1">
          {message.timestamp.toLocaleTimeString()}
        </span>
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
          <User className="w-5 h-5 text-white" />
        </div>
      )}
    </div>
  );
};