"use client";

import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { RagPipeline } from '@/lib/types';
import { PlusCircle, Play, Settings, Trash2, Edit3, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { useState } from 'react';

const mockPipelines: RagPipeline[] = [
  { id: '1', name: 'Customer Support Bot (GraphRAG)', type: 'GraphRAG', status: 'active', lastRun: '2023-10-26T10:00:00Z', performance: { latency: 180, recall: 0.92, precision: 0.88 } },
  { id: '2', name: 'Product Q&A (Naive)', type: 'NaiveRAG', status: 'inactive', lastRun: '2023-10-25T14:30:00Z', performance: { latency: 350, recall: 0.75, precision: 0.80 } },
  { id: '3', name: 'Financial Analyst Assistant (GraphRAG)', type: 'GraphRAG', status: 'error', lastRun: '2023-10-26T11:00:00Z', performance: { latency: 220, recall: 0.85, precision: 0.70 } },
  { id: '4', name: 'Internal Knowledge Base (Naive)', type: 'NaiveRAG', status: 'active', lastRun: '2023-10-24T09:15:00Z', performance: { latency: 400, recall: 0.80, precision: 0.82 } },
];

function PipelineStatusBadge({ status }: { status: RagPipeline['status'] }) {
  switch (status) {
    case 'active':
      return <Badge variant="default" className="bg-secondary hover:bg-secondary/90"><CheckCircle2 className="mr-1 h-3 w-3" />Active</Badge>;
    case 'inactive':
      return <Badge variant="outline">Inactive</Badge>;
    case 'error':
      return <Badge variant="destructive"><AlertCircle className="mr-1 h-3 w-3" />Error</Badge>;
    default:
      return <Badge variant="secondary">Unknown</Badge>;
  }
}

export default function PipelinesPage() {
  const [activeTab, setActiveTab] = useState<'all' | 'graphrag' | 'naiverag'>('all');

  const filteredPipelines = mockPipelines.filter(pipeline => {
    if (activeTab === 'all') return true;
    if (activeTab === 'graphrag') return pipeline.type === 'GraphRAG';
    if (activeTab === 'naiverag') return pipeline.type === 'NaiveRAG';
    return true;
  });

  return (
    <AppLayout>
      <div className="flex flex-col gap-5">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-headline">RAG Pipeline Management</h1>
          <Button>
            <PlusCircle className="mr-2 h-4 w-4" /> Create New Pipeline
          </Button>
        </div>

        <Card className="shadow-lg">
          <CardHeader>
            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
              <TabsList className="grid w-full grid-cols-3 md:w-[400px]">
                <TabsTrigger value="all">All Pipelines</TabsTrigger>
                <TabsTrigger value="graphrag">GraphRAG</TabsTrigger>
                <TabsTrigger value="naiverag">Naive RAG</TabsTrigger>
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPipelines.length > 0 ? filteredPipelines.map((pipeline) => (
                  <TableRow key={pipeline.id}>
                    <TableCell className="font-medium">{pipeline.name}</TableCell>
                    <TableCell>
                      <Badge variant={pipeline.type === 'GraphRAG' ? 'default' : 'secondary'}>
                        {pipeline.type}
                      </Badge>
                    </TableCell>
                    <TableCell><PipelineStatusBadge status={pipeline.status} /></TableCell>
                    <TableCell>{new Date(pipeline.lastRun).toLocaleDateString()}</TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button variant="ghost" size="icon" title="Run">
                        <Play className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Edit">
                        <Edit3 className="h-4 w-4" />
                      </Button>
                       <Button variant="ghost" size="icon" title="Settings">
                        <Settings className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" title="Delete">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                )) : (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center h-24">
                      No pipelines found for "{activeTab}" type.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
