// API Types
export interface ChatRequest {
  query: string;
  session_id?: string;
}

export interface RetrievedDocument {
  section: string;
  title: string;
  text: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  sources: RetrievedDocument[];
  session_id: string;
  query: string;
}

export interface HealthResponse {
  status: string;
  environment: string;
  version: string;
  services: {
    qdrant?: {
      status: string;
      collection?: string;
      vectors_count?: number;
    };
    embedding_model?: {
      status: string;
      model?: string;
    };
  };
}

export interface ErrorResponse {
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

// Message Types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: RetrievedDocument[];
  timestamp: Date;
}

// UI State Types
export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  sessionId: string | null;
}