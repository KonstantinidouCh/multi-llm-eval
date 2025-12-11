import { useState, useEffect } from "react";
import { QueryInput } from "@/components/QueryInput";
import { ResultsDisplay } from "@/components/ResultsDisplay";
import { llmApi } from "@/services/api";
import {
  type EvaluationResult,
  type LLMProvider,
  type ModelSelection,
  type StreamEvent,
} from "@/types/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Activity,
  History,
  Settings,
  CheckCircle2,
  Loader2,
  AlertCircle,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { ComparisonSummary } from "./components/ComparisonSummary";

function App() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [currentResult, setCurrentResult] = useState<EvaluationResult | null>(
    null
  );
  const [history, setHistory] = useState<EvaluationResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Streaming state
  const [streamingStatus, setStreamingStatus] = useState<string | null>(null);
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadProviders();
    loadHistory();
  }, []);

  const loadProviders = async () => {
    try {
      const data = await llmApi.getProviders();
      setProviders(data);
    } catch (err) {
      console.error("Failed to load providers:", err);
      setProviders([
        {
          id: "groq",
          name: "Groq",
          models: [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
          ],
          enabled: true,
        },
        {
          id: "huggingface",
          name: "HuggingFace",
          models: [
            "HuggingFaceH4/zephyr-7b-beta",
            "tiiuae/falcon-7b-instruct",
            "google/flan-t5-base",
          ],
          enabled: true,
        },
        {
          id: "ollama",
          name: "Ollama (Local)",
          models: ["llama3", "mistral", "codellama"],
          enabled: true,
        },
      ]);
    }
  };

  const loadHistory = async () => {
    try {
      const data = await llmApi.getHistory();
      setHistory(data);
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const handleStreamEvent = (event: StreamEvent) => {
    switch (event.type) {
      case "node_complete":
        if (event.node) {
          setCompletedNodes((prev) => [...prev, event.node!]);
          // Map node names to user-friendly status
          const statusMap: Record<string, string> = {
            validate_input: "Validated input",
            parallel_evaluation: "Evaluating models...",
            retry_failed: "Retrying failed models...",
            error_recovery: "Recovering from errors...",
            calculate_metrics: "Calculating metrics...",
            llm_judge: "LLM Judge evaluating responses...",
            generate_summary: "Generating summary...",
          };
          setStreamingStatus(statusMap[event.node] || event.node);
        }
        break;
      case "error":
        setError(event.error || "An error occurred");
        break;
      case "complete":
        if (event.result) {
          setCurrentResult(event.result);
          setHistory((prev) => [event.result!, ...prev]);
        }
        break;
    }
  };

  const handleSubmit = async (query: string, selections: ModelSelection[]) => {
    setIsLoading(true);
    setError(null);
    setStreamingStatus("Starting evaluation...");
    setCompletedNodes([]);
    setCurrentResult(null);

    try {
      await llmApi.evaluateStream({ query, selections }, handleStreamEvent);
    } catch (err) {
      console.error("Evaluation failed:", err);
      setError(
        "Failed to run evaluation. Please check the backend connection."
      );
    } finally {
      setIsLoading(false);
      setStreamingStatus(null);
    }
  };

  const allNodes = [
    "validate_input",
    "parallel_evaluation",
    "retry_failed",
    "error_recovery",
    "calculate_metrics",
    "llm_judge",
    "generate_summary",
  ];

  const nodeLabels: Record<string, string> = {
    validate_input: "Validate",
    parallel_evaluation: "Evaluate",
    retry_failed: "Retry",
    error_recovery: "Recovery",
    calculate_metrics: "Metrics",
    llm_judge: "Judge",
    generate_summary: "Summary",
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <header className="border-b bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 text-white">
                <Activity className="h-5 w-5" />
              </div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-violet-600 to-purple-600 bg-clip-text text-transparent">
                Multi-LLM Eval
              </h1>
            </div>
            <Badge
              variant="outline"
              className="border-violet-300 text-violet-600"
            >
              v0.1.0
            </Badge>
          </div>
        </div>
      </header>

      {/* Streaming Progress Bar - Fixed at top */}
      {isLoading && (
        <div className="bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-lg">
          <div className="container mx-auto px-4 py-3">
            <div className="flex items-center gap-4">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="font-medium">{streamingStatus}</span>
              <div className="flex-1 flex items-center gap-1">
                {allNodes.map((node, i) => {
                  const isCompleted = completedNodes.includes(node);
                  const isCurrent = !isCompleted && completedNodes.length === i;
                  return (
                    <div key={node} className="flex items-center">
                      <div
                        className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium transition-all ${
                          isCompleted
                            ? "bg-white/30 text-white"
                            : isCurrent
                            ? "bg-white text-purple-600 animate-pulse"
                            : "bg-white/10 text-white/50"
                        }`}
                      >
                        {isCompleted && <CheckCircle2 className="h-3 w-3" />}
                        {nodeLabels[node]}
                      </div>
                      {i < allNodes.length - 1 && (
                        <div
                          className={`w-4 h-0.5 mx-1 ${
                            isCompleted ? "bg-white/50" : "bg-white/20"
                          }`}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
              <Progress
                value={(completedNodes.length / allNodes.length) * 100}
                className="w-24 h-2 bg-white/20"
              />
            </div>
          </div>
        </div>
      )}

      <main className="container mx-auto px-4 py-6">
        <Tabs defaultValue="evaluate" className="space-y-6">
          <TabsList className="bg-white dark:bg-slate-800 shadow-sm">
            <TabsTrigger
              value="evaluate"
              className="flex items-center gap-2 data-[state=active]:bg-violet-100 data-[state=active]:text-violet-700"
            >
              <Activity className="h-4 w-4" />
              Evaluate
            </TabsTrigger>
            <TabsTrigger
              value="history"
              className="flex items-center gap-2 data-[state=active]:bg-violet-100 data-[state=active]:text-violet-700"
            >
              <History className="h-4 w-4" />
              History
            </TabsTrigger>
            <TabsTrigger
              value="settings"
              className="flex items-center gap-2 data-[state=active]:bg-violet-100 data-[state=active]:text-violet-700"
            >
              <Settings className="h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>

          <TabsContent value="evaluate" className="space-y-6">
            {/* Error display at top */}
            {error && (
              <Card className="border-red-300 bg-red-50 dark:bg-red-950/30">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertCircle className="h-5 w-5" />
                    <p className="font-medium">{error}</p>
                  </div>
                </CardContent>
              </Card>
            )}

            <div className="grid lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1">
                <QueryInput
                  providers={providers}
                  onSubmit={handleSubmit}
                  isLoading={isLoading}
                />
              </div>

              <div className="lg:col-span-2">
                {currentResult && <ResultsDisplay result={currentResult} />}
                {!currentResult && !error && !isLoading && (
                  <Card className="border-dashed border-2 border-slate-200 dark:border-slate-700 bg-white/50 dark:bg-slate-800/50">
                    <CardContent className="pt-6">
                      <div className="text-center py-12">
                        <div className="mx-auto w-16 h-16 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mb-4">
                          <Activity className="h-8 w-8 text-violet-500" />
                        </div>
                        <p className="text-muted-foreground">
                          Select models and enter a query to compare LLM
                          responses
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="history">
            <Card>
              <CardHeader>
                <CardTitle>Evaluation History</CardTitle>
              </CardHeader>
              <CardContent>
                {history.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">
                    No evaluations yet. Run your first comparison!
                  </p>
                ) : (
                  <div className="space-y-4">
                    {history.map((item, index) => {
                      const itemId = item.id || `item-${index}`;
                      const isExpanded = expandedItems.has(itemId);
                      const toggleExpanded = () => {
                        setExpandedItems((prev) => {
                          const newSet = new Set(prev);
                          if (newSet.has(itemId)) {
                            newSet.delete(itemId);
                          } else {
                            newSet.add(itemId);
                          }
                          return newSet;
                        });
                      };

                      return (
                        <div
                          key={itemId}
                          className="p-4 border rounded-lg cursor-pointer hover:bg-muted/50"
                          onClick={toggleExpanded}
                        >
                          <div className="flex items-start gap-4">
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">
                                {item.query}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {item.responses.length} responses compared
                              </p>
                            </div>
                            <Badge variant="outline" className="shrink-0">
                              {new Date(item.timestamp).toLocaleDateString()}
                            </Badge>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 shrink-0"
                            >
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4 text-slate-500" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-slate-500" />
                              )}
                            </Button>
                          </div>
                          <div
                            className={`grid transition-[grid-template-rows] duration-300 ease-out ${
                              isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
                            }`}
                          >
                            <div className="overflow-hidden">
                              <div className="p-4 text-slate-600 dark:text-slate-300 leading-relaxed border-t border-violet-100 dark:border-violet-900/50 mt-2">
                                <ComparisonSummary result={item} />
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle>Provider Configuration</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {providers.map((provider) => (
                    <div
                      key={provider.id}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div>
                        <p className="font-medium">{provider.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {provider.models.length} models available
                        </p>
                      </div>
                      <Badge
                        variant={provider.enabled ? "default" : "secondary"}
                      >
                        {provider.enabled ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-muted-foreground mt-4">
                  Configure API keys in the backend .env file to enable
                  providers.
                </p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

export default App;
