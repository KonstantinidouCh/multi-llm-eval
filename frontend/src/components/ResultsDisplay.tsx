import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Clock, Zap, DollarSign, Award, AlertCircle, Trophy } from 'lucide-react';
import type { EvaluationResult, LLMResponse } from '@/services/api';

interface ResultsDisplayProps {
  result: EvaluationResult;
}

// Helper to shorten model names for display
function shortenModelName(fullName: string): string {
  if (!fullName) return 'N/A';
  // Extract just the model name without provider prefix if it's in the format "provider/model"
  const parts = fullName.split('/');
  const modelPart = parts[parts.length - 1];
  // Truncate if too long
  if (modelPart.length > 20) {
    return modelPart.slice(0, 18) + '...';
  }
  return modelPart;
}

export function ResultsDisplay({ result }: ResultsDisplayProps) {
  const latencyData = result.responses.map(r => ({
    name: shortenModelName(r.model),
    fullName: `${r.provider}/${r.model}`,
    latency: r.metrics.latency_ms,
    tps: r.metrics.tokens_per_second,
  }));

  const qualityData = result.responses.map(r => ({
    name: shortenModelName(r.model),
    fullName: `${r.provider}/${r.model}`,
    coherence: r.metrics.coherence_score * 100,
    relevance: r.metrics.relevance_score * 100,
    quality: r.metrics.quality_score * 100,
  }));

  const costData = result.responses.map(r => ({
    name: shortenModelName(r.model),
    fullName: `${r.provider}/${r.model}`,
    cost: r.metrics.estimated_cost * 1000,
    inputTokens: r.metrics.input_tokens,
    outputTokens: r.metrics.output_tokens,
  }));

  return (
    <div className="space-y-6">
      <Card className="bg-white dark:bg-slate-800 shadow-lg border-0">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Trophy className="h-5 w-5 text-amber-500" />
            Comparison Summary
          </CardTitle>
          <CardDescription className="truncate">Query: "{result.query}"</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 rounded-xl bg-gradient-to-br from-cyan-50 to-blue-50 dark:from-cyan-950/30 dark:to-blue-950/30 border border-cyan-200 dark:border-cyan-800">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-1.5 rounded-lg bg-cyan-500 text-white">
                  <Clock className="h-4 w-4" />
                </div>
                <span className="text-xs font-medium text-cyan-700 dark:text-cyan-300">Fastest</span>
              </div>
              <p className="font-semibold text-sm text-cyan-900 dark:text-cyan-100 truncate" title={result.comparison_summary.fastest}>
                {shortenModelName(result.comparison_summary.fastest)}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-950/30 dark:to-yellow-950/30 border border-amber-200 dark:border-amber-800">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-1.5 rounded-lg bg-amber-500 text-white">
                  <Award className="h-4 w-4" />
                </div>
                <span className="text-xs font-medium text-amber-700 dark:text-amber-300">Quality</span>
              </div>
              <p className="font-semibold text-sm text-amber-900 dark:text-amber-100 truncate" title={result.comparison_summary.highest_quality}>
                {shortenModelName(result.comparison_summary.highest_quality)}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-50 to-green-50 dark:from-emerald-950/30 dark:to-green-950/30 border border-emerald-200 dark:border-emerald-800">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-1.5 rounded-lg bg-emerald-500 text-white">
                  <DollarSign className="h-4 w-4" />
                </div>
                <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300">Cost Effective</span>
              </div>
              <p className="font-semibold text-sm text-emerald-900 dark:text-emerald-100 truncate" title={result.comparison_summary.most_cost_effective}>
                {shortenModelName(result.comparison_summary.most_cost_effective)}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-950/30 dark:to-purple-950/30 border border-violet-200 dark:border-violet-800">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-1.5 rounded-lg bg-gradient-to-r from-violet-500 to-purple-500 text-white">
                  <Zap className="h-4 w-4" />
                </div>
                <span className="text-xs font-medium text-violet-700 dark:text-violet-300">Best Overall</span>
              </div>
              <p className="font-semibold text-sm text-violet-900 dark:text-violet-100 truncate" title={result.comparison_summary.best_overall}>
                {shortenModelName(result.comparison_summary.best_overall)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="responses" className="w-full">
        <TabsList className="grid w-full grid-cols-4 bg-white dark:bg-slate-800 shadow-sm">
          <TabsTrigger value="responses" className="data-[state=active]:bg-violet-100 data-[state=active]:text-violet-700">Responses</TabsTrigger>
          <TabsTrigger value="performance" className="data-[state=active]:bg-cyan-100 data-[state=active]:text-cyan-700">Performance</TabsTrigger>
          <TabsTrigger value="quality" className="data-[state=active]:bg-amber-100 data-[state=active]:text-amber-700">Quality</TabsTrigger>
          <TabsTrigger value="cost" className="data-[state=active]:bg-emerald-100 data-[state=active]:text-emerald-700">Cost</TabsTrigger>
        </TabsList>

        <TabsContent value="responses" className="space-y-4">
          {result.responses.map((response, index) => (
            <ResponseCard key={index} response={response} />
          ))}
        </TabsContent>

        <TabsContent value="performance">
          <Card className="bg-white dark:bg-slate-800 shadow-md border-0">
            <CardHeader>
              <CardTitle className="text-cyan-700 dark:text-cyan-300">Performance Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={latencyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} tick={{ fill: '#64748b', fontSize: 12 }} />
                    <YAxis yAxisId="left" orientation="left" stroke="#06b6d4" tick={{ fill: '#06b6d4' }} />
                    <YAxis yAxisId="right" orientation="right" stroke="#8b5cf6" tick={{ fill: '#8b5cf6' }} />
                    <Tooltip contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                    <Legend />
                    <Bar yAxisId="left" dataKey="latency" fill="#06b6d4" name="Latency (ms)" radius={[4, 4, 0, 0]} />
                    <Bar yAxisId="right" dataKey="tps" fill="#8b5cf6" name="Tokens/sec" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="quality">
          <Card className="bg-white dark:bg-slate-800 shadow-md border-0">
            <CardHeader>
              <CardTitle className="text-amber-700 dark:text-amber-300">Quality Scores</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={qualityData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" domain={[0, 100]} tick={{ fill: '#64748b' }} />
                    <YAxis dataKey="name" type="category" width={100} tick={{ fill: '#64748b', fontSize: 11 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                    <Legend />
                    <Bar dataKey="coherence" fill="#8b5cf6" name="Coherence" radius={[0, 4, 4, 0]} />
                    <Bar dataKey="relevance" fill="#06b6d4" name="Relevance" radius={[0, 4, 4, 0]} />
                    <Bar dataKey="quality" fill="#f59e0b" name="Overall Quality" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cost">
          <Card className="bg-white dark:bg-slate-800 shadow-md border-0">
            <CardHeader>
              <CardTitle className="text-emerald-700 dark:text-emerald-300">Cost Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={costData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} tick={{ fill: '#64748b', fontSize: 12 }} />
                    <YAxis yAxisId="left" orientation="left" stroke="#10b981" tick={{ fill: '#10b981' }} />
                    <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" tick={{ fill: '#f59e0b' }} />
                    <Tooltip contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                    <Legend />
                    <Bar yAxisId="left" dataKey="cost" fill="#10b981" name="Cost (x0.001$)" radius={[4, 4, 0, 0]} />
                    <Bar yAxisId="right" dataKey="outputTokens" fill="#f59e0b" name="Output Tokens" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ResponseCard({ response }: { response: LLMResponse }) {
  const qualityColor = response.metrics.quality_score > 0.7
    ? 'bg-emerald-500'
    : response.metrics.quality_score > 0.4
    ? 'bg-amber-500'
    : 'bg-red-500';

  return (
    <Card className="bg-white dark:bg-slate-800 shadow-md border-0 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <span className="px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300">
              {response.provider}
            </span>
            <span className="truncate max-w-[200px]" title={response.model}>
              {shortenModelName(response.model)}
            </span>
          </CardTitle>
          <div className="flex gap-2 flex-wrap">
            <Badge className="bg-cyan-100 text-cyan-700 hover:bg-cyan-100 border-0">
              {response.metrics.latency_ms.toFixed(0)}ms
            </Badge>
            <Badge className="bg-violet-100 text-violet-700 hover:bg-violet-100 border-0">
              {response.metrics.tokens_per_second.toFixed(1)} t/s
            </Badge>
            <Badge className={`${qualityColor} text-white hover:${qualityColor} border-0`}>
              Q: {(response.metrics.quality_score * 100).toFixed(0)}%
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {response.error ? (
          <div className="flex items-center gap-2 text-red-600 bg-red-50 dark:bg-red-950/30 p-3 rounded-lg">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm">{response.error}</span>
          </div>
        ) : (
          <>
            <div className="prose prose-sm max-w-none dark:prose-invert mb-4 bg-slate-50 dark:bg-slate-900/50 p-4 rounded-lg">
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{response.response}</p>
            </div>
            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100 dark:border-slate-700">
              <div>
                <p className="text-xs font-medium text-violet-600 dark:text-violet-400 mb-1">Coherence</p>
                <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full transition-all"
                    style={{ width: `${response.metrics.coherence_score * 100}%` }}
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">{(response.metrics.coherence_score * 100).toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-xs font-medium text-cyan-600 dark:text-cyan-400 mb-1">Relevance</p>
                <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all"
                    style={{ width: `${response.metrics.relevance_score * 100}%` }}
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">{(response.metrics.relevance_score * 100).toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-xs font-medium text-amber-600 dark:text-amber-400 mb-1">Quality</p>
                <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full transition-all"
                    style={{ width: `${response.metrics.quality_score * 100}%` }}
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">{(response.metrics.quality_score * 100).toFixed(0)}%</p>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
