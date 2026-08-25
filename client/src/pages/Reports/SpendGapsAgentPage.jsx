import { useState, useRef, useEffect } from "react";
import { useGapsAgentChat } from "../../data/spend";

// ── Message bubble ───────────────────────────────────────────────────────────

function ToolChip({ name }) {
  return (
    <span className="inline-block text-[10px] px-1.5 py-0.5 rounded font-medium bg-indigo-50 text-indigo-600">
      queried: {name}
    </span>
  );
}

function MessageBubble({ role, content, toolsCalled }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
        isUser
          ? "bg-indigo-600 text-white"
          : "bg-white border border-gray-200 text-gray-800"
      }`}>
        {content}
        {toolsCalled && toolsCalled.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {toolsCalled.map((t, i) => (
              <ToolChip key={i} name={t.name} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] rounded-xl px-4 py-2.5 text-sm bg-white border border-gray-200 text-gray-400 animate-pulse">
        Thinking…
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SpendGapsAgentPage() {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const { mutate, isPending, isError, error, reset } = useGapsAgentChat();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isPending]);

  function handleSend() {
    const text = draft.trim();
    if (!text || isPending) return;

    const nextMessages = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setDraft("");
    reset();

    mutate(
      nextMessages.map(({ role, content }) => ({ role, content })),
      {
        onSuccess: (data) => {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: data.message, toolsCalled: data.tools_called },
          ]);
        },
      }
    );
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="p-6 space-y-5 flex flex-col h-[calc(100vh-4rem)]">

      {/* Header */}
      <div>
        <h1 className="text-base font-semibold text-gray-900">Data Quality Agent</h1>
        <p className="text-xs text-gray-400 mt-0.5">
          Ask about spend transactions with account numbers, department codes, or activity IDs
          that don't exist in reference data — the agent queries live data to answer.
        </p>
      </div>

      {/* Conversation */}
      <div className="flex-1 min-h-0 bg-gray-50 border border-gray-100 rounded-xl p-4 overflow-y-auto space-y-3">
        {messages.length === 0 && !isPending && (
          <div className="h-full flex items-center justify-center text-center text-sm text-gray-400 px-8">
            Try asking "what account number gaps exist right now?" or
            "which department has the most data quality issues?"
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} content={m.content} toolsCalled={m.toolsCalled} />
        ))}
        {isPending && <ThinkingBubble />}
        {isError && (
          <div className="text-center text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error?.response?.status === 503
              ? <>Local model unavailable — is Ollama running? (<code>ollama serve</code>)</>
              : (error?.response?.data?.detail
                  ? `Request failed: ${JSON.stringify(error.response.data.detail)}`
                  : "Request failed — see the browser console for details.")}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex items-end gap-2">
        <textarea
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about data quality gaps… (Shift+Enter for a new line)"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          onClick={handleSend}
          disabled={isPending || !draft.trim()}
          className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          {isPending ? "Thinking…" : "Send"}
        </button>
      </div>

    </div>
  );
}
