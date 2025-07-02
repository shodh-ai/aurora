"use client";

import { useState, useRef, useEffect, FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const TYPING_SPEED = 3;

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const characterQueueRef = useRef<string[]>([]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isTyping) {
      const intervalId = setInterval(() => {
        const queue = characterQueueRef.current;
        if (queue.length === 0) {
          setIsTyping(false);
          return;
        }
        const nextChar = queue.shift();
        setMessages((prevMessages) => {
          const lastMessage = prevMessages[prevMessages.length - 1];
          const updatedLastMessage = { ...lastMessage, content: lastMessage.content + nextChar };
          return [...prevMessages.slice(0, -1), updatedLastMessage];
        });
      }, TYPING_SPEED);
      return () => clearInterval(intervalId);
    }
  }, [isTyping]);

  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage, { role: "assistant", content: "" }]);
    const currentInput = input;
    setInput("");
    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: currentInput }),
      });
      if (!response.ok || !response.body) throw new Error("Failed to get a streaming response.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const processStream = () => {
        reader.read().then(({ done, value }) => {
          if (done) return;
          const chunk = decoder.decode(value);
          characterQueueRef.current.push(...chunk.split(''));
          if (!isTyping) setIsTyping(true);
          processStream();
        });
      };
      processStream();
    } catch (error) {
      console.error("Error during streaming:", error);
      setMessages((prev) => [...prev.slice(0, -1), { role: 'assistant', content: "Sorry, an error occurred." }]);
    }
  };

  return (
    <div className="flex h-screen w-screen">
      <div className="w-1/2 flex flex-col bg-gray-900 text-white">
        <header className="bg-gray-800 p-4 shadow-md">
          <h1 className="text-xl font-bold text-center">Gemini Agent Foundation</h1>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <div className="max-w-3xl mx-auto">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex items-start gap-4 my-4 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && <div className="w-8 h-8 rounded-full bg-blue-500 flex-shrink-0"></div>}
                <div
                  className={`p-3 rounded-lg max-w-lg prose prose-invert prose-p:my-2 prose-headings:my-2 prose-blockquote:my-2 prose-ul:my-2 prose-ol:my-2 ${
                    msg.role === "user" ? "bg-blue-600" : "bg-gray-700"
                  }`}
                >
                  <ReactMarkdown
                    components={{
                      code(props) {
                        const { ref, node, children, className, ...rest } = props;
                        const match = /language-(\w+)/.exec(className || "");
                        
                        return match ? (
                          <SyntaxHighlighter
                            {...rest}
                            PreTag="div"
                            children={String(children).replace(/\n$/, "")}
                            language={match[1]}
                            style={vscDarkPlus}
                          />
                        ) : (
                          <code {...rest} className="bg-gray-800 rounded-md px-1.5 py-0.5 font-mono">
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {`${msg.content}${msg.role === 'assistant' && isTyping && index === messages.length - 1 ? "▋" : ""}`}
                  </ReactMarkdown>
                </div>
                {msg.role === "user" && <div className="w-8 h-8 rounded-full bg-gray-600 flex-shrink-0"></div>}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </main>
        <footer className="bg-gray-800 p-4">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSendMessage} className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={isTyping ? "Agent is typing..." : "Ask the agent anything..."}
                className="flex-1 p-2 rounded-lg bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isTyping}
              />
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed"
                disabled={!input.trim() || isTyping}
              >
                Send
              </button>
            </form>
          </div>
        </footer>
      </div>
      <div className="w-1/2 bg-white"></div>
    </div>
  );
}