export interface LLMProvider {
  id: string;
  name: string;
  models: string[];
  enabled: boolean;
}

export interface ModelSelection {
  provider: string;
  model: string;
}

export interface EvaluationRequest {
  query: string;
  selections: ModelSelection[];
}

export interface MetricResult {
  latency_ms: number;
  tokens_per_second: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  coherence_score: number;
  relevance_score: number;
  quality_score: number;
}

export interface LLMResponse {
  provider: string;
  model: string;
  response: string;
  metrics: MetricResult;
  error?: string;
}

export interface EvaluationResult {
  id: string;
  query: string;
  timestamp: string;
  responses: LLMResponse[];
  comparison_summary: ComparisonSummary;
}

export interface ComparisonSummary {
  fastest: string;
  highest_quality: string;
  most_cost_effective: string;
  best_overall: string;
}

export interface StreamEvent {
  type: "node_start" | "node_complete" | "error" | "complete";
  node?: string;
  data?: any;
  error?: string;
  result?: EvaluationResult;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string | null;
}

export interface ChatResponse {
  message: ChatMessage;
  session_id: string;
}
