import axios from "axios";
import type { ChatRequest, ChatResponse, HealthResponse } from "../types";

/**
 * Backend base URL
 * MUST be set in frontend/.env as:
 * VITE_API_URL=http://localhost:8000
 */
const API_BASE_URL = import.meta.env.VITE_API_URL;

if (!API_BASE_URL) {
  throw new Error("VITE_API_URL is not defined");
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach Supabase JWT to every outgoing request
api.interceptors.request.use(async (config) => {
  const { supabase } = await import("./auth");
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const chatApi = {
  /**
   * Send a query to the legal assistant
   */
  sendQuery: async (request: ChatRequest): Promise<ChatResponse> => {
    const { data } = await api.post<ChatResponse>("/api/query", request);
    return data;
  },

  /**
   * Clear a chat session (optional / future use)
   */
  clearSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/api/session/${sessionId}`);  // FIXED: Template literal syntax
  },

  /**
   * Check API health
   */
  checkHealth: async (): Promise<HealthResponse> => {
    const { data } = await api.get<HealthResponse>("/health");
    return data;
  },

  /**
   * Restore the latest chat session for the current user
   */
  getLatestSession: async (): Promise<{ session_id: string | null; history: any[] }> => {
    const { data } = await api.get<{ session_id: string | null; history: any[] }>("/api/session/latest");
    return data;
  },
};

// Centralized error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message);
    }
    throw error;
  }
);

export default api;