import { useState, useEffect } from "react";
import { QueryInput } from "@/components/QueryInput";
import { ResultsDisplay } from "@/components/ResultsDisplay";
import {
  llmApi,
  type EvaluationResult,
  type LLMProvider,
  type ModelSelection,
  type StreamEvent,
} from "@/services/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, History, Settings } from "lucide-react";

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
            calculate_metrics: "Calculating metrics...",
            run_tools: "Running analysis tools...",
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

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-6 w-6" />
              <h1 className="text-xl font-bold">Multi-LLM Eval</h1>
            </div>
            <Badge variant="outline">v0.1.0</Badge>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <Tabs defaultValue="evaluate" className="space-y-6">
          <TabsList>
            <TabsTrigger value="evaluate" className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Evaluate
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <History className="h-4 w-4" />
              History
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>

          <TabsContent value="evaluate" className="space-y-6">
            <div className="grid lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1">
                <QueryInput
                  providers={providers}
                  onSubmit={handleSubmit}
                  isLoading={isLoading}
                />

                {/* Streaming Progress */}
                {isLoading && streamingStatus && (
                  <Card className="mt-4">
                    <CardContent className="pt-4">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-2 bg-blue-500 rounded-full animate-pulse" />
                          <span className="text-sm font-medium">
                            {streamingStatus}
                          </span>
                        </div>
                        {completedNodes.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {completedNodes.map((node, i) => (
                              <Badge
                                key={i}
                                variant="secondary"
                                className="text-xs"
                              >
                                {node}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>

              <div className="lg:col-span-2">
                {error && (
                  <Card className="border-destructive">
                    <CardContent className="pt-6">
                      <p className="text-destructive">{error}</p>
                    </CardContent>
                  </Card>
                )}
                {currentResult && <ResultsDisplay result={currentResult} />}
                {!currentResult && !error && !isLoading && (
                  <Card>
                    <CardContent className="pt-6">
                      <p className="text-muted-foreground text-center py-12">
                        Select providers and enter a query to compare LLM
                        responses
                      </p>
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
                    {history.map((item, index) => (
                      <div
                        key={item.id || index}
                        className="p-4 border rounded-lg cursor-pointer hover:bg-muted/50"
                        onClick={() => setCurrentResult(item)}
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-medium truncate max-w-md">
                              {item.query}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {item.responses.length} responses compared
                            </p>
                          </div>
                          <Badge variant="outline">
                            {new Date(item.timestamp).toLocaleDateString()}
                          </Badge>
                        </div>
                      </div>
                    ))}
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
