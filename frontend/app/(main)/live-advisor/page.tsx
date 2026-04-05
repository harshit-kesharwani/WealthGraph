"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string };

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

export default function LiveAdvisorPage() {
  const { token } = useAuth();
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

  const speechSupported =
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const speakWithGemini = useCallback(
    async (text: string) => {
      if (!voiceOut || !token || !text) return;
      try {
        setSpeaking(true);
        const resp = await fetch(
          "/api/advisor/tts",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ text: text.slice(0, 5000), voice: "Kore" }),
          },
        );
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
          body: JSON.stringify({ messages: payload }),
        });
        const assistantText = r.reply || "";
        const updated: Msg[] = [...messagesRef.current, { role: "assistant", content: assistantText }];
        messagesRef.current = updated;
        setMessages(updated);
        void speakWithGemini(assistantText);
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [token, speakWithGemini],
  );

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
    <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-24">
      <div>
        <h1 className="font-display text-3xl font-bold text-white">Live AI Advisor</h1>
        <p className="mt-2 text-sm text-gray-400">
          Chat grounded in your saved portfolio and goals. Voice uses Gemini AI for natural speech. Not personalized SEBI-registered advice.
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
            Ask anything about your holdings, or tap &quot;Analyze my portfolio&quot; to start.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
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

      <form
        className="fixed bottom-0 left-0 right-0 border-t border-gray-800 bg-ink-950/95 p-4 backdrop-blur"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <div className="mx-auto flex max-w-3xl gap-2">
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
