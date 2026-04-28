import { FormEvent, useRef, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  token: string | null;
  onClose: () => void;
  onAgentCreated: () => void;
}

export default function ClaudeChatModal({ token, onClose, onAgentCreated }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Olá! Descreva o agente que você quer criar — o que ele deve fazer e com que frequência. Vou gerar o código e configurar o agendamento para você.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function send(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setError(null);

    const history = nextMessages.slice(0, -1).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await apiFetch<{ reply: string; agent_created: unknown }>(
        "/api/agents/claude/chat",
        {
          method: "POST",
          token,
          json: { message: text, history },
        }
      );
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      if (res.agent_created) {
        onAgentCreated();
      }
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Erro ao comunicar com o assistente.";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `❌ ${msg}` },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex w-full max-w-xl flex-col rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-xl"
        style={{ height: "min(600px, 90vh)" }}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 px-5 py-4">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">Criar Agente com IA</h2>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Descreva o que o agente deve fazer
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
          >
            ✕
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-brand-green text-white"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-xl bg-gray-100 dark:bg-gray-800 px-4 py-2.5 text-sm text-gray-400 dark:text-gray-500">
                Pensando...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form
          onSubmit={send}
          className="border-t border-gray-100 dark:border-gray-800 p-4 flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder="Descreva o agente..."
            className="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-brand-green px-4 py-2 text-sm font-medium text-white hover:bg-brand-deep disabled:opacity-50"
          >
            Enviar
          </button>
        </form>
      </div>
    </div>
  );
}
