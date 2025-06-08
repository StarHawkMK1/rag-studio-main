"use server";

import { suggestRagConfiguration, type RagConfigurationInput, type RagConfigurationOutput } from "@/ai/flows/rag-configuration-tool";
import { z } from "zod";

const RagConfigSchema = z.object({
  currentConfiguration: z.string().min(10, "Current configuration must be at least 10 characters."),
  performanceMetrics: z.string().optional(),
  costConstraints: z.string().optional(),
});

export interface FormState {
  message: string;
  fields?: Record<string, string>;
  issues?: string[];
  data?: RagConfigurationOutput;
}

export async function getRagSuggestions(
  prevState: FormState,
  data: FormData
): Promise<FormState> {
  const formData = Object.fromEntries(data);
  const parsed = RagConfigSchema.safeParse(formData);

  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message);
    return {
      message: "Invalid form data",
      issues,
      fields: formData as Record<string, string>,
    };
  }

  try {
    const input: RagConfigurationInput = {
      currentConfiguration: parsed.data.currentConfiguration,
      performanceMetrics: parsed.data.performanceMetrics,
      costConstraints: parsed.data.costConstraints,
    };
    
    const result = await suggestRagConfiguration(input);
    
    return {
      message: "Suggestions generated successfully!",
      data: result,
    };
  } catch (error) {
    return {
      message: "An error occurred while generating suggestions. Please try again.",
      fields: formData as Record<string, string>,
    };
  }
}
