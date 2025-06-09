"use client"

import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent } from "@/components/ui/chart"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import Image from 'next/image';

const benchmarkData = [
  { name: 'GraphRAG - Support', latency: 180, recall: 0.92, precision: 0.88, cost: 0.008 },
  { name: 'NaiveRAG - Product', latency: 350, recall: 0.75, precision: 0.80, cost: 0.003 },
  { name: 'GraphRAG - Finance', latency: 220, recall: 0.85, precision: 0.70, cost: 0.012 },
  { name: 'NaiveRAG - KB', latency: 400, recall: 0.80, precision: 0.82, cost: 0.002 },
];

const chartConfig = {
  latency: { label: "Latency (ms)", color: "hsl(var(--chart-1))" },
  recall: { label: "Recall", color: "hsl(var(--chart-2))" },
  precision: { label: "Precision", color: "hsl(var(--chart-3))" },
  cost: { label: "Cost/Query ($)", color: "hsl(var(--chart-4))" },
} satisfies ChartConfig

export default function BenchmarkingPage() {
  return (
    <AppLayout>
      <div className="flex flex-col gap-5">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-headline">Performance Benchmarking</h1>
          <Select defaultValue="last-7-days">
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select Period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="last-24-hours">Last 24 Hours</SelectItem>
              <SelectItem value="last-7-days">Last 7 Days</SelectItem>
              <SelectItem value="last-30-days">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Latency Comparison (ms)</CardTitle>
            <CardDescription>Lower is better. Comparing average query latency.</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[300px] w-full">
              <BarChart data={benchmarkData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tickFormatter={(value) => value.substring(0,10) + '...'}/>
                <YAxis />
                <ChartTooltip content={<ChartTooltipContent />} />
                <ChartLegend content={<ChartLegendContent />} />
                <Bar dataKey="latency" fill="var(--color-latency)" radius={4} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <div className="grid md:grid-cols-2 gap-5">
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Recall vs. Precision</CardTitle>
              <CardDescription>Higher is better for both metrics.</CardDescription>
            </CardHeader>
            <CardContent>
               <ChartContainer config={chartConfig} className="h-[300px] w-full">
                <BarChart data={benchmarkData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tickFormatter={(value) => value.substring(0,10) + '...'} />
                  <YAxis />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  <Bar dataKey="recall" fill="var(--color-recall)" radius={4} />
                  <Bar dataKey="precision" fill="var(--color-precision)" radius={4} />
                </BarChart>
              </ChartContainer>
            </CardContent>
          </Card>
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Cost Per Query ($)</CardTitle>
              <CardDescription>Lower is better. Estimated cost for each query.</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartContainer config={chartConfig} className="h-[300px] w-full">
                <LineChart data={benchmarkData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tickFormatter={(value) => value.substring(0,10) + '...'}/>
                  <YAxis domain={[0, 'auto']}/>
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  <Line type="monotone" dataKey="cost" stroke="var(--color-cost)" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ChartContainer>
            </CardContent>
          </Card>
        </div>
        
        <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Historical Performance Trends</CardTitle>
              <CardDescription>Track precision over time for key pipelines.</CardDescription>
            </CardHeader>
            <CardContent>
                 <Image src="https://placehold.co/1200x400.png" alt="Historical Performance Chart" width={1200} height={400} className="rounded-md" data-ai-hint="line graph" />
            </CardContent>
        </Card>

      </div>
    </AppLayout>
  );
}
