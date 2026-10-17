"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Batch = {
  batch_id: number;
  product_name: string;
  organization_id: number;
  produced_at: string;
  status: string;
};

export default function Home() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");

  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((r) => (r.ok ? setApiStatus("ok") : setApiStatus("down")))
      .catch(() => setApiStatus("down"));

    fetch(`${API_URL}/api/batches`)
      .then((r) => r.json())
      .then(setBatches)
      .catch(() => setBatches([]));
  }, []);

  return (
    <main className="mx-auto max-w-4xl p-8">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Tracefront</h1>
        <span
          className={`rounded px-2 py-1 text-xs font-medium ${
            apiStatus === "ok"
              ? "bg-green-100 text-green-700"
              : apiStatus === "down"
                ? "bg-red-100 text-red-700"
                : "bg-slate-100 text-slate-600"
          }`}
        >
          API: {apiStatus}
        </span>
      </header>

      <section>
        <h2 className="mb-2 text-lg font-medium">Batches</h2>
        {batches.length === 0 ? (
          <p className="text-sm text-slate-500">No batches yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b">
                <th className="py-2">ID</th>
                <th className="py-2">Product</th>
                <th className="py-2">Status</th>
                <th className="py-2">Produced at</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.batch_id} className="border-b">
                  <td className="py-2">{b.batch_id}</td>
                  <td className="py-2">{b.product_name}</td>
                  <td className="py-2">{b.status}</td>
                  <td className="py-2">{new Date(b.produced_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
