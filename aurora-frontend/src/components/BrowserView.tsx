"use client";

import { useState, useEffect, useRef } from "react";

export default function BrowserView() {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isConnected) return;

    ws.current = new WebSocket("ws://localhost:8000/ws/agent");

    let lastObjectUrl: string | null = null;

    ws.current.onmessage = (event) => {
      if (lastObjectUrl) {
        URL.revokeObjectURL(lastObjectUrl);
      }
      const newUrl = URL.createObjectURL(event.data);
      setImageUrl(newUrl);
      lastObjectUrl = newUrl;
    };

    ws.current.onclose = () => {
      console.log("WebSocket disconnected");
      setIsConnected(false);
      if (lastObjectUrl) {
        URL.revokeObjectURL(lastObjectUrl);
      }
      setImageUrl(null);
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      ws.current?.close();
    };

    return () => {
      ws.current?.close();
    };
  }, [isConnected]);

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 text-white text-center">
        <h2 className="text-lg font-semibold">Agent Browser View</h2>
      </div>
      <div className="flex-1 flex items-center justify-center p-4">
        {!isConnected ? (
          <button
            onClick={() => setIsConnected(true)}
            className="px-6 py-3 bg-green-600 text-white font-bold transition-colors"
          >
            Start Agent Session
          </button>
        ) : imageUrl ? (
          <img
            src={imageUrl}
            alt="Live view from the agent's browser"
            className="w-full h-full object-contain"
          />
        ) : (
          <p className="text-gray-500 text-xl">Connecting to agent...</p>
        )}
      </div>
    </div>
  );
}
