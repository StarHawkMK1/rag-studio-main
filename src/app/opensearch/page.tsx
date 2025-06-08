"use client";

import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { OpenSearchCluster, OpenSearchIndex, OpenSearchModel, OpenSearchPipeline } from '@/lib/types';
import { CheckCircle2, AlertTriangle, DatabaseZap, Settings2, Puzzle, ListTree, PlusCircle } from 'lucide-react';

const mockClusters: OpenSearchCluster[] = [
  { id: 'cluster-1', name: 'Primary Production Cluster', status: 'green', nodeCount: 5, totalShards: 250 },
  { id: 'cluster-2', name: 'Development Cluster', status: 'yellow', nodeCount: 2, totalShards: 80 },
];

const mockIndexes: OpenSearchIndex[] = [
  { id: 'index-1', name: 'product_embeddings_v3', documentCount: 1250000, size: '2.5GB', status: 'open' },
  { id: 'index-2', name: 'customer_support_logs', documentCount: 5500000, size: '10.1GB', status: 'open' },
  { id: 'index-3', name: 'archive_data_2022', documentCount: 800000, size: '1.2GB', status: 'closed' },
];

const mockModels: OpenSearchModel[] = [
  { id: 'model-1', name: 'all-MiniLM-L6-v2', type: 'text_embedding', status: 'loaded' },
  { id: 'model-2', name: 'cohere.embed-english-v3.0', type: 'text_embedding', status: 'loaded' },
  { id: 'model-3', name: 'sparse-model-custom', type: 'sparse_retrieval', status: 'unloaded' },
];

const mockOsPipelines: OpenSearchPipeline[] = [
    { id: 'osp-1', name: 'document_ingestion_pipeline', description: 'Standard pipeline for text chunking and embedding', processorCount: 5 },
    { id: 'osp-2', name: 'hybrid_search_pipeline', description: 'Combines dense and sparse retrieval', processorCount: 3 },
];

function StatusBadge({ status }: { status: 'green' | 'yellow' | 'red' | 'open' | 'closed' | 'loaded' | 'unloaded' }) {
  if (status === 'green' || status === 'open' || status === 'loaded') {
    return <Badge variant="default" className="bg-secondary hover:bg-secondary/90"><CheckCircle2 className="mr-1 h-3 w-3" />{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>;
  }
  if (status === 'yellow') {
    return <Badge variant="outline" className="border-accent text-accent hover:bg-accent/10"><AlertTriangle className="mr-1 h-3 w-3" />{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>;
  }
  if (status === 'red' || status === 'closed' || status === 'unloaded') {
    return <Badge variant="destructive"><AlertTriangle className="mr-1 h-3 w-3" />{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>;
  }
  return <Badge variant="secondary">{status}</Badge>;
}


export default function OpenSearchPage() {
  return (
    <AppLayout>
      <div className="flex flex-col gap-5">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-headline">OpenSearch Integration Management</h1>
           <Button><PlusCircle className="mr-2 h-4 w-4" /> Add Resource</Button>
        </div>

        <Tabs defaultValue="clusters" className="w-full">
          <TabsList className="grid w-full grid-cols-2 md:grid-cols-4 mb-5">
            <TabsTrigger value="clusters"><DatabaseZap className="mr-2 h-4 w-4"/>Clusters</TabsTrigger>
            <TabsTrigger value="indexes"><ListTree className="mr-2 h-4 w-4"/>Indexes</TabsTrigger>
            <TabsTrigger value="models"><Puzzle className="mr-2 h-4 w-4"/>Models</TabsTrigger>
            <TabsTrigger value="pipelines"><Settings2 className="mr-2 h-4 w-4"/>Pipelines</TabsTrigger>
          </TabsList>

          <TabsContent value="clusters">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>OpenSearch Clusters</CardTitle>
                <CardDescription>Manage and monitor your OpenSearch clusters.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Nodes</TableHead>
                      <TableHead>Total Shards</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockClusters.map((cluster) => (
                      <TableRow key={cluster.id}>
                        <TableCell className="font-medium">{cluster.name}</TableCell>
                        <TableCell><StatusBadge status={cluster.status} /></TableCell>
                        <TableCell>{cluster.nodeCount}</TableCell>
                        <TableCell>{cluster.totalShards}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="indexes">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Indexes</CardTitle>
                <CardDescription>Oversee document indexes and their statuses.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Docs</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockIndexes.map((index) => (
                      <TableRow key={index.id}>
                        <TableCell className="font-medium">{index.name}</TableCell>
                        <TableCell>{index.documentCount.toLocaleString()}</TableCell>
                        <TableCell>{index.size}</TableCell>
                        <TableCell><StatusBadge status={index.status} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="models">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Embedding Models</CardTitle>
                <CardDescription>Manage deployed embedding and sparse models.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockModels.map((model) => (
                      <TableRow key={model.id}>
                        <TableCell className="font-medium">{model.name}</TableCell>
                        <TableCell>{model.type}</TableCell>
                        <TableCell><StatusBadge status={model.status} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="pipelines">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Ingestion Pipelines</CardTitle>
                <CardDescription>Manage OpenSearch ingestion pipelines.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Processors</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockOsPipelines.map((pipeline) => (
                      <TableRow key={pipeline.id}>
                        <TableCell className="font-medium">{pipeline.name}</TableCell>
                        <TableCell>{pipeline.description}</TableCell>
                        <TableCell>{pipeline.processorCount}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
