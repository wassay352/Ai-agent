"use client";

import { motion } from "framer-motion";

interface ToolCallCardProps {
  name: string;
  arguments?: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "error";
  result?: string;
}

export default function ToolCallCard({
  name,
  arguments: args,
  status,
  result,
}: ToolCallCardProps) {
  const statusColors = {
    pending: "text-gray-400",
    running: "text-yellow-400",
    completed: "text-green-400",
    error: "text-red-400",
  };

  const statusLabels = {
    pending: "Pending",
    running: "Running...",
    completed: "Completed",
    error: "Error",
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <svg
            className="w-3.5 h-3.5 text-accent"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
            />
          </svg>
          <span className="font-mono font-medium text-gray-200">{name}</span>
        </div>
        <span className={`font-medium ${statusColors[status]}`}>
          {statusLabels[status]}
        </span>
      </div>

      {args && Object.keys(args).length > 0 && (
        <div className="mt-2 bg-gray-950 rounded p-2 overflow-x-auto">
          <pre className="text-gray-400 font-mono text-xs">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
      )}

      {result && (
        <div className="mt-2 bg-gray-950 rounded p-2 overflow-x-auto max-h-40">
          <pre className="text-gray-300 font-mono text-xs whitespace-pre-wrap">
            {result}
          </pre>
        </div>
      )}

      {status === "running" && (
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1 flex-1 bg-gray-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-accent rounded-full"
              initial={{ width: "0%" }}
              animate={{ width: "100%" }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
        </div>
      )}
    </motion.div>
  );
}
