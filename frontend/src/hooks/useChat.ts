import { useState, useCallback } from 'react';
import { chatApi } from '../services/api';
import type { Message, ChatState } from '../types';

export const useChat = () => {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: null,
    sessionId: null,
  });

  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim()) return;

    // Add user message
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
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
        query,
        session_id: state.sessionId || undefined,
      });

      // Add assistant message
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
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
        error: error instanceof Error ? error.message : 'An error occurred',
      }));
    }
  }, [state.sessionId]);

  const clearChat = useCallback(async () => {
    if (state.sessionId) {
      try {
        await chatApi.clearSession(state.sessionId);
      } catch (error) {
        console.error('Failed to clear session:', error);
      }
    }

    setState({
      messages: [],
      isLoading: false,
      error: null,
      sessionId: null,
    });
  }, [state.sessionId]);

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