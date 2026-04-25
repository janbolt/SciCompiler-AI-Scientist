"use client";
import { useState } from "react";

export default function Home() {
  const [q, setQ] = useState("");
  const [out, setOut] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    const r = await fetch("/api/demo/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scientific_question: q, constraints: {} }),
    });
    setOut(await r.json());
    setLoading(false);
  }

  return (
    <main className="mx-auto max-w-3xl p-8 space-y-4">
      <h1 className="text-2xl font-semibold">PredictiveBio</h1>
      <textarea
        className="w-full border rounded p-3"
        rows={4}
        placeholder="Enter a scientific hypothesis..."
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <button
        onClick={run}
        disabled={loading || !q}
        className="bg-black text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? "Generating..." : "Generate plan"}
      </button>
      {out && <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto">{JSON.stringify(out, null, 2)}</pre>}
    </main>
  );
}
