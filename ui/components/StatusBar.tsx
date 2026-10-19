"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAgentStore } from "@/lib/agentStore";

const MODELS = [
  "claude-3-5-sonnet-20241022",
  "claude-3-haiku-20240307",
  "gpt-4-turbo",
  "gpt-4o",
  "gpt-3.5-turbo",
];

export default function StatusBar() {
  const [showSettings, setShowSettings] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const model = useAgentStore((s) => s.model);
  const isStreaming = useAgentStore((s) => s.isStreaming);
  const setApiKeyStore = useAgentStore((s) => s.setApiKey);
  const setModelStore = useAgentStore((s) => s.setModel);
  const hydrateFromStorage = useAgentStore((s) => s.hydrateFromStorage);

  // Pull saved key/model out of localStorage AFTER mount. Doing this during
  // render (or in the store initialiser) makes the client tree differ from
  // the server HTML and breaks hydration.
  useEffect(() => {
    hydrateFromStorage();
  }, [hydrateFromStorage]);

  const handleSaveApiKey = () => {
    setApiKeyStore(apiKey);
    try {
      localStorage.setItem("cloak_api_key", apiKey);
    } catch {
      // Storage can be unavailable; the in-memory key still works.
    }
    setShowSettings(false);
  };

  const handleModelChange = (newModel: string) => {
    setModelStore(newModel);
    try {
      localStorage.setItem("cloak_model", newModel);
    } catch {
      // Storage can be unavailable; the in-memory model still works.
    }
  };

  return (
    <header className="border-b border-gray-800 px-4 py-3">
      <div className="flex items-center justify-between max-w-4xl mx-auto">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">Cloak Agent</h1>
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isStreaming ? "bg-yellow-400 animate-pulse" : "bg-green-400"
              }`}
            />
            <span className="text-xs text-gray-400">
              {isStreaming ? "Working" : "Ready"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={model}
            onChange={(e) => handleModelChange(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-accent"
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>

          <button
            onClick={() => {
              setApiKey(localStorage.getItem("cloak_api_key") || "");
              setShowSettings(!showSettings);
            }}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <svg
              className="w-4 h-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </div>

      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="max-w-4xl mx-auto pt-4">
              <div className="bg-gray-800 rounded-xl p-4 space-y-3">
                <label className="block text-xs font-medium text-gray-400">
                  API Key
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter your API key"
                    className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent"
                  />
                  <button
                    onClick={handleSaveApiKey}
                    className="bg-accent hover:bg-accent-hover rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors"
                  >
                    Save
                  </button>
                </div>
                <p className="text-xs text-gray-500">
                  Stored locally in your browser. Sent as Bearer token to the agent API.
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
