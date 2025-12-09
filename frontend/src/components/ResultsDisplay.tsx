import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';
import { Clock, Zap, DollarSign, Award, AlertCircle } from 'lucide-react';
import type { EvaluationResult, LLMResponse } from '@/services/api';

interface ResultsDisplayProps {
  result: EvaluationResult;
}

export function ResultsDisplay({ result }: ResultsDisplayProps) {
  const latencyData = result.responses.map(r => ({
    name: `${r.provider}/${r.model}`,
    latency: r.metrics.latency_ms,
    tps: r.metrics.tokens_per_second,
  }));

  const qualityData = result.responses.map(r => ({
    name: `${r.provider}/${r.model}`,
    coherence: r.metrics.coherence_score * 100,
    relevance: r.metrics.relevance_score * 100,
    quality: r.metrics.quality_score * 100,
  }));

  const radarData = result.responses.map(r => ({
    subject: `${r.provider}`,
    speed: Math.max(0, 100 - (r.metrics.latency_ms / 50)),
    quality: r.metrics.quality_score * 100,
    coherence: r.metrics.coherence_score * 100,
    relevance: r.metrics.relevance_score * 100,
    cost: Math.max(0, 100 - (r.metrics.estimated_cost * 1000)),
  }));

  const costData = result.responses.map(r => ({
    name: `${r.provider}/${r.model}`,
    cost: r.metrics.estimated_cost * 1000,
    inputTokens: r.metrics.input_tokens,
    outputTokens: r.metrics.output_tokens,
  }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Comparison Summary</CardTitle>
          <CardDescription>Query: "{result.query}"</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-2 p-3 rounded-lg bg-muted">
              <Clock className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-xs text-muted-foreground">Fastest</p>
                <p className="font-medium">{result.comparison_summary.fastest}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-3 rounded-lg bg-muted">
              <Award className="h-5 w-5 text-yellow-500" />
              <div>
                <p className="text-xs text-muted-foreground">Highest Quality</p>
                <p className="font-medium">{result.comparison_summary.highest_quality}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-3 rounded-lg bg-muted">
              <DollarSign className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-xs text-muted-foreground">Most Cost Effective</p>
                <p className="font-medium">{result.comparison_summary.most_cost_effective}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-3 rounded-lg bg-muted">
              <Zap className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-xs text-muted-foreground">Best Overall</p>
                <p className="font-medium">{result.comparison_summary.best_overall}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="responses" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="responses">Responses</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="cost">Cost</TabsTrigger>
        </TabsList>

        <TabsContent value="responses" className="space-y-4">
          {result.responses.map((response, index) => (
            <ResponseCard key={index} response={response} />
          ))}
        </TabsContent>

        <TabsContent value="performance">
          <Card>
            <CardHeader>
              <CardTitle>Performance Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={latencyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                    <YAxis yAxisId="left" orientation="left" stroke="#8884d8" />
                    <YAxis yAxisId="right" orientation="right" stroke="#82ca9d" />
                    <Tooltip />
                    <Legend />
                    <Bar yAxisId="left" dataKey="latency" fill="#8884d8" name="Latency (ms)" />
                    <Bar yAxisId="right" dataKey="tps" fill="#82ca9d" name="Tokens/sec" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="quality">
          <div className="grid md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Quality Scores</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={qualityData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" domain={[0, 100]} />
                      <YAxis dataKey="name" type="category" width={120} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="coherence" fill="#8884d8" name="Coherence" />
                      <Bar dataKey="relevance" fill="#82ca9d" name="Relevance" />
                      <Bar dataKey="quality" fill="#ffc658" name="Overall Quality" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Radar Comparison</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={radarData}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="subject" />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} />
                      <Radar
                        name="Metrics"
                        dataKey="quality"
                        stroke="#8884d8"
                        fill="#8884d8"
                        fillOpacity={0.6}
                      />
                      <Tooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="cost">
          <Card>
            <CardHeader>
              <CardTitle>Cost Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={costData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                    <YAxis yAxisId="left" orientation="left" stroke="#8884d8" />
                    <YAxis yAxisId="right" orientation="right" stroke="#82ca9d" />
                    <Tooltip />
                    <Legend />
                    <Bar yAxisId="left" dataKey="cost" fill="#8884d8" name="Cost (x0.001$)" />
                    <Bar yAxisId="right" dataKey="outputTokens" fill="#82ca9d" name="Output Tokens" />
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
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">
            {response.provider} / {response.model}
          </CardTitle>
          <div className="flex gap-2">
            <Badge variant="outline">{response.metrics.latency_ms.toFixed(0)}ms</Badge>
            <Badge variant="outline">{response.metrics.tokens_per_second.toFixed(1)} t/s</Badge>
            <Badge variant={response.metrics.quality_score > 0.7 ? 'success' : 'warning'}>
              Q: {(response.metrics.quality_score * 100).toFixed(0)}%
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {response.error ? (
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{response.error}</span>
          </div>
        ) : (
          <>
            <div className="prose prose-sm max-w-none dark:prose-invert mb-4">
              <p className="whitespace-pre-wrap">{response.response}</p>
            </div>
            <div className="grid grid-cols-3 gap-4 pt-4 border-t">
              <div>
                <p className="text-xs text-muted-foreground">Coherence</p>
                <Progress value={response.metrics.coherence_score * 100} className="h-2" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Relevance</p>
                <Progress value={response.metrics.relevance_score * 100} className="h-2" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Quality</p>
                <Progress value={response.metrics.quality_score * 100} className="h-2" />
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
