"use client";

import { FormEvent, useRef, useState } from "react";
import { askQuestion } from "@/lib/api";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

function MarkdownMessage({
  content,
  isUser = false,
}: {
  content: string;
  isUser?: boolean;
}) {
  return (
    <div
      className={`prose max-w-none prose-sm ${
        isUser ? "prose-invert" : "prose-stone dark:prose-invert"
      }`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

type RepositoryAssistantProps = {
  suggestions: string[];
  repoOwner: string;
  repoName: string;
};

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
};

export default function RepositoryAssistant({
  suggestions,
  repoOwner,
  repoName,
}: RepositoryAssistantProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "👋 Hi! Ask anything about this repository.",
    },
  ]);

  const [isSending, setIsSending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const query = inputRef.current?.value.trim();

    if (!query || isSending) return;

    setIsSending(true);

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: query,
      },
    ]);

    if (inputRef.current) {
      inputRef.current.value = "";
    }

    try {
      const response = await askQuestion(repoOwner, repoName, query);

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            response?.answer ??
            response?.error ??
            "No answer was returned by the backend.",
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            error instanceof Error
              ? error.message
              : "Failed to get an answer from the backend.",
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="flex h-full min-h-128 flex-col">
      <div className="shrink-0 border-b border-stone-200 p-4">
        <div className="flex flex-wrap gap-2">
          {suggestions.map((item) => (
            <button
              key={item}
              onClick={() => {
                if (inputRef.current) {
                  inputRef.current.value = item;
                  inputRef.current.focus();
                }
              }}
              className="rounded-full border border-stone-300 px-3 py-1 text-xs text-stone-700 transition hover:bg-stone-100"
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`max-w-[90%] rounded-2xl p-4 ${
              message.role === "user"
                ? "ml-auto bg-stone-900 text-white"
                : "bg-stone-100 text-stone-900"
            }`}
          >
            <MarkdownMessage
              content={message.content}
              isUser={message.role === "user"}
            />
          </div>
        ))}
      </div>

      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t border-stone-200 p-4"
      >
        <div className="flex items-center gap-2 rounded-2xl border border-stone-300 px-3 py-2">
          <input
            ref={inputRef}
            type="text"
            placeholder="Ask about this repository..."
            className="flex-1 bg-transparent text-sm outline-none"
          />

          <button
            type="submit"
            disabled={isSending}
            className="rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSending ? "Sending..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
