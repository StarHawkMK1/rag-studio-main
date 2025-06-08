'use server';

/**
 * @fileOverview This file defines a Genkit flow for providing AI-powered RAG configuration suggestions.
 *
 * The flow analyzes a user's current RAG configuration and suggests improvements.
 * - suggestRagConfiguration - The function to trigger the RAG configuration suggestions.
 * - RagConfigurationInput - The input type for the suggestRagConfiguration function.
 * - RagConfigurationOutput - The output type for the suggestRagConfiguration function.
 */

import {ai} from '@/ai/genkit';
import {z} from 'genkit';

const RagConfigurationInputSchema = z.object({
  currentConfiguration: z
    .string()
    .describe('The current RAG configuration in detail, including data sources, embedding models, chunking strategies, and retrieval methods.'),
  performanceMetrics: z
    .string()
    .optional()
    .describe('Optional: Performance metrics of the current RAG configuration, such as latency, recall, and precision.'),
  costConstraints: z
    .string()
    .optional()
    .describe('Optional: Cost constraints for the RAG configuration, such as maximum spend per query or per month.'),
});
export type RagConfigurationInput = z.infer<typeof RagConfigurationInputSchema>;

const RagConfigurationOutputSchema = z.object({
  suggestedImprovements: z.string().describe('A detailed list of suggested improvements to the RAG configuration, including specific changes to data sources, embedding models, chunking strategies, retrieval methods, and any other relevant parameters.'),
  rationale: z.string().describe('The rationale behind each suggested improvement, explaining how it is expected to improve performance, relevance, and/or cost-efficiency.'),
  estimatedImpact: z
    .string()
    .optional()
    .describe('Optional: Estimated impact of each suggested improvement on performance metrics and cost, if available.'),
});
export type RagConfigurationOutput = z.infer<typeof RagConfigurationOutputSchema>;

export async function suggestRagConfiguration(input: RagConfigurationInput): Promise<RagConfigurationOutput> {
  return suggestRagConfigurationFlow(input);
}

const prompt = ai.definePrompt({
  name: 'ragConfigurationSuggestionPrompt',
  input: {schema: RagConfigurationInputSchema},
  output: {schema: RagConfigurationOutputSchema},
  prompt: `You are an AI expert in Retrieval Augmented Generation (RAG) systems.

You are tasked with analyzing a user's current RAG configuration and suggesting improvements to optimize performance, relevance, and cost-efficiency.

Consider the following information about the current configuration, performance metrics, and cost constraints:

Current Configuration: {{{currentConfiguration}}}
Performance Metrics (Optional): {{{performanceMetrics}}}
Cost Constraints (Optional): {{{costConstraints}}}

Based on your expertise, provide a detailed list of suggested improvements, the rationale behind each improvement, and the estimated impact on performance metrics and cost (if available).

Output should be formatted as follows:

Suggested Improvements: [List of improvements]
Rationale: [Explanation of why each improvement is suggested]
Estimated Impact: [Estimated impact on performance and cost, if available]`,
});

const suggestRagConfigurationFlow = ai.defineFlow(
  {
    name: 'suggestRagConfigurationFlow',
    inputSchema: RagConfigurationInputSchema,
    outputSchema: RagConfigurationOutputSchema,
  },
  async input => {
    const {output} = await prompt(input);
    return output!;
  }
);
