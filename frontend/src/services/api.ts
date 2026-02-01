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