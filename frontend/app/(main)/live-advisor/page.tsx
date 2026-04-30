"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string };

type ThreadSummary = { id: string; title: string; updatedAt: string };

type ThreadDetail = {
  id: string;
  title: string;
  messages: Array<{ role: string; content: string }>;
};

type LiveChatResponse = {
  reply: string;
  structured?: {
    actions?: Array<{ what?: string; why?: string }>;
    fund_alternatives?: Array<{ name?: string; reason?: string }>;
  };
};

type WebSpeechRec = new () => {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((ev: { results: SpeechRecognitionResultList }) => void) | null;
  onerror: ((ev: { error: string }) => void) | null;
  onend: (() => void) | null;
};

declare global {
  interface Window {
    webkitSpeechRecognition?: WebSpeechRec;
    SpeechRecognition?: WebSpeechRec;
  }
}

function normalizeMessages(raw: unknown): Msg[] {
  if (!Array.isArray(raw)) return [];
  const out: Msg[] = [];
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const r = row as { role?: string; content?: string };
    const role = r.role === "assistant" ? "assistant" : r.role === "user" ? "user" : null;
    const content = typeof r.content === "string" ? r.content : "";
    if (role && content) out.push({ role, content });
  }
  return out;
}

export default function LiveAdvisorPage() {
  const { token } = useAuth();
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [threadsLoading, setThreadsLoading] = useState(true);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [err, setErr] = useState("");
  const [voiceOut, setVoiceOut] = useState(true);
  const [listening, setListening] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recRef = useRef<InstanceType<WebSpeechRec> | null>(null);
  const messagesRef = useRef<Msg[]>([]);
  const activeThreadIdRef = useRef<string | null>(null);

  useEffect(() => {
    activeThreadIdRef.current = activeThreadId;
  }, [activeThreadId]);

  const speechSupported =
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const refreshThreads = useCallback(async () => {
    if (!token) return;
    const r = await apiFetch<{ threads: ThreadSummary[] }>("/advisor/live/threads", token);
    setThreads(r.threads || []);
  }, [token]);

  const hydrateThread = useCallback(
    async (threadId: string) => {
      if (!token) return;
      const data = await apiFetch<ThreadDetail>(`/advisor/live/threads/${threadId}`, token);
      const msgs = normalizeMessages(data.messages);
      messagesRef.current = msgs;
      setMessages(msgs);
      setActiveThreadId(threadId);
      activeThreadIdRef.current = threadId;
    },
    [token],
  );

  useEffect(() => {
    if (!token) {
      setThreads([]);
      setThreadsLoading(false);
      setActiveThreadId(null);
      activeThreadIdRef.current = null;
      messagesRef.current = [];
      setMessages([]);
      return;
    }
    let cancelled = false;
    setThreadsLoading(true);
    (async () => {
      try {
        const r = await apiFetch<{ threads: ThreadSummary[] }>("/advisor/live/threads", token);
        if (cancelled) return;
        const list = r.threads || [];
        setThreads(list);
        if (list.length > 0) {
          await hydrateThread(list[0].id);
        } else {
          messagesRef.current = [];
          setMessages([]);
          setActiveThreadId(null);
          activeThreadIdRef.current = null;
        }
      } catch {
        if (!cancelled) setErr("Could not load conversations.");
      } finally {
        if (!cancelled) setThreadsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, hydrateThread]);

  const speakWithGemini = useCallback(
    async (text: string) => {
      if (!voiceOut || !token || !text) return;
      try {
        setSpeaking(true);
        const resp = await fetch("/api/advisor/tts", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ text: text.slice(0, 5000), voice: "Kore" }),
        });
        if (!resp.ok) throw new Error("TTS failed");
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        if (audioRef.current) {
          audioRef.current.pause();
          audioRef.current = null;
        }
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => {
          setSpeaking(false);
          URL.revokeObjectURL(url);
        };
        audio.onerror = () => {
          setSpeaking(false);
          URL.revokeObjectURL(url);
        };
        await audio.play();
      } catch {
        setSpeaking(false);
        if (typeof window !== "undefined" && window.speechSynthesis) {
          window.speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(text);
          u.rate = 1;
          window.speechSynthesis.speak(u);
        }
      }
    },
    [voiceOut, token],
  );

  const stopSpeaking = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
  }, []);

  const send = useCallback(
    async (userText: string) => {
      const t = userText.trim();
      if (!token || !t) return;
      setErr("");

      let tid = activeThreadIdRef.current;
      if (!tid) {
        try {
          const created = await apiFetch<{ id: string }>("/advisor/live/threads", token, {
            method: "POST",
          });
          tid = created.id;
          activeThreadIdRef.current = tid;
          setActiveThreadId(tid);
          await refreshThreads();
        } catch (e: unknown) {
          setErr(e instanceof Error ? e.message : "Could not start a conversation.");
          return;
        }
      }

      const userMsg: Msg = { role: "user", content: t };
      const thread: Msg[] = [...messagesRef.current, userMsg];
      messagesRef.current = thread;
      setMessages(thread);
      setInput("");
      setLoading(true);
      try {
        const payload = thread.map((m) => ({ role: m.role, content: m.content }));
        if (payload.length === 0) return;
        const r = await apiFetch<LiveChatResponse>("/advisor/live/chat", token, {
          method: "POST",
          body: JSON.stringify({ messages: payload, thread_id: tid }),
        });
        const assistantText = r.reply || "";
        const updated: Msg[] = [...messagesRef.current, { role: "assistant", content: assistantText }];
        messagesRef.current = updated;
        setMessages(updated);
        void speakWithGemini(assistantText);
        await refreshThreads();
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [token, speakWithGemini, refreshThreads],
  );

  async function selectThread(threadId: string) {
    if (!token || threadId === activeThreadIdRef.current) return;
    setErr("");
    try {
      await hydrateThread(threadId);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not open conversation.");
    }
  }

  async function newChat() {
    if (!token) return;
    setErr("");
    try {
      const created = await apiFetch<{ id: string }>("/advisor/live/threads", token, {
        method: "POST",
      });
      activeThreadIdRef.current = created.id;
      setActiveThreadId(created.id);
      messagesRef.current = [];
      setMessages([]);
      await refreshThreads();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Could not create conversation.");
    }
  }

  function startListen() {
    if (!speechSupported) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.continuous = true;
    rec.maxAlternatives = 1;
    recRef.current = rec;
    setListening(true);
    let fullTranscript = "";
    rec.onresult = (ev) => {
      for (let i = 0; i < ev.results.length; i++) {
        if (ev.results[i].isFinal) {
          fullTranscript += " " + (ev.results[i][0]?.transcript || "");
        }
      }
    };
    rec.onerror = (ev) => {
      if (ev.error !== "no-speech") setListening(false);
    };
    rec.onend = () => {
      setListening(false);
      recRef.current = null;
      const said = fullTranscript.trim();
      if (said && said.length >= 2) {
        void send(said);
      }
    };
    rec.start();
  }

  function stopListen() {
    if (recRef.current) {
      recRef.current.stop();
    }
  }

  function analyzePortfolio() {
    void send(
      "Review my portfolio from your context. List concrete observations tied to my holdings, any stop-loss concerns, and 2–3 specific actions. If a mutual fund switch makes sense, name alternative funds by their full scheme name and explain why.",
    );
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 pb-24 lg:flex-row lg:items-stretch lg:gap-8">
      <aside className="flex w-full shrink-0 flex-col gap-2 lg:w-56">
        <button
          type="button"
          onClick={() => void newChat()}
          disabled={!token || threadsLoading}
          className="rounded-lg bg-mint-500/20 px-3 py-2 text-left text-sm font-medium text-mint-400 hover:bg-mint-500/30 disabled:opacity-40"
        >
          New chat
        </button>
        <div className="max-h-[40vh] overflow-y-auto rounded-xl border border-gray-800 bg-ink-900/40 lg:max-h-[min(70vh,560px)]">
          {threadsLoading ? (
            <p className="p-3 text-xs text-gray-500">Loading…</p>
          ) : threads.length === 0 ? (
            <p className="p-3 text-xs text-gray-500">No chats yet. Send a message to create one.</p>
          ) : (
            <ul className="divide-y divide-gray-800/80">
              {threads.map((th) => (
                <li key={th.id}>
                  <button
                    type="button"
                    onClick={() => void selectThread(th.id)}
                    className={`w-full px-3 py-2.5 text-left text-sm transition-colors ${
                      th.id === activeThreadId
                        ? "bg-mint-500/15 text-mint-100"
                        : "text-gray-300 hover:bg-gray-800/60"
                    }`}
                  >
                    <span className="line-clamp-2 font-medium">{th.title || "Chat"}</span>
                    {th.updatedAt ? (
                      <span className="mt-0.5 block truncate text-[10px] text-gray-600">
                        {String(th.updatedAt).slice(0, 16)}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col gap-6">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Live AI Advisor</h1>
          <p className="mt-2 text-sm text-gray-400">
            Chat grounded in your saved portfolio and goals. Voice uses Gemini AI for natural speech. Not
            personalized SEBI-registered advice.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={analyzePortfolio}
            disabled={!token || loading}
            className="rounded-lg bg-mint-500/20 px-4 py-2 text-sm font-medium text-mint-400 hover:bg-mint-500/30 disabled:opacity-40"
          >
            Analyze my portfolio
          </button>
          {speechSupported ? (
            listening ? (
              <button
                type="button"
                onClick={stopListen}
                className="rounded-lg border border-red-500/60 bg-red-500/20 px-4 py-2 text-sm text-red-300 hover:bg-red-500/30 animate-pulse"
              >
                Stop listening
              </button>
            ) : (
              <button
                type="button"
                onClick={startListen}
                disabled={loading || !token}
                className="rounded-lg border border-gray-600 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-40"
              >
                Voice input
              </button>
            )
          ) : (
            <span className="text-xs text-gray-600 self-center">Voice input needs Chrome / Edge</span>
          )}
          {speaking && (
            <button
              type="button"
              onClick={stopSpeaking}
              className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-4 py-2 text-sm text-amber-300 hover:bg-amber-500/20"
            >
              Stop speaking
            </button>
          )}
          <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-500">
            <input type="checkbox" checked={voiceOut} onChange={(e) => setVoiceOut(e.target.checked)} />
            Read replies aloud
          </label>
        </div>

        <div className="min-h-[320px] space-y-4 rounded-xl border border-gray-800 bg-ink-900/60 p-4">
          {messages.length === 0 && (
            <p className="text-sm text-gray-500">
              Ask anything about your holdings, or tap &quot;Analyze my portfolio&quot; to start. Use the
              sidebar to switch conversations — context is restored for each chat.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={`${i}-${m.role}-${m.content.slice(0, 24)}`}
              className={`rounded-lg px-4 py-3 text-sm ${
                m.role === "user"
                  ? "ml-8 bg-mint-500/10 text-gray-100"
                  : "mr-8 border border-gray-800 bg-ink-950/80 text-gray-200"
              }`}
            >
              <div className="flex items-center justify-between">
                <p className="text-xs text-gray-500">{m.role === "user" ? "You" : "Advisor"}</p>
                {m.role === "assistant" && (
                  <button
                    type="button"
                    onClick={() => void speakWithGemini(m.content)}
                    className="text-xs text-gray-600 hover:text-mint-400"
                    title="Play this reply"
                  >
                    Play
                  </button>
                )}
              </div>
              <p className="mt-1 whitespace-pre-wrap">{m.content}</p>
            </div>
          ))}
          {loading && <p className="text-sm text-gray-500">Thinking...</p>}
          {speaking && <p className="text-xs text-mint-500 animate-pulse">Speaking...</p>}
          <div ref={bottomRef} />
        </div>

        {err && <p className="text-sm text-red-400">{err}</p>}
      </div>

      <form
        className="fixed bottom-0 left-0 right-0 border-t border-gray-800 bg-ink-950/95 p-4 backdrop-blur"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <div className="mx-auto flex max-w-6xl gap-2 px-4 lg:pl-[calc(14rem+2rem)]">
          <input
            className="flex-1 rounded-lg border border-gray-700 bg-ink-900 px-4 py-3 text-sm text-white placeholder:text-gray-600"
            placeholder="Ask about your portfolio..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!token || loading}
          />
          <button
            type="submit"
            disabled={!token || loading || !input.trim()}
            className="rounded-lg bg-mint-500 px-5 py-3 text-sm font-medium text-ink-950 hover:bg-mint-400 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
