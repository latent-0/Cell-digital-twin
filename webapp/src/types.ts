export interface Cell { id: string; name: string; cyp?: number }
export interface Target { node: string; effect: string; process: string | null }
export interface Toxin {
  id: string; name: string; class: string; description: string;
  requires_bioactivation: boolean; targets: Target[];
}
export interface GraphNode {
  id: string; label: string; type: string; process?: string | null;
  compartment?: string | null; x: number; y: number;
}
export interface GraphEdge { source: string; target: string; type: string; sign: number }
export interface Graph { nodes: GraphNode[]; edges: GraphEdge[] }

export interface TimePoint {
  t: number; atp: number; ros: number; gsh: number;
  caspase: number; membrane: number; viability: number;
}
export interface Mechanism {
  dominant: string; apoptotic: number; necrotic: number;
  energy_failure: number; oxidative_stress: number; narrative: string;
}
export interface SimulationResult {
  cell_id: string; duration_h: number; trajectory: TimePoint[];
  final_viability: number; mechanism: Mechanism;
}
export interface DoseResponse {
  toxin_id: string; cell_id: string; duration_h: number;
  curve: { dose: number; viability: number }[];
  ic50: number | null; hill: number | null;
}
export interface Combination {
  observed_viability: number; expected_bliss: number;
  synergy: number; interpretation: string;
}
export interface BayesFit {
  toxin: string; grid: number[]; median: number[]; lo: number[]; hi: number[];
  obsDoses: number[]; obs: number[][];
  ic50: { median: number; lo: number; hi: number };
  rHat: number; shrinkage: number; verdict: string;
}
export interface Assim {
  truth: number; times: number[]; mean: number[]; lo: number[]; hi: number[];
}
