import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, X } from 'lucide-react';

interface Provider {
  id: string;
  name: string;
  models: string[];
  enabled: boolean;
}

interface ModelSelection {
  provider: string;
  model: string;
}

interface QueryInputProps {
  providers: Provider[];
  onSubmit: (query: string, selections: ModelSelection[]) => void;
  isLoading: boolean;
}

export function QueryInput({ providers, onSubmit, isLoading }: QueryInputProps) {
  const [query, setQuery] = useState('');
  const [selections, setSelections] = useState<ModelSelection[]>([]);

  const toggleModel = (providerId: string, model: string) => {
    setSelections(prev => {
      const exists = prev.some(s => s.provider === providerId && s.model === model);
      if (exists) {
        return prev.filter(s => !(s.provider === providerId && s.model === model));
      } else {
        return [...prev, { provider: providerId, model }];
      }
    });
  };

  const isModelSelected = (providerId: string, model: string) => {
    return selections.some(s => s.provider === providerId && s.model === model);
  };

  const removeSelection = (providerId: string, model: string) => {
    setSelections(prev => prev.filter(s => !(s.provider === providerId && s.model === model)));
  };

  const handleSubmit = () => {
    if (query.trim() && selections.length > 0) {
      onSubmit(query, selections);
    }
  };

  const getProviderName = (providerId: string) => {
    return providers.find(p => p.id === providerId)?.name || providerId;
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
          <Label>Select Models to Compare</Label>
          <div className="space-y-3">
            {providers.map(provider => (
              <div key={provider.id} className="space-y-2">
                <div className="text-sm font-medium text-muted-foreground">
                  {provider.name}
                  {!provider.enabled && ' (unavailable)'}
                </div>
                <div className="flex flex-wrap gap-2">
                  {provider.models.map(model => (
                    <Badge
                      key={`${provider.id}-${model}`}
                      variant={isModelSelected(provider.id, model) ? 'default' : 'outline'}
                      className={`cursor-pointer ${!provider.enabled ? 'opacity-50' : ''}`}
                      onClick={() => provider.enabled && toggleModel(provider.id, model)}
                    >
                      {model}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {selections.length > 0 && (
          <div className="space-y-2">
            <Label>Selected Models ({selections.length})</Label>
            <div className="flex flex-wrap gap-2">
              {selections.map(sel => (
                <Badge
                  key={`${sel.provider}-${sel.model}`}
                  variant="secondary"
                  className="flex items-center gap-1"
                >
                  <span className="text-xs text-muted-foreground">{getProviderName(sel.provider)}:</span>
                  {sel.model}
                  <X
                    className="h-3 w-3 cursor-pointer hover:text-destructive"
                    onClick={() => removeSelection(sel.provider, sel.model)}
                  />
                </Badge>
              ))}
            </div>
          </div>
        )}

        <Button
          onClick={handleSubmit}
          disabled={!query.trim() || selections.length === 0 || isLoading}
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
              Compare {selections.length} Model{selections.length !== 1 ? 's' : ''}
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
