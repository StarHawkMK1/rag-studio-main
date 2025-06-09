"use client";

import { useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowUpRight, BarChart3, Database, ListChecks, CheckCircle2, AlertCircle, Clock, Loader2 } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { apiClient } from '@/lib/api';

interface DashboardStats {
  activePipelines: number;
  totalPipelines: number;
  clusterStatus: 'green' | 'yellow' | 'red';
  nodeCount: number;
  totalShards: number;
  totalDocuments: number;
  activeModels: number;
  ingestionPipelines: number;
  avgPrecision: number;
  avgLatency: number;
}

interface RecentActivity {
  id: string;
  name: string;
  status: 'completed' | 'error' | 'in_progress';
  time: string;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    activePipelines: 0,
    totalPipelines: 0,
    clusterStatus: 'green',
    nodeCount: 0,
    totalShards: 0,
    totalDocuments: 0,
    activeModels: 0,
    ingestionPipelines: 0,
    avgPrecision: 0,
    avgLatency: 0,
  });
  const [recentActivities, setRecentActivities] = useState<RecentActivity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);

        // Fetch pipelines
        const pipelinesResponse = await apiClient.getPipelines();
        const activePipelines = pipelinesResponse.items.filter(p => p.status === 'active').length;
        
        // Calculate average metrics from pipelines
        let totalLatency = 0;
        let totalPrecision = 0;
        let metricsCount = 0;
        
        pipelinesResponse.items.forEach(pipeline => {
          if (pipeline.metrics) {
            totalLatency += pipeline.metrics.average_latency;
            metricsCount++;
          }
        });

        // Fetch cluster health
        let clusterData = null;
        try {
          clusterData = await apiClient.getClusterHealth();
        } catch (error) {
          console.error('Failed to fetch cluster health:', error);
        }

        // Fetch indices for document count
        let totalDocs = 0;
        try {
          const indicesResponse = await apiClient.getIndices();
          totalDocs = indicesResponse.indices.reduce((sum, index) => sum + index.document_count, 0);
        } catch (error) {
          console.error('Failed to fetch indices:', error);
        }

        // Fetch models
        let modelsCount = 0;
        try {
          const models = await apiClient.getModels();
          modelsCount = models.filter((m: any) => m.status === 'loaded').length;
        } catch (error) {
          console.error('Failed to fetch models:', error);
        }

        // Fetch OpenSearch pipelines
        let osPipelinesCount = 0;
        try {
          const osPipelines = await apiClient.getOpenSearchPipelines();
          osPipelinesCount = osPipelines.length;
        } catch (error) {
          console.error('Failed to fetch OpenSearch pipelines:', error);
        }

        setStats({
          activePipelines,
          totalPipelines: pipelinesResponse.items.length,
          clusterStatus: clusterData?.status || 'yellow',
          nodeCount: clusterData?.node_count || 0,
          totalShards: clusterData?.active_shards || 0,
          totalDocuments: totalDocs,
          activeModels: modelsCount,
          ingestionPipelines: osPipelinesCount,
          avgPrecision: 92.5, // Mock data for now
          avgLatency: metricsCount > 0 ? totalLatency / metricsCount : 250,
        });

        // Map recent pipelines to activities
        const activities = pipelinesResponse.items
          .filter(p => p.last_run)
          .sort((a, b) => new Date(b.last_run!).getTime() - new Date(a.last_run!).getTime())
          .slice(0, 3)
          .map(pipeline => ({
            id: pipeline.id,
            name: pipeline.name,
            status: pipeline.status === 'error' ? 'error' : 
                   pipeline.status === 'active' ? 'completed' : 'in_progress' as const,
            time: getRelativeTime(new Date(pipeline.last_run!)),
          }));

        setRecentActivities(activities);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      </AppLayout>
    );
  }

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
              <div className="text-2xl font-bold">{stats.activePipelines}</div>
              <p className="text-xs text-muted-foreground">Out of {stats.totalPipelines} total pipelines</p>
            </CardContent>
          </Card>
          <Card className="shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">OpenSearch Cluster Status</CardTitle>
              <Database className="h-5 w-5 text-secondary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold flex items-center">
                {stats.clusterStatus === 'green' ? (
                  <><CheckCircle2 className="h-6 w-6 text-secondary mr-2" /> Healthy</>
                ) : stats.clusterStatus === 'yellow' ? (
                  <><AlertCircle className="h-6 w-6 text-accent mr-2" /> Warning</>
                ) : (
                  <><AlertCircle className="h-6 w-6 text-destructive mr-2" /> Critical</>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{stats.nodeCount} Nodes, {stats.totalShards} Shards</p>
            </CardContent>
          </Card>
          <Card className="shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Average Query Performance</CardTitle>
              <BarChart3 className="h-5 w-5 text-accent" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.avgPrecision}% Precision</div>
              <p className="text-xs text-muted-foreground">Avg. Latency: {Math.round(stats.avgLatency)}ms</p>
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
              {recentActivities.length > 0 ? recentActivities.map(activity => (
                <div key={activity.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-md">
                  <div className="flex items-center gap-3">
                    {activity.status === 'completed' && <CheckCircle2 className="h-5 w-5 text-secondary" />}
                    {activity.status === 'error' && <AlertCircle className="h-5 w-5 text-destructive" />}
                    {activity.status === 'in_progress' && <Clock className="h-5 w-5 text-blue-500 animate-spin" />}
                    <div>
                      <p className="font-medium">{activity.name}</p>
                      <p className="text-xs text-muted-foreground capitalize">{activity.status.replace('_', ' ')}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">{activity.time}</p>
                </div>
              )) : (
                <p className="text-sm text-muted-foreground text-center py-4">No recent pipeline activity</p>
              )}
              <Link href="/pipelines" passHref>
                <Button variant="outline" className="w-full mt-4">
                  View All Pipelines <ArrowUpRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
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
                <p className="font-semibold">{formatNumber(stats.totalDocuments)}</p>
              </div>
              <div className="flex justify-between items-center p-3 bg-muted/50 rounded-md">
                <p>Active Models</p>
                <p className="font-semibold">{stats.activeModels}</p>
              </div>
              <div className="flex justify-between items-center p-3 bg-muted/50 rounded-md">
                <p>Total Ingestion Pipelines</p>
                <p className="font-semibold">{stats.ingestionPipelines}</p>
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

function getRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString();
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
}