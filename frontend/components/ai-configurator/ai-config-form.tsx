"use client";

import { useFormState, useFormStatus } from "react-dom";
import { getRagSuggestions, type FormState } from "@/lib/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useEffect, useRef } from "react";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Sparkles } from "lucide-react";

const initialState: FormState = {
  message: "",
};

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending} className="w-full md:w-auto">
      {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" /> }
      Get Suggestions
    </Button>
  );
}

export default function AIConfigForm() {
  const [state, formAction] = useFormState(getRagSuggestions, initialState);
  const { toast } = useToast();
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state.message && state.message !== "Invalid form data" && !state.issues?.length) {
      toast({
        title: state.data ? "Success!" : "Info",
        description: state.message,
        variant: state.data ? "default" : "destructive",
      });
      if (state.data) { // Clear form on success
        formRef.current?.reset();
      }
    } else if (state.issues?.length) {
       toast({
        title: "Validation Error",
        description: state.issues.join("\n"),
        variant: "destructive",
      });
    }
  }, [state, toast]);

  return (
    <div className="space-y-5">
      <form ref={formRef} action={formAction} className="space-y-5">
        <div>
          <Label htmlFor="currentConfiguration" className="font-semibold">Current RAG Configuration</Label>
          <Textarea
            id="currentConfiguration"
            name="currentConfiguration"
            placeholder="Describe your data sources, embedding models, chunking strategies, retrieval methods, etc."
            rows={6}
            required
            defaultValue={state.fields?.currentConfiguration}
            className="mt-1"
          />
          {state.issues?.find(issue => issue.toLowerCase().includes("configuration")) && (
            <p className="text-sm text-destructive mt-1">{state.issues.find(issue => issue.toLowerCase().includes("configuration"))}</p>
          )}
        </div>

        <div>
          <Label htmlFor="performanceMetrics" className="font-semibold">Performance Metrics (Optional)</Label>
          <Input
            id="performanceMetrics"
            name="performanceMetrics"
            placeholder="e.g., Latency: 500ms, Recall: 0.85, Precision: 0.90"
            defaultValue={state.fields?.performanceMetrics}
            className="mt-1"
          />
        </div>

        <div>
          <Label htmlFor="costConstraints" className="font-semibold">Cost Constraints (Optional)</Label>
          <Input
            id="costConstraints"
            name="costConstraints"
            placeholder="e.g., Max $0.01 per query, Max $100/month"
            defaultValue={state.fields?.costConstraints}
            className="mt-1"
          />
        </div>
        
        <SubmitButton />
      </form>

      {state.data && (
        <Card className="shadow-md">
          <CardHeader>
            <CardTitle className="text-xl font-headline flex items-center">
              <Sparkles className="mr-2 h-5 w-5 text-primary" /> AI Generated Suggestions
            </CardTitle>
            <CardDescription>
              Based on your input, here are some potential improvements for your RAG system.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <AlertTitle className="font-semibold">Suggested Improvements</AlertTitle>
              <AlertDescription className="whitespace-pre-wrap font-code">
                {state.data.suggestedImprovements}
              </AlertDescription>
            </Alert>
            <Alert>
              <AlertTitle className="font-semibold">Rationale</AlertTitle>
              <AlertDescription className="whitespace-pre-wrap font-code">
                {state.data.rationale}
              </AlertDescription>
            </Alert>
            {state.data.estimatedImpact && (
              <Alert>
                <AlertTitle className="font-semibold">Estimated Impact</AlertTitle>
                <AlertDescription className="whitespace-pre-wrap font-code">
                  {state.data.estimatedImpact}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
