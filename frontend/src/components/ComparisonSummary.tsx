import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import type { ComparisonSummary, EvaluationResult } from "@/types/api";
import { Award, Clock, DollarSign, Trophy, Zap } from "lucide-react";

export function ComparisonSummary({ result }: { result: EvaluationResult }) {
  // Helper to shorten model names for display
  function shortenModelName(fullName: string): string {
    if (!fullName) return "N/A";
    // Extract just the model name without provider prefix if it's in the format "provider/model"
    const parts = fullName.split("/");
    const modelPart = parts[parts.length - 1];
    // Truncate if too long
    if (modelPart.length > 20) {
      return modelPart.slice(0, 18) + "...";
    }
    return modelPart;
  }

  return (
    <Card className="bg-white dark:bg-slate-800 shadow-lg border-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Trophy className="h-5 w-5 text-amber-500" />
          Comparison Summary
        </CardTitle>
        <CardDescription className="truncate">
          Query: "{result.query}"
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-4 rounded-xl bg-gradient-to-br from-cyan-50 to-blue-50 dark:from-cyan-950/30 dark:to-blue-950/30 border border-cyan-200 dark:border-cyan-800">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-1.5 rounded-lg bg-cyan-500 text-white">
                <Clock className="h-4 w-4" />
              </div>
              <span className="text-xs font-medium text-cyan-700 dark:text-cyan-300">
                Fastest
              </span>
            </div>
            <p
              className="font-semibold text-sm text-cyan-900 dark:text-cyan-100 truncate"
              title={result.comparison_summary.fastest}
            >
              {shortenModelName(result.comparison_summary.fastest)}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-950/30 dark:to-yellow-950/30 border border-amber-200 dark:border-amber-800">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-1.5 rounded-lg bg-amber-500 text-white">
                <Award className="h-4 w-4" />
              </div>
              <span className="text-xs font-medium text-amber-700 dark:text-amber-300">
                Quality
              </span>
            </div>
            <p
              className="font-semibold text-sm text-amber-900 dark:text-amber-100 truncate"
              title={result.comparison_summary.highest_quality}
            >
              {shortenModelName(result.comparison_summary.highest_quality)}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-50 to-green-50 dark:from-emerald-950/30 dark:to-green-950/30 border border-emerald-200 dark:border-emerald-800">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-1.5 rounded-lg bg-emerald-500 text-white">
                <DollarSign className="h-4 w-4" />
              </div>
              <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300">
                Cost Effective
              </span>
            </div>
            <p
              className="font-semibold text-sm text-emerald-900 dark:text-emerald-100 truncate"
              title={result.comparison_summary.most_cost_effective}
            >
              {shortenModelName(result.comparison_summary.most_cost_effective)}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-950/30 dark:to-purple-950/30 border border-violet-200 dark:border-violet-800">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-1.5 rounded-lg bg-gradient-to-r from-violet-500 to-purple-500 text-white">
                <Zap className="h-4 w-4" />
              </div>
              <span className="text-xs font-medium text-violet-700 dark:text-violet-300">
                Best Overall
              </span>
            </div>
            <p
              className="font-semibold text-sm text-violet-900 dark:text-violet-100 truncate"
              title={result.comparison_summary.best_overall}
            >
              {shortenModelName(result.comparison_summary.best_overall)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
