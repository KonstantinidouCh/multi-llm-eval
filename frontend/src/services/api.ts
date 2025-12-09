import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface LLMProvider {
  id: string;
  name: string;
  models: string[];
  enabled: boolean;
}

export interface EvaluationRequest {
  query: string;
  providers: string[];
  models: Record<string, string>;
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
  comparison_summary: {
    fastest: string;
    highest_quality: string;
    most_cost_effective: string;
    best_overall: string;
  };
}

export const llmApi = {
  getProviders: async (): Promise<LLMProvider[]> => {
    const response = await api.get('/providers');
    return response.data;
  },

  evaluate: async (request: EvaluationRequest): Promise<EvaluationResult> => {
    const response = await api.post('/evaluate', request);
    return response.data;
  },

  getHistory: async (): Promise<EvaluationResult[]> => {
    const response = await api.get('/history');
    return response.data;
  },

  getEvaluation: async (id: string): Promise<EvaluationResult> => {
    const response = await api.get(`/evaluations/${id}`);
    return response.data;
  },
};

export default api;
