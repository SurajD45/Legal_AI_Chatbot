import React, { useState, KeyboardEvent, useEffect } from "react";
import { ArrowUp, Loader2, Sparkles } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  isLoading,
}) => {
  const [input, setInput] = useState("");
  const [loadingStep, setLoadingStep] = useState(0);

  const loadingMessages = [
    "Thinking...",
    "Retrieving IPC provisions...",
    "Analyzing related sections...",
    "Assembling legal reasoning...",
  ];

  // Cycle loading messages to simulate multi-stage pipeline transparency
  useEffect(() => {
    if (!isLoading) {
      setLoadingStep(0);
      return;
    }

    const timer1 = setTimeout(() => setLoadingStep(1), 600);
    const timer2 = setTimeout(() => setLoadingStep(2), 1500);
    const timer3 = setTimeout(() => setLoadingStep(3), 2800);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
    };
  }, [isLoading]);

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
    <div className="border-t border-dark-border/40 bg-navy-black px-4 md:px-6 py-4 relative z-20">
      <div className="max-w-3xl mx-auto space-y-3">
        {/* Loading Steps Indicator */}
        {isLoading && (
          <div className="flex items-center gap-2 px-4 py-1.5 bg-gold/5 border border-gold/10 rounded-full w-fit mx-auto animate-pulse text-xs text-gold/90 font-mono">
            <Sparkles className="w-3.5 h-3.5 animate-spin" />
            <span>{loadingMessages[loadingStep]}</span>
          </div>
        )}

        {/* Input Bar */}
        <div className="relative flex items-center bg-dark-surface border border-dark-border hover:border-dark-border/80 focus-within:border-gold/40 focus-within:ring-1 focus-within:ring-gold/30 rounded-2xl shadow-xl transition-all duration-300 p-1.5 pl-4">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a legal query or search IPC section..."
            className="flex-1 bg-transparent border-0 focus:ring-0 outline-none text-text-primary placeholder:text-text-secondary/50 font-sans text-sm resize-none py-2 max-h-24 no-scrollbar"
            rows={1}
            disabled={isLoading}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = `${Math.min(target.scrollHeight, 96)}px`;
            }}
          />

          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="w-10 h-10 bg-gold hover:bg-gold/90 active:scale-95 text-navy-black rounded-xl flex items-center justify-center transition disabled:opacity-30 disabled:pointer-events-none"
            aria-label="Send"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin text-navy-black" />
            ) : (
              <ArrowUp className="w-4 h-4 stroke-[3]" />
            )}
          </button>
        </div>

        <div className="text-[10px] text-text-secondary/60 text-center tracking-wide">
          Enter to send • Shift+Enter for new line
        </div>
      </div>
    </div>
  );
};
