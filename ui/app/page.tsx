"use client";

import { motion } from "framer-motion";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import StatusBar from "@/components/StatusBar";
import { useAgentStore } from "@/lib/agentStore";

export default function Home() {
  const messages = useAgentStore((s) => s.messages);
  const isStreaming = useAgentStore((s) => s.isStreaming);

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto">
      <StatusBar />

      <main className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center h-full text-center"
          >
            <h2 className="text-2xl font-semibold mb-2">Cloak Agent</h2>
            <p className="text-gray-400 max-w-md">
              Start a conversation with your AI agent. It can use tools, run
              commands, and help you accomplish tasks.
            </p>
          </motion.div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}

        {isStreaming && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-gray-400 px-4 py-2"
          >
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            <span className="text-sm">Agent is thinking...</span>
          </motion.div>
        )}
      </main>

      <ChatInput />
    </div>
  );
}
