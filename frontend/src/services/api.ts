import {
  EvaluationRequest,
  EvaluationResult,
  LLMProvider,
  StreamEvent,
  ChatRequest,
  ChatResponse,
  ChatMessage,
} from "@/types/api";
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
});

export const llmApi = {
  getProviders: async (): Promise<LLMProvider[]> => {
    const response = await api.get("/providers");
    return response.data;
  },

  evaluate: async (request: EvaluationRequest): Promise<EvaluationResult> => {
    const response = await api.post("/evaluate", request);
    return response.data;
  },

  getHistory: async (): Promise<EvaluationResult[]> => {
    const response = await api.get("/history");
    return response.data;
  },

  getEvaluation: async (id: string): Promise<EvaluationResult> => {
    const response = await api.get(`/evaluations/${id}`);
    return response.data;
  },

  evaluateStream: async (
    request: EvaluationRequest,
    onEvent: (event: StreamEvent) => void
  ): Promise<EvaluationResult | null> => {
    const response = await fetch("/api/evaluate/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) throw new Error("No response body");

    let finalResult: EvaluationResult | null = null;
    let buffer = ""; // Buffer for incomplete chunks

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Append new chunk to buffer
        buffer += decoder.decode(value, { stream: true });

        // Split by double newline (SSE event separator)
        const events = buffer.split("\n\n");

        // Keep the last potentially incomplete event in buffer
        buffer = events.pop() || "";

        for (const event of events) {
          const lines = event.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                onEvent(data);

                // Capture the final result
                if (data.type === "complete" && data.result) {
                  finalResult = data.result;
                }
              } catch (e) {
                console.error("Failed to parse SSE data:", e, line);
              }
            }
          }
        }
      }

      // Process any remaining data in buffer
      if (buffer.trim()) {
        const lines = buffer.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              onEvent(data);
              if (data.type === "complete" && data.result) {
                finalResult = data.result;
              }
            } catch (e) {
              console.error("Failed to parse remaining SSE data:", e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    return finalResult;
  },

  // Chat API
  sendChatMessage: async (
    message: string,
    sessionId?: string | null
  ): Promise<ChatResponse> => {
    const request: ChatRequest = {
      message,
      session_id: sessionId,
    };
    const response = await api.post("/chat", request);
    return response.data;
  },

  getChatHistory: async (sessionId: string): Promise<ChatMessage[]> => {
    const response = await api.get(`/chat/history/${sessionId}`);
    return response.data;
  },

  clearChatSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/chat/session/${sessionId}`);
  },
};

export default api;
