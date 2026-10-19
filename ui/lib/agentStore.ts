import { create } from "zustand";
import type { Message } from "@/components/ChatMessage";

interface AgentState {
  messages: Message[];
  apiKey: string;
  model: string;
  isStreaming: boolean;
  setApiKey: (apiKey: string) => void;
  setModel: (model: string) => void;
  hydrateFromStorage: () => void;
  sendMessage: (content: string) => Promise<void>;
}

const API_URL = "http://localhost:8000/v1/chat/completions";
const DEFAULT_MODEL = "claude-3-5-sonnet-20241022";

export const useAgentStore = create<AgentState>((set, get) => ({
  messages: [],
  // NOTE: never read localStorage during store creation. The store is
  // evaluated on both the server and the client, so a value that differs
  // between them (saved key vs. empty) causes a hydration mismatch. Start
  // from a deterministic default and hydrate from localStorage in an effect.
  apiKey: "",
  model: DEFAULT_MODEL,
  isStreaming: false,

  setApiKey: (apiKey: string) => set({ apiKey: apiKey }),
  setModel: (model: string) => set({ model: model }),

  hydrateFromStorage: () => {
    if (typeof window === "undefined") return;
    try {
      const savedKey = localStorage.getItem("cloak_api_key");
      const savedModel = localStorage.getItem("cloak_model");
      set({
        apiKey: savedKey ?? "",
        model: savedModel ?? DEFAULT_MODEL,
      });
    } catch {
      // localStorage can throw in private mode; defaults are fine.
    }
  },

  sendMessage: async (content: string) => {
    const { messages, apiKey, model, isStreaming } = get();
    if (isStreaming) return;

    const userMessage: Message = { role: "user", content };
    const newMessages = [...messages, userMessage];

    set({ messages: newMessages, isStreaming: true });

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
        },
        body: JSON.stringify({
          model,
          messages: newMessages.map((m) => ({
            role: m.role,
            content: m.content,
            ...(m.tool_calls ? { tool_calls: m.tool_calls } : {}),
            ...(m.tool_call_id ? { tool_call_id: m.tool_call_id } : {}),
            ...(m.name ? { name: m.name } : {}),
          })),
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let assistantContent = "";
      let currentMessages = [...newMessages];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim() || line.trim() === "data: [DONE]") continue;
          if (!line.startsWith("data: ")) continue;

          try {
            const json = JSON.parse(line.slice(6));
            const delta = json.choices?.[0]?.delta;

            if (delta?.content) {
              assistantContent += delta.content;

              const assistantMessage: Message = {
                role: "assistant",
                content: assistantContent,
              };

              currentMessages = [...newMessages, assistantMessage];
              set({ messages: currentMessages });
            }

            if (delta?.tool_calls) {
              // Handle tool calls
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }

      // Final message
      if (assistantContent) {
        const finalMessage: Message = {
          role: "assistant",
          content: assistantContent,
        };
        set({ messages: [...newMessages, finalMessage] });
      }
    } catch (error) {
      const errorMessage: Message = {
        role: "system",
        content: `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
      };
      set({ messages: [...newMessages, errorMessage] });
    } finally {
      set({ isStreaming: false });
    }
  },
}));
