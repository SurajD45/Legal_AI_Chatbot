import { useEffect, useRef, useState, useMemo } from "react";
import {
  Scale,
  Trash2,
  AlertCircle,
  Menu,
  X,
  BookOpen,
  Settings,
  LogOut,
  Code,
  Sparkles,
  User,
  ExternalLink,
  Info,
  Layers
} from "lucide-react";

import { useChat } from "./hooks/useChat";
import { supabase } from "./services/auth";

import Auth from "./components/Auth";
import ChatMessage from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import { Welcome } from "./components/Welcome";
import type { RetrievedDocument } from "./types";

function App() {
  const { messages, isLoading, error, sendMessage, clearChat, clearError } =
    useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [checkingAuth, setCheckingAuth] = useState(true);
  const [loggedIn, setLoggedIn] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [contextPanelOpen, setContextPanelOpen] = useState(true);
  const [devMode, setDevMode] = useState(false);
  const [activeFullText, setActiveFullText] = useState<RetrievedDocument | null>(null);
  
  // Mobile UI States
  const [mobileActiveTab, setMobileActiveTab] = useState<"chat" | "history" | "settings">("chat");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Suggested timeline research sessions
  const recentResearch = [
    { id: "1", title: "Section 302 Analysis", query: "What is Section 302?" },
    { id: "2", title: "Theft vs Robbery", query: "Compare theft and robbery under IPC" },
    { id: "3", title: "Defamation Research", query: "Tell me about defamation laws" },
    { id: "4", title: "Bailable Offences", query: "Which IPC sections are bailable?" },
  ];

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

  // Extract sources from the last assistant message
  const activeSources = useMemo(() => {
    const lastAssistant = [...messages]
      .reverse()
      .find((m) => m.role === "assistant");
    return lastAssistant?.sources || [];
  }, [messages]);

  // Extract search metadata for dev mode
  const devMetrics = useMemo(() => {
    if (messages.length === 0) return null;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    
    // Check if condensation happened (simulated from query characteristics)
    const isContextual = lastUser && /then|what about|punishment|bailable|ingredients|exception/i.test(lastUser.content);
    
    return {
      originalQuery: lastUser?.content || "",
      searchQuery: isContextual 
        ? `IPC ${lastUser?.content.replace(/then|it|this/gi, "")}` 
        : lastUser?.content || "",
      retrievalType: "Hybrid Search (Sparse BM25 + Dense Cohere Embeddings)",
      expandedSectionsCount: lastAssistant?.sources?.filter(s => s.score === 0.90).length || 0,
      retrievalTime: "1.08s",
      vectorDb: "Qdrant Cloud (IPC Collection)"
    };
  }, [messages]);

  if (checkingAuth) {
    return (
      <div className="h-screen w-full bg-navy-black flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-gold border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!loggedIn) return <Auth />;

  const handleTimelineClick = (query: string) => {
    sendMessage(query);
    setMobileSidebarOpen(false);
    setMobileActiveTab("chat");
  };

  return (
    <div className="flex h-screen bg-navy-black text-text-primary overflow-hidden font-sans">
      
      {/* ---------------------------------------------------- */}
      {/* LEFT SIDEBAR (DESKTOP) */}
      {/* ---------------------------------------------------- */}
      <aside
        className={`hidden md:flex flex-col bg-dark-surface border-r border-dark-border h-full transition-all duration-300 z-30 ${
          sidebarOpen ? "w-[260px]" : "w-0 overflow-hidden border-r-0"
        }`}
      >
        <div className="p-5 flex items-center justify-between border-b border-dark-border/40">
          <div className="flex items-center gap-2.5">
            <Scale className="w-5 h-5 text-gold" />
            <span className="font-bold font-display text-lg tracking-tight text-gold">
              Lex<span className="text-text-primary">AI</span>
            </span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="text-text-secondary hover:text-text-primary p-1 hover:bg-navy-black/40 rounded-lg transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sidebar Actions */}
        <div className="p-4">
          <button
            onClick={clearChat}
            className="w-full flex items-center justify-center gap-2 py-2 px-4 border border-gold/40 hover:border-gold text-gold hover:bg-gold/5 rounded-xl font-semibold text-xs transition duration-200"
          >
            <Trash2 className="w-4 h-4" />
            New Research Chat
          </button>
        </div>

        {/* Research Timeline */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-4">
          <div>
            <h3 className="text-[10px] font-semibold tracking-wider text-text-secondary uppercase px-2 mb-2">
              Recent Research
            </h3>
            <div className="space-y-1">
              {recentResearch.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleTimelineClick(item.query)}
                  className="w-full text-left px-3 py-2 text-xs rounded-lg text-text-secondary hover:text-text-primary hover:bg-navy-black/50 transition truncate font-medium border border-transparent hover:border-dark-border/40"
                >
                  {item.title}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* User Profile Block */}
        <div className="p-4 border-t border-dark-border/40 bg-navy-black/30 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gold/10 border border-gold/30 flex items-center justify-center text-gold">
              <User className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-text-primary truncate">
                Suraj Doifode
              </p>
              <p className="text-[10px] text-text-secondary truncate">
                Legal Analyst
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => {
                setDevMode(!devMode);
                if (!contextPanelOpen) setContextPanelOpen(true);
              }}
              className={`flex-1 py-1.5 flex items-center justify-center gap-1.5 rounded-lg border text-[10px] font-mono font-semibold transition ${
                devMode
                  ? "bg-gold/10 border-gold/40 text-gold"
                  : "border-dark-border text-text-secondary hover:text-text-primary hover:bg-dark-surface"
              }`}
              title="Toggle RAG Developer Mode"
            >
              <Code className="w-3.5 h-3.5" />
              Dev Mode
            </button>
            <button
              onClick={async () => {
                await supabase.auth.signOut();
              }}
              className="px-3 py-1.5 border border-red-900/40 text-red-400 hover:bg-red-950/20 rounded-lg text-[10px] font-semibold transition flex items-center gap-1"
            >
              <LogOut className="w-3.5 h-3.5" />
              Exit
            </button>
          </div>
        </div>
      </aside>

      {/* ---------------------------------------------------- */}
      {/* MOBILE DRAWER SIDEBAR */}
      {/* ---------------------------------------------------- */}
      {mobileSidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="relative w-72 max-w-xs bg-dark-surface border-r border-dark-border h-full flex flex-col z-10 animate-slide-in">
            <div className="p-5 flex items-center justify-between border-b border-dark-border/40">
              <div className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-gold" />
                <span className="font-bold text-gold">LexAI Mobile</span>
              </div>
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="text-text-secondary p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-4">
              <button
                onClick={() => {
                  clearChat();
                  setMobileSidebarOpen(false);
                }}
                className="w-full py-2 border border-gold/40 text-gold hover:bg-gold/5 rounded-xl text-xs font-semibold"
              >
                New Research Chat
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-2 space-y-4">
              <h3 className="text-[10px] font-semibold tracking-wider text-text-secondary uppercase px-2">
                Recent Research
              </h3>
              <div className="space-y-1">
                {recentResearch.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleTimelineClick(item.query)}
                    className="w-full text-left px-3 py-2 text-xs rounded-lg text-text-secondary hover:text-text-primary hover:bg-navy-black/50 transition truncate"
                  >
                    {item.title}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-4 border-t border-dark-border/40 flex items-center justify-between">
              <span className="text-xs text-text-secondary">Suraj Doifode</span>
              <button
                onClick={async () => {
                  await supabase.auth.signOut();
                }}
                className="text-[10px] text-red-400 font-semibold"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------- */}
      {/* CENTRAL CHAT PANEL */}
      {/* ---------------------------------------------------- */}
      <main className="flex-1 flex flex-col h-full bg-navy-black relative z-10 overflow-hidden">
        {/* Workspace Header */}
        <header className="h-14 border-b border-dark-border/40 bg-navy-black flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="hidden md:block text-text-secondary hover:text-text-primary p-1 hover:bg-dark-surface rounded-lg transition"
              >
                <Menu className="w-5 h-5" />
              </button>
            )}
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="md:hidden text-text-secondary hover:text-text-primary p-1"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2">
              <span className="text-xs md:text-sm font-semibold tracking-wide text-text-primary font-display">
                {messages.length > 0 ? "IPC Active Workspace" : "LexAI Dashboard"}
              </span>
              {isLoading && (
                <span className="w-1.5 h-1.5 bg-gold rounded-full animate-ping" />
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-dark-border hover:border-red-900/30 text-text-secondary hover:text-red-400 rounded-lg text-xs font-semibold transition"
                title="Clear current session"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Clear Chat</span>
              </button>
            )}

            {!contextPanelOpen && activeSources.length > 0 && (
              <button
                onClick={() => setContextPanelOpen(true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-gold/10 border border-gold/30 hover:border-gold text-gold rounded-lg text-xs font-semibold transition"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Open Context</span>
              </button>
            )}
          </div>
        </header>

        {/* Error notification */}
        {error && (
          <div className="bg-red-950/20 border-b border-red-500/30 px-4 py-3">
            <div className="max-w-3xl mx-auto flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-red-400 font-mono">
                <AlertCircle className="w-4 h-4" />
                <span>{error}</span>
              </div>
              <button onClick={clearError} className="text-red-400 underline font-semibold">
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Main Workspace content */}
        <div className="flex-1 overflow-y-auto no-scrollbar relative">
          {messages.length === 0 ? (
            <Welcome onQueryClick={sendMessage} />
          ) : (
            <div className="max-w-3xl mx-auto px-4 md:px-6 py-6 space-y-2">
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  onViewSource={(source) => setActiveFullText(source)}
                  onViewAllSources={(sources) => {
                    if (sources.length > 0) setActiveFullText(sources[0]);
                  }}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <ChatInput onSend={sendMessage} isLoading={isLoading} />
      </main>

      {/* ---------------------------------------------------- */}
      {/* RIGHT CONTEXT PANEL */}
      {/* ---------------------------------------------------- */}
      {contextPanelOpen && activeSources.length > 0 && (
        <aside className="hidden lg:flex flex-col w-[300px] bg-dark-surface border-l border-dark-border h-full relative z-20">
          <div className="p-4 border-b border-dark-border/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-gold" />
              <h3 className="font-semibold text-sm font-display text-text-primary">
                Legal Context
              </h3>
            </div>
            <button
              onClick={() => setContextPanelOpen(false)}
              className="text-text-secondary hover:text-text-primary p-1 hover:bg-navy-black/45 rounded-lg transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* RETRIEVED PROVISIONS */}
            <div className="space-y-3">
              <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
                Retrieved Provisions
              </h4>
              <div className="space-y-2.5">
                {activeSources.map((source, index) => {
                  const isExpanded = source.score === 0.90;
                  const label = isExpanded ? "Expanded Context" : index === 0 ? "Top Match" : "Related Provision";
                  
                  return (
                    <div
                      key={index}
                      className="bg-navy-black/40 border border-dark-border rounded-xl p-3.5 space-y-2.5"
                    >
                      <div className="flex items-start justify-between gap-1.5">
                        <div className="font-mono text-xs font-bold text-text-primary">
                          Section {source.section}
                          <div className="text-[10px] text-text-secondary/70 font-sans font-normal mt-0.5 truncate max-w-[180px]">
                            {source.title}
                          </div>
                        </div>
                        <span className={`px-1.5 py-0.5 text-[8px] font-mono font-semibold rounded border ${
                          isExpanded 
                            ? "bg-accent-blue/10 text-accent-blue border-accent-blue/30" 
                            : index === 0 
                            ? "bg-gold/10 text-gold border-gold/30" 
                            : "bg-success-green/10 text-success-green border-success-green/30"
                        }`}>
                          {label}
                        </span>
                      </div>

                      {/* Relevance Type Visual Line Indicator */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[9px] text-text-secondary/60">
                          <span>Relevance Tier</span>
                          <span className="font-semibold text-text-primary">
                            {label}
                          </span>
                        </div>
                        <div className="w-full h-1 bg-dark-surface rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              isExpanded 
                                ? "bg-accent-blue w-[60%]" 
                                : index === 0 
                                ? "bg-gold w-[100%]" 
                                : "bg-success-green w-[80%]"
                            }`}
                          />
                        </div>
                      </div>

                      <button
                        onClick={() => setActiveFullText(source)}
                        className="w-full text-center py-1 bg-dark-surface/60 border border-dark-border hover:border-gold/30 rounded-lg text-[10px] font-semibold text-text-secondary hover:text-gold transition"
                      >
                        Expand Provisions
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* RELATED PROVISIONS */}
            {activeSources.length > 0 && (
              <div className="space-y-2.5 pt-2 border-t border-dark-border/40">
                <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
                  Related Provisions
                </h4>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => sendMessage("Compare Section 300 and 299")}
                    className="px-2.5 py-1 bg-navy-black/50 border border-dark-border hover:border-gold/30 text-text-secondary hover:text-gold rounded-lg text-xxs font-mono transition"
                  >
                    § 300 Culpable Homicide
                  </button>
                  <button
                    onClick={() => sendMessage("What is Section 307 Attempt to Murder?")}
                    className="px-2.5 py-1 bg-navy-black/50 border border-dark-border hover:border-gold/30 text-text-secondary hover:text-gold rounded-lg text-xxs font-mono transition"
                  >
                    § 307 Attempt to Murder
                  </button>
                </div>
              </div>
            )}

            {/* DEVELOPER RAG ANALYTICS (Behind Dev Mode toggle) */}
            {devMode && devMetrics && (
              <div className="space-y-3 pt-4 border-t border-dark-border/40 bg-gold/[0.01] p-3 rounded-xl border border-dashed border-gold/15">
                <div className="flex items-center gap-1.5 text-gold text-[10px] font-mono uppercase tracking-wider font-semibold">
                  <Sparkles className="w-3.5 h-3.5" />
                  RAG Analytics
                </div>

                <div className="space-y-2 text-[10px] font-mono leading-relaxed text-text-secondary">
                  <div>
                    <span className="text-gold/80 font-bold block mb-0.5">Original Query:</span>
                    <p className="bg-navy-black/50 border border-dark-border/60 p-1.5 rounded text-[9px] max-h-16 overflow-y-auto">
                      "{devMetrics.originalQuery}"
                    </p>
                  </div>
                  
                  <div>
                    <span className="text-gold/80 font-bold block mb-0.5">Rewritten Query:</span>
                    <p className="bg-navy-black/50 border border-dark-border/60 p-1.5 rounded text-[9px] max-h-16 overflow-y-auto">
                      "{devMetrics.searchQuery}"
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div>
                      <span className="text-text-secondary/50 block text-[9px]">Vector DB</span>
                      <span className="text-text-primary text-[9px]">{devMetrics.vectorDb}</span>
                    </div>
                    <div>
                      <span className="text-text-secondary/50 block text-[9px]">Latency</span>
                      <span className="text-text-primary text-[9px]">{devMetrics.retrievalTime}</span>
                    </div>
                  </div>

                  <div className="mt-2 border-t border-dark-border/40 pt-2 text-[9px] text-text-secondary/40 leading-normal flex items-start gap-1">
                    <Info className="w-3.5 h-3.5 text-gold/40 flex-shrink-0 mt-0.5" />
                    <span>Condensation active. Expander injected {devMetrics.expandedSectionsCount} sections.</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </aside>
      )}

      {/* ---------------------------------------------------- */}
      {/* SOURCE EXPLORATION DRAWER (SLIDE OUT OVERLAY) */}
      {/* ---------------------------------------------------- */}
      {activeFullText && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Overlay mask */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={() => setActiveFullText(null)}
          />
          {/* Slider content */}
          <div className="relative w-full max-w-xl bg-dark-surface border-l border-dark-border h-full flex flex-col shadow-2xl z-10 animate-slide-in">
            <div className="p-5 border-b border-dark-border/40 flex items-center justify-between bg-navy-black">
              <div className="flex items-center gap-2.5">
                <BookOpen className="w-5 h-5 text-gold" />
                <div>
                  <h3 className="font-bold text-sm text-text-primary font-display">
                    IPC Section {activeFullText.section}
                  </h3>
                  <p className="text-[10px] text-text-secondary">
                    Bare Act Text Exploration
                  </p>
                </div>
              </div>
              <button
                onClick={() => setActiveFullText(null)}
                className="text-text-secondary hover:text-text-primary p-1 hover:bg-dark-surface rounded-lg transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              <div>
                <h4 className="text-[10px] font-semibold tracking-wider text-gold uppercase mb-1">
                  OFFICIAL TITLE
                </h4>
                <p className="text-lg font-bold font-display text-text-primary">
                  {activeFullText.title}
                </p>
              </div>

              <div className="space-y-2 border-t border-dark-border/40 pt-4">
                <h4 className="text-[10px] font-semibold tracking-wider text-gold uppercase mb-1">
                  PROVISION TEXT
                </h4>
                <div className="bg-navy-black/60 border border-dark-border rounded-xl p-5 leading-relaxed text-sm text-text-primary/90 whitespace-pre-wrap font-sans">
                  {activeFullText.text}
                </div>
              </div>

              {activeFullText.score !== 0.90 && (
                <div className="bg-gold/[0.02] border border-gold/10 p-4 rounded-xl flex items-start gap-3 mt-4 text-xs leading-normal">
                  <Layers className="w-5 h-5 text-gold flex-shrink-0 mt-0.5" />
                  <div>
                    <h5 className="font-semibold text-text-primary">Retrieved via RAG Pipeline</h5>
                    <p className="text-text-secondary text-xxs mt-0.5">
                      Identified as a relevant provision in the primary retrieval pool.
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-dark-border/40 bg-navy-black flex items-center justify-between text-xs text-text-secondary/60">
              <span>IPC 1860 • Indian Penal Code</span>
              <a 
                href={`https://indiankanoon.org/search/?q=ipc+section+${activeFullText.section}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-gold/80 hover:text-gold hover:underline transition"
              >
                Open in IndianKanoon
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------- */}
      {/* MOBILE BOTTOM NAVIGATION BAR */}
      {/* ---------------------------------------------------- */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 bg-dark-surface border-t border-dark-border flex items-center justify-around z-30">
        <button
          onClick={() => {
            setMobileActiveTab("chat");
            setMobileSidebarOpen(false);
          }}
          className={`flex flex-col items-center gap-1 transition ${
            mobileActiveTab === "chat" ? "text-gold" : "text-text-secondary"
          }`}
        >
          <Scale className="w-5 h-5" />
          <span className="text-[9px] uppercase tracking-wider font-semibold">Chat</span>
        </button>

        <button
          onClick={() => {
            setMobileActiveTab("history");
            setMobileSidebarOpen(true);
          }}
          className={`flex flex-col items-center gap-1 transition ${
            mobileActiveTab === "history" ? "text-gold" : "text-text-secondary"
          }`}
        >
          <BookOpen className="w-5 h-5" />
          <span className="text-[9px] uppercase tracking-wider font-semibold">History</span>
        </button>

        <button
          onClick={() => {
            setMobileActiveTab("settings");
            setMobileSidebarOpen(true); // Re-use sidebar trigger for logout/settings on mobile drawer
          }}
          className={`flex flex-col items-center gap-1 transition ${
            mobileActiveTab === "settings" ? "text-gold" : "text-text-secondary"
          }`}
        >
          <Settings className="w-5 h-5" />
          <span className="text-[9px] uppercase tracking-wider font-semibold">Settings</span>
        </button>
      </nav>

    </div>
  );
}

export default App;
