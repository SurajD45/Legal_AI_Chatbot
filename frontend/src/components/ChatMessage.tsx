// frontend/src/components/ChatMessage.tsx
import { Scale, BookOpen, BadgeCheck } from "lucide-react";
import type { Message } from "../types";

interface ChatMessageProps {
  message: Message;
}

function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  // USER MESSAGE
  if (isUser) {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-[75%] bg-primary-600 text-white rounded-xl px-4 py-3 shadow-sm">
          <p className="whitespace-pre-wrap break-words leading-relaxed">
            {message.content}
          </p>
          <div className="text-xs text-primary-100 mt-1 text-right">
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>
    );
  }

  // ASSISTANT MESSAGE (LEGAL STYLE)
  return (
    <div className="flex gap-4 mb-8">
      <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary-700 flex items-center justify-center">
        <Scale className="w-5 h-5 text-white" />
      </div>

      <div className="flex-1 space-y-4">
        {/* SOURCES FIRST */}
        {message.sources && message.sources.length > 0 && (
          <div className="bg-[#f4f1e8] border-l-4 border-[#d4af37] p-4 rounded-md">
            <div className="flex items-center gap-2 text-sm font-mono uppercase tracking-wide text-gray-700">
              <BookOpen className="w-4 h-4" />
              Cited Provisions
            </div>

            <div className="mt-3 space-y-2">
              {message.sources.map((source, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="font-mono font-bold text-primary-800">
                    Section {source.section}
                    {source.title && ` — ${source.title}`}
                  </div>
                  <div className="text-xs text-gray-600">
                    {(source.score * 100).toFixed(1)}%
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center gap-2 mt-3 text-xs text-gray-600">
              <BadgeCheck className="w-4 h-4 text-[#d4af37]" />
              Source: Bare Act of Indian Penal Code, 1860
            </div>
          </div>
        )}

        {/* AI ANSWER */}
        <div className="bg-white border border-gray-200 rounded-lg px-5 py-4 shadow-sm">
          <p className="font-serif text-gray-900 leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>

          <div className="text-xs text-gray-500 mt-3">
            Generated at{" "}
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatMessage;
