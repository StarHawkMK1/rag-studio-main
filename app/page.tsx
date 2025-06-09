import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowUpRight, BarChart3, Database, ListChecks, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';

export default function DashboardPage() {
  return (
    <AppLayout>
      <div className="flex flex-col gap-5">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          <Card className="shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active RAG Pipelines</CardTitle>
              <ListChecks className="h-5 w-5 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">12</div>
              <p className="text-xs text-muted-foreground">+5 since last week</p>
            </CardContent>
          </Card>
          <Card className="shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">OpenSearch Cluster Status</CardTitle>
              <Database className="h-5 w-5 text-secondary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold flex items-center">
                <CheckCircle2 className="h-6 w-6 text-secondary mr-2" /> Healthy
              </div>
              <p className="text-xs text-muted-foreground">3 Nodes, 125 Shards</p>
            </CardContent>
          </Card>
          <Card className="shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Average Query Performance</CardTitle>
              <BarChart3 className="h-5 w-5 text-accent" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">92.5% Precision</div>
              <p className="text-xs text-muted-foreground">Avg. Latency: 250ms</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Card className="shadow-lg md:col-span-1">
            <CardHeader>
              <CardTitle>Recent Pipeline Activity</CardTitle>
              <CardDescription>Overview of the latest pipeline runs and statuses.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { name: 'GraphRAG Customer Support Bot', status: 'Completed', time: '2m ago', icon: <CheckCircle2 className="h-5 w-5 text-secondary" /> },
                { name: 'Naive Product Q&A', status: 'Error', time: '15m ago', icon: <AlertCircle className="h-5 w-5 text-destructive" /> },
                { name: 'GraphRAG Financial Analyst', status: 'In Progress', time: '30s ago', icon: <Clock className="h-5 w-5 text-blue-500 animate-spin" /> },
              ].map(activity => (
                <div key={activity.name} className="flex items-center justify-between p-3 bg-muted/50 rounded-md">
                  <div className="flex items-center gap-3">
                    {activity.icon}
                    <div>
                      <p className="font-medium">{activity.name}</p>
                      <p className="text-xs text-muted-foreground">{activity.status}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">{activity.time}</p>
                </div>
              ))}
               <Button variant="outline" className="w-full mt-4">
                View All Pipelines <ArrowUpRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>

          <Card className="shadow-lg md:col-span-1">
            <CardHeader>
              <CardTitle>OpenSearch Quick Stats</CardTitle>
              <CardDescription>Key metrics from your OpenSearch integration.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between items-center p-3 bg-muted/50 rounded-md">
                <p>Total Documents Indexed</p>
                <p className="font-semibold">1.2M</p>
              </div>
              <div className="flex justify-between items-center p-3 bg-muted/50 rounded-md">
                <p>Active Models</p>
                <p className="font-semibold">5</p>
              </div>
              <div className="flex justify-between items-center p-3 bg-muted/50 rounded-md">
                <p>Total Ingestion Pipelines</p>
                <p className="font-semibold">8</p>
              </div>
               <Link href="/opensearch" passHref>
                <Button variant="outline" className="w-full mt-4">
                  Manage OpenSearch <ArrowUpRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
        
        <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Performance Overview</CardTitle>
              <CardDescription>Comparative performance of RAG methodologies.</CardDescription>
            </CardHeader>
            <CardContent>
              <Image src="https://placehold.co/1200x400.png" alt="Performance Chart" width={1200} height={400} className="rounded-md" data-ai-hint="data analytics" />
              <Link href="/benchmarking" passHref>
                <Button variant="secondary" className="mt-5">
                  Go to Benchmarking <ArrowUpRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
      </div>
    </AppLayout>
  );
}
