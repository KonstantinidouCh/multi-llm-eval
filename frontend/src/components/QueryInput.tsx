import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2 } from 'lucide-react';

interface Provider {
  id: string;
  name: string;
  models: string[];
  enabled: boolean;
}

interface QueryInputProps {
  providers: Provider[];
  onSubmit: (query: string, selectedProviders: string[], selectedModels: Record<string, string>) => void;
  isLoading: boolean;
}

export function QueryInput({ providers, onSubmit, isLoading }: QueryInputProps) {
  const [query, setQuery] = useState('');
  const [selectedProviders, setSelectedProviders] = useState<string[]>([]);
  const [selectedModels, setSelectedModels] = useState<Record<string, string>>({});

  const toggleProvider = (providerId: string) => {
    setSelectedProviders(prev => {
      if (prev.includes(providerId)) {
        const newSelected = prev.filter(id => id !== providerId);
        const newModels = { ...selectedModels };
        delete newModels[providerId];
        setSelectedModels(newModels);
        return newSelected;
      } else {
        const provider = providers.find(p => p.id === providerId);
        if (provider && provider.models.length > 0) {
          setSelectedModels(prev => ({
            ...prev,
            [providerId]: provider.models[0]
          }));
        }
        return [...prev, providerId];
      }
    });
  };

  const handleModelChange = (providerId: string, model: string) => {
    setSelectedModels(prev => ({
      ...prev,
      [providerId]: model
    }));
  };

  const handleSubmit = () => {
    if (query.trim() && selectedProviders.length > 0) {
      onSubmit(query, selectedProviders, selectedModels);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM Comparison Query</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="query">Enter your query</Label>
          <Textarea
            id="query"
            placeholder="Type your question or prompt here..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-h-[100px]"
          />
        </div>

        <div className="space-y-2">
          <Label>Select LLM Providers</Label>
          <div className="flex flex-wrap gap-2">
            {providers.map(provider => (
              <Badge
                key={provider.id}
                variant={selectedProviders.includes(provider.id) ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => provider.enabled && toggleProvider(provider.id)}
              >
                {provider.name}
                {!provider.enabled && ' (unavailable)'}
              </Badge>
            ))}
          </div>
        </div>

        {selectedProviders.length > 0 && (
          <div className="space-y-2">
            <Label>Select Models</Label>
            <div className="grid gap-2">
              {selectedProviders.map(providerId => {
                const provider = providers.find(p => p.id === providerId);
                if (!provider) return null;
                return (
                  <div key={providerId} className="flex items-center gap-2">
                    <span className="text-sm font-medium w-32">{provider.name}:</span>
                    <select
                      value={selectedModels[providerId] || ''}
                      onChange={(e) => handleModelChange(providerId, e.target.value)}
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                    >
                      {provider.models.map(model => (
                        <option key={model} value={model}>{model}</option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <Button
          onClick={handleSubmit}
          disabled={!query.trim() || selectedProviders.length === 0 || isLoading}
          className="w-full"
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Running Evaluation...
            </>
          ) : (
            <>
              <Send className="mr-2 h-4 w-4" />
              Compare LLMs
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
