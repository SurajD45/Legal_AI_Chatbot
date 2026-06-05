import ReactMarkdown from "react-markdown";
import { Scale, BookOpen, BadgeCheck, FileText, ChevronRight } from "lucide-react";
import type { Message, RetrievedDocument } from "../types";

interface ChatMessageProps {
  message: Message;
  onViewSource?: (source: RetrievedDocument) => void;
  onViewAllSources?: (sources: RetrievedDocument[]) => void;
}

export default function ChatMessage({
  message,
  onViewSource,
  onViewAllSources,
}: ChatMessageProps) {
  const isUser = message.role === "user";

  const getRelevanceLabel = (source: RetrievedDocument, index: number) => {
    if (source.score === 0.90) {
      return "Expanded Context";
    }
    if (index === 0) {
      return "Top Match";
    }
    if (source.score > 0.8) {
      return "Related Provision";
    }
    return "Supporting Context";
  };

  const getRelevanceBadgeColor = (label: string) => {
    switch (label) {
      case "Top Match":
        return "bg-gold/10 text-gold border-gold/30";
      case "Expanded Context":
        return "bg-accent-blue/10 text-accent-blue border-accent-blue/30";
      case "Related Provision":
        return "bg-success-green/10 text-success-green border-success-green/30";
      default:
        return "bg-text-secondary/10 text-text-secondary border-dark-border";
    }
  };

  // USER MESSAGE BUBBLE
  if (isUser) {
    return (
      <div className="flex justify-end mb-6 animate-fade-in">
        <div className="max-w-[80%] md:max-w-[70%] bg-gold/10 border border-gold/20 hover:border-gold/30 rounded-2xl px-5 py-3.5 shadow-md transition-all duration-300">
          <p className="whitespace-pre-wrap break-words leading-relaxed text-sm text-text-primary">
            {message.content}
          </p>
          <div className="text-[10px] text-text-secondary mt-1.5 text-right font-mono">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    );
  }

  // ASSISTANT MESSAGE BUBBLE (LEGAL DESIGN SYSTEM)
  return (
    <div className="flex gap-3 md:gap-4 mb-8 animate-fade-in items-start">
      {/* Bot Icon */}
      <div className="flex-shrink-0 w-8 h-8 md:w-9 md:h-9 rounded-xl bg-gold/10 border border-gold/30 flex items-center justify-center shadow-lg shadow-gold/5">
        <Scale className="w-4 h-4 md:w-5 md:h-5 text-gold" />
      </div>

      <div className="flex-1 space-y-4 overflow-hidden">
        
        {/* Cited Badges Row */}
        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-col gap-2.5 bg-dark-surface border border-dark-border p-4 rounded-xl shadow-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-text-secondary">
                <BookOpen className="w-3.5 h-3.5 text-gold" />
                Cited Provisions
              </div>
              
              {onViewAllSources && (
                <button
                  onClick={() => onViewAllSources(message.sources || [])}
                  className="flex items-center gap-1 text-[11px] font-semibold text-gold hover:text-gold/80 hover:underline transition-all"
                >
                  View All Full Texts
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Badges container */}
            <div className="flex flex-wrap gap-2 mt-1">
              {message.sources.map((source, idx) => {
                const label = getRelevanceLabel(source, idx);
                return (
                  <button
                    key={idx}
                    onClick={() => onViewSource && onViewSource(source)}
                    className="flex items-center gap-2 px-3 py-1.5 bg-navy-black/60 border border-dark-border hover:border-gold/35 rounded-lg text-xs transition-all text-left hover:-translate-y-0.5"
                  >
                    <span className="font-mono font-bold text-text-primary">
                      § {source.section}
                    </span>
                    <span className={`px-1.5 py-0.5 text-[9px] font-mono font-semibold rounded border ${getRelevanceBadgeColor(label)}`}>
                      {label}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-1.5 mt-2 border-t border-dark-border/40 pt-2 text-[10px] text-text-secondary/60">
              <BadgeCheck className="w-3.5 h-3.5 text-gold/80" />
              <span>Source verified: Bare Act of Indian Penal Code, 1860</span>
            </div>
          </div>
        )}

        {/* AI Markdown Answer */}
        <div className="bg-dark-surface border border-dark-border rounded-xl px-5 py-4 shadow-lg">
          <div className="prose prose-invert max-w-none text-text-primary text-sm leading-relaxed space-y-3 font-sans">
            <ReactMarkdown
              components={{
                h3: ({ node, ...props }) => (
                  <h3 className="text-sm font-semibold tracking-wider uppercase text-gold/90 font-display mt-4 mb-2 border-l-2 border-gold pl-2" {...props} />
                ),
                h4: ({ node, ...props }) => (
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mt-3 mb-1" {...props} />
                ),
                p: ({ node, ...props }) => <p className="leading-relaxed mb-3" {...props} />,
                ul: ({ node, ...props }) => <ul className="list-disc pl-4 space-y-1 mb-3" {...props} />,
                ol: ({ node, ...props }) => <ol className="list-decimal pl-4 space-y-1 mb-3" {...props} />,
                li: ({ node, ...props }) => <li className="text-text-primary/95 text-xs md:text-sm" {...props} />,
                code: ({ node, ...props }) => (
                  <code className="bg-navy-black border border-dark-border px-1.5 py-0.5 rounded text-xs font-mono text-gold/80" {...props} />
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          <div className="text-[10px] text-text-secondary/50 mt-4 border-t border-dark-border/20 pt-2 flex items-center gap-1">
            <FileText className="w-3.5 h-3.5 text-text-secondary/40" />
            <span>
              Generated at{" "}
              {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}
