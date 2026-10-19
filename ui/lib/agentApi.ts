"use client";

import type { Message } from "@/components/ChatMessage";

const API_URL = "http://localhost:8000/v1/chat/completions";

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onToolCall?: (toolCall: {
    id: string;
    name: string;
    arguments: Record<string, unknown>;
  }) => void;
  onDone: () => void;
  onError: (error: Error) => void;
}

export async function streamChat(
  messages: Message[],
  model: string,
  apiKey: string,
  callbacks: StreamCallbacks
): Promise<void> {
  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      },
      body: JSON.stringify({
        model,
        messages: messages.map((m) => ({
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
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

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
            callbacks.onToken(delta.content);
          }

          if (delta?.tool_calls) {
            for (const tc of delta.tool_calls) {
              if (tc.function) {
                callbacks.onToolCall?.({
                  id: tc.id || "",
                  name: tc.function.name || "",
                  arguments: JSON.parse(tc.function.arguments || "{}"),
                });
              }
            }
          }
        } catch {
          // Skip malformed JSON
        }
      }
    }

    callbacks.onDone();
  } catch (error) {
    callbacks.onError(error instanceof Error ? error : new Error("Unknown error"));
  }
}

export async function checkHealth(): Promise<{
  status: string;
  provider?: string;
}> {
  try {
    const response = await fetch("http://localhost:8000/health");
    if (!response.ok) throw new Error("Health check failed");
    return await response.json();
  } catch {
    return { status: "unavailable" };
  }
}
