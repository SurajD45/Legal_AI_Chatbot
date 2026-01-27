import { useState, useCallback, useEffect } from "react";
import { chatApi } from "../services/api";
import { getCurrentSession } from "../services/auth";
import type { Message, ChatState } from "../types";

export const useChat = () => {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: null,
    sessionId: null,
  });

  // ----------------------------
  // Restore last conversation
  // ----------------------------
  useEffect(() => {
    async function restoreHistory() {
      const session = await getCurrentSession();
      if (!session?.user?.id) return;

      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/session/latest?user_id=${session.user.id}`
      );
      const data = await res.json();

      if (data.session_id) {
        setState((prev) => ({
          ...prev,
          sessionId: data.session_id,
          messages: data.history.map((m: any) => ({
            id: crypto.randomUUID(),
            role: m.role,
            content: m.content,
            timestamp: new Date(),
          })),
        }));
      }
    }

    restoreHistory();
  }, []);

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim()) return;

      const session = await getCurrentSession();
      if (!session?.user?.id) {
        setState((prev) => ({
          ...prev,
          error: "Please log in to use the chat",
        }));
        return;
      }

      const userId = session.user.id;

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
        timestamp: new Date(),
      };

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isLoading: true,
        error: null,
      }));

      try {
        const response = await chatApi.sendQuery({
          user_id: userId,
          query,
          session_id: state.sessionId || undefined,
        });

        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          timestamp: new Date(),
        };

        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
          isLoading: false,
          sessionId: response.session_id,
        }));
      } catch (error) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error:
            error instanceof Error ? error.message : "An error occurred",
        }));
      }
    },
    [state.sessionId]
  );

  const clearChat = useCallback(() => {
    setState({
      messages: [],
      isLoading: false,
      error: null,
      sessionId: null,
    });
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    messages: state.messages,
    isLoading: state.isLoading,
    error: state.error,
    sendMessage,
    clearChat,
    clearError,
  };
};
