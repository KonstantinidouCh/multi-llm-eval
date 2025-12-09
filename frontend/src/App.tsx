import { useState, useEffect } from 'react';
import { QueryInput } from '@/components/QueryInput';
import { ResultsDisplay } from '@/components/ResultsDisplay';
import { llmApi, type EvaluationResult, type LLMProvider } from '@/services/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, History, Settings } from 'lucide-react';

function App() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [currentResult, setCurrentResult] = useState<EvaluationResult | null>(null);
  const [history, setHistory] = useState<EvaluationResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProviders();
    loadHistory();
  }, []);

  const loadProviders = async () => {
    try {
      const data = await llmApi.getProviders();
      setProviders(data);
    } catch (err) {
      console.error('Failed to load providers:', err);
      // Set default providers for demo
      setProviders([
        { id: 'groq', name: 'Groq', models: ['llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'], enabled: true },
        { id: 'huggingface', name: 'HuggingFace', models: ['meta-llama/Meta-Llama-3-8B-Instruct', 'mistralai/Mistral-7B-Instruct-v0.2'], enabled: true },
        { id: 'ollama', name: 'Ollama (Local)', models: ['llama3', 'mistral', 'codellama'], enabled: true },
      ]);
    }
  };

  const loadHistory = async () => {
    try {
      const data = await llmApi.getHistory();
      setHistory(data);
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  const handleSubmit = async (query: string, selectedProviders: string[], selectedModels: Record<string, string>) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await llmApi.evaluate({
        query,
        providers: selectedProviders,
        models: selectedModels,
      });
      setCurrentResult(result);
      setHistory(prev => [result, ...prev]);
    } catch (err) {
      console.error('Evaluation failed:', err);
      setError('Failed to run evaluation. Please check the backend connection.');
    } finally {
      setIsLoading(false);
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
                {!currentResult && !error && (
                  <Card>
                    <CardContent className="pt-6">
                      <p className="text-muted-foreground text-center py-12">
                        Select providers and enter a query to compare LLM responses
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
                            <p className="font-medium truncate max-w-md">{item.query}</p>
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
                  {providers.map(provider => (
                    <div key={provider.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div>
                        <p className="font-medium">{provider.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {provider.models.length} models available
                        </p>
                      </div>
                      <Badge variant={provider.enabled ? 'success' : 'secondary'}>
                        {provider.enabled ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-muted-foreground mt-4">
                  Configure API keys in the backend .env file to enable providers.
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
