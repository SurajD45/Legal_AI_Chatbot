import { useEffect, useRef, useState } from "react";
import { Trash2, AlertCircle, Scale } from "lucide-react";

import { useChat } from "./hooks/useChat";
import { supabase } from "./services/auth";

import Auth from "./components/Auth";
import ChatMessage from "./components/ChatMessage";

import { ChatInput } from "./components/ChatInput";
import { Welcome } from "./components/Welcome";

function App() {
  const { messages, isLoading, error, sendMessage, clearChat, clearError } =
    useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [checkingAuth, setCheckingAuth] = useState(true);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setLoggedIn(!!data.session?.user);
      setCheckingAuth(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setLoggedIn(!!session?.user);
      }
    );

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (checkingAuth) return null;
  if (!loggedIn) return <Auth />;

  return (
    <div className="flex flex-col h-screen bg-[#f7f7f5]">
      {/* HEADER */}
      <header className="bg-primary-800 border-b-4 border-[#d4af37] text-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Scale className="w-10 h-10 text-[#d4af37]" />
            <div>
              <h1 className="text-2xl font-serif tracking-wide">
                Legal AI Assistant
              </h1>
              <p className="text-sm text-[#f0e6b8] tracking-wider">
                INDIAN PENAL CODE (IPC)
              </p>
            </div>
          </div>

          <div className="flex gap-3">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-md text-sm"
              >
                <Trash2 className="w-4 h-4" />
                Clear
              </button>
            )}

            <button
              onClick={async () => {
                await supabase.auth.signOut();
              }}
              className="px-4 py-2 bg-red-700 hover:bg-red-800 rounded-md text-sm"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* ERROR */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-3">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2 text-red-800">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
            <button
              onClick={clearError}
              className="text-red-700 font-medium"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* CONTENT */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <Welcome onQueryClick={sendMessage} />
        ) : (
          <div className="max-w-5xl mx-auto px-6 py-8">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}

export default App;
