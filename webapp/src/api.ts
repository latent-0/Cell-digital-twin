import type {
  Assim, BayesFit, Combination, DoseResponse, Graph, SimulationResult, Toxin,
} from "./types";

// In dev, Vite proxies /api -> the FastAPI backend (see vite.config.ts).
// Override with VITE_API_BASE for a deployed backend.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${path} -> ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  cells: () => get<string[]>("/cells"),
  toxins: () => get<Toxin[]>("/toxins"),
  graph: (cell: string) => get<Graph>(`/cells/${cell}/graph`),
  simulate: (cell: string, toxin: string, dose: number, hours = 24) =>
    post<SimulationResult>("/simulate", {
      cell_id: cell, exposures: [{ toxin_id: toxin, dose }], duration_h: hours,
    }),
  doseResponse: (toxin: string, cell: string, hours = 24) =>
    get<DoseResponse>(`/dose-response/${toxin}?cell_id=${cell}&hours=${hours}`),
  combine: (cell: string, exposures: { toxin_id: string; dose: number }[]) =>
    post<Combination>(`/combine?cell_id=${cell}`, exposures),
  fitBayes: (toxin: string, cell: string) =>
    get<BayesFit>(`/fit-bayes/${toxin}?cell_id=${cell}`),
  assimilate: () => get<Assim>("/assimilate"),
};

// Pretty cell names come from the graph metadata; the /cells endpoint returns ids.
export const CELL_NAMES: Record<string, string> = {
  hepatocyte: "Human hepatocyte",
  cardiomyocyte: "Cardiomyocyte",
  neuron: "Neuron",
  proximal_tubule: "Renal proximal tubule",
  cancer_cell: "Tumor cell line",
};
export const cellLabel = (id: string) => CELL_NAMES[id] ?? id;
