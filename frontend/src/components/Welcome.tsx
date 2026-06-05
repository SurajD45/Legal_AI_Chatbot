import React from 'react';
import { Scale, Search, BookOpen, Clock } from 'lucide-react';

const exampleQueries = [
  'What is Section 302?',
  'Explain Section 420 in simple terms',
  'What are the punishments for theft?',
  'Tell me about defamation laws',
];

interface WelcomeProps {
  onQueryClick: (query: string) => void;
}

export const Welcome: React.FC<WelcomeProps> = ({ onQueryClick }) => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 bg-navy-black text-text-primary overflow-y-auto min-h-full">
      <div className="max-w-2xl w-full space-y-10 py-8">
        
        {/* Hero Area */}
        <div className="text-center space-y-4">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-gold/10 border border-gold/40 rounded-2xl flex items-center justify-center shadow-lg shadow-gold/5 pulse-gold">
              <Scale className="w-9 h-9 text-gold" />
            </div>
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold font-display tracking-tight">
            Lex<span className="text-gold">AI</span> Assistant
          </h1>
          <p className="text-text-secondary text-base md:text-lg max-w-md mx-auto leading-relaxed">
            Conversational Legal Research Platform for the Indian Penal Code (IPC)
          </p>
        </div>

        {/* Suggestion Chips (2x2 Grid) */}
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider text-center">
            Suggested Queries
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {exampleQueries.map((query, idx) => (
              <button
                key={idx}
                onClick={() => onQueryClick(query)}
                className="text-left p-4 bg-dark-surface border border-dark-border border-l-2 border-l-gold hover:border-gold/50 rounded-xl transition-all duration-300 hover:shadow-lg hover:shadow-gold/5 hover:-translate-y-0.5 group flex items-start gap-3"
              >
                <div className="w-5 h-5 rounded-md bg-navy-black border border-dark-border flex items-center justify-center text-text-secondary group-hover:text-gold transition-colors mt-0.5">
                  <Search className="w-3.5 h-3.5" />
                </div>
                <span className="text-sm text-text-secondary group-hover:text-text-primary transition-colors leading-relaxed">
                  "{query}"
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Brand Specs / Stats Bar */}
        <div className="border-t border-dark-border/60 pt-8 mt-4">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="space-y-1">
              <div className="text-2xl font-bold font-display text-gold">548</div>
              <div className="text-xxs uppercase tracking-wider text-text-secondary flex items-center justify-center gap-1">
                <BookOpen className="w-3 h-3 text-gold/60" />
                IPC Sections
              </div>
            </div>
            
            <div className="space-y-1 border-x border-dark-border/60 px-2">
              <div className="text-2xl font-bold font-display text-gold">Hybrid</div>
              <div className="text-xxs uppercase tracking-wider text-text-secondary flex items-center justify-center gap-1">
                <Search className="w-3 h-3 text-gold/60" />
                RAG Engine
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-2xl font-bold font-display text-gold">~3s</div>
              <div className="text-xxs uppercase tracking-wider text-text-secondary flex items-center justify-center gap-1">
                <Clock className="w-3 h-3 text-gold/60" />
                Response Time
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};