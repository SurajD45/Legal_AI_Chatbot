import React from 'react';
import { Scale, MessageSquare, Search, BookText } from 'lucide-react';

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
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="max-w-2xl w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <div className="w-16 h-16 bg-primary-600 rounded-2xl flex items-center justify-center">
              <Scale className="w-10 h-10 text-white" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Legal AI Assistant
          </h1>
          <p className="text-lg text-gray-600">
            Your AI-powered guide to the Indian Penal Code
          </p>
        </div>

        {/* Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
            <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center mx-auto mb-2">
              <Search className="w-5 h-5 text-primary-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Smart Search</h3>
            <p className="text-sm text-gray-600">
              Hybrid section detection + semantic search
            </p>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
            <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center mx-auto mb-2">
              <MessageSquare className="w-5 h-5 text-primary-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">AI-Powered</h3>
            <p className="text-sm text-gray-600">
              Groq LLM with RAG for accurate answers
            </p>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
            <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center mx-auto mb-2">
              <BookText className="w-5 h-5 text-primary-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Source Citations</h3>
            <p className="text-sm text-gray-600">
              Every answer backed by IPC sections
            </p>
          </div>
        </div>

        {/* Example Queries */}
        <div className="bg-gradient-to-br from-primary-50 to-blue-50 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 mb-4">
            💬 Try asking:
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {exampleQueries.map((query, idx) => (
              <button
                key={idx}
                onClick={() => onQueryClick(query)}
                className="text-left px-4 py-3 bg-white rounded-lg border border-gray-200 hover:border-primary-500 hover:bg-primary-50 transition-all group"
              >
                <span className="text-gray-700 group-hover:text-primary-700">
                  "{query}"
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="flex justify-center gap-8 text-sm text-gray-600">
          <div className="text-center">
            <div className="font-bold text-2xl text-primary-600">512</div>
            <div>IPC Sections</div>
          </div>
          <div className="text-center">
            <div className="font-bold text-2xl text-primary-600">&lt;2s</div>
            <div>Response Time</div>
          </div>
          <div className="text-center">
            <div className="font-bold text-2xl text-primary-600">RAG</div>
            <div>Architecture</div>
          </div>
        </div>
      </div>
    </div>
  );
};