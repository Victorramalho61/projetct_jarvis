import { useEffect, useState } from "react";

type HealthResponse = {
  api: string;
  db: string;
};

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/health", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<HealthResponse>;
      })
      .then(setHealth)
      .catch((e: Error) => {
        if (e.name !== "AbortError") {
          console.error("Health check failed:", e.message);
          setError(e.message);
        }
      });

    return () => controller.abort();
  }, []);

  const dbColor =
    health?.db === "ok"
      ? "text-green-600"
      : health?.db === "degraded"
        ? "text-yellow-500"
        : "text-red-500";

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="rounded-xl border bg-white p-10 shadow-md text-center space-y-2">
        <h1 className="text-2xl font-bold text-gray-900">
          React + FastAPI + Supabase
        </h1>
        {error ? (
          <p className="text-sm text-red-500">Erro: {error}</p>
        ) : (
          <>
            <p className="text-gray-500">
              API:{" "}
              <span className={health ? "font-medium text-green-600" : "text-gray-400"}>
                {health?.api ?? "conectando..."}
              </span>
            </p>
            <p className="text-gray-500">
              DB:{" "}
              <span className={health ? `font-medium ${dbColor}` : "text-gray-400"}>
                {health?.db ?? "verificando..."}
              </span>
            </p>
          </>
        )}
      </div>
    </main>
  );
}
