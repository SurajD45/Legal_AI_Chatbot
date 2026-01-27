import React, { useState, KeyboardEvent } from "react";
import { Search, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  isLoading,
}) => {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (input.trim() && !isLoading) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-300 bg-white px-6 py-4">
      <div className="max-w-5xl mx-auto flex gap-3 items-center">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search IPC sections or ask a legal question…"
          className="flex-1 px-4 py-3 border border-gray-400 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary-600 font-serif"
          rows={1}
          disabled={isLoading}
          style={{ minHeight: "52px", maxHeight: "120px" }}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = "auto";
            target.style.height = `${Math.min(
              target.scrollHeight,
              120
            )}px`;
          }}
        />

        <button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="w-12 h-12 bg-primary-700 hover:bg-primary-800 text-white rounded-md flex items-center justify-center disabled:opacity-50"
          aria-label="Search"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Search className="w-5 h-5" />
          )}
        </button>
      </div>

      <div className="text-xs text-gray-600 text-center mt-2">
        Press Enter to search • Shift+Enter for new line
      </div>
    </div>
  );
};
