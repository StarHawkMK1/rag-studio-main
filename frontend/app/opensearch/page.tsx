"use client";

import { useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { CheckCircle2, AlertTriangle, DatabaseZap, Settings2, Puzzle, ListTree, PlusCircle, Loader2, Trash2, RefreshCw } from 'lucide-react';
import { apiClient, type OpenSearchCluster, type IndexInfo } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
  const [clusterHealth, setClusterHealth] = useState<OpenSearchCluster | null>(null);
  const [indices, setIndices] = useState<IndexInfo[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [osPipelines, setOsPipelines] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [createIndexDialogOpen, setCreateIndexDialogOpen] = useState(false);
  const [deleteIndexDialogOpen, setDeleteIndexDialogOpen] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [newIndex, setNewIndex] = useState({
    name: '',
    number_of_shards: 2,
    number_of_replicas: 1,
    embedding_dimension: 384,
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch cluster health
      try {
        const health = await apiClient.getClusterHealth();
        setClusterHealth(health);
      } catch (error) {
        console.error('Failed to fetch cluster health:', error);
      }

      // Fetch indices
      try {
        const indicesResponse = await apiClient.getIndices();
        setIndices(indicesResponse.indices);
      } catch (error) {
        console.error('Failed to fetch indices:', error);
      }

      // Fetch models
      try {
        const modelsData = await apiClient.getModels();
        setModels(modelsData);
      } catch (error) {
        console.error('Failed to fetch models:', error);
      }

      // Fetch OpenSearch pipelines
      try {
        const pipelinesData = await apiClient.getOpenSearchPipelines();
        setOsPipelines(pipelinesData);
      } catch (error) {
        console.error('Failed to fetch OpenSearch pipelines:', error);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
    toast({
      title: "Data refreshed",
      description: "OpenSearch data has been updated",
    });
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateIndex = async () => {
    try {
      await apiClient.createIndex(newIndex.name, {
        number_of_shards: newIndex.number_of_shards,
        number_of_replicas: newIndex.number_of_replicas,
        embedding_dimension: newIndex.embedding_dimension,
      });
      toast({
        title: "Success",
        description: "Index created successfully",
      });
      setCreateIndexDialogOpen(false);
      setNewIndex({
        name: '',
        number_of_shards: 2,
        number_of_replicas: 1,
        embedding_dimension: 384,
      });
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create index",
        variant: "destructive",
      });
    }
  };

  const handleDeleteIndex = async (name: string) => {
    try {
      await apiClient.deleteIndex(name);
      toast({
        title: "Success",
        description: "Index deleted successfully",
      });
      setDeleteIndexDialogOpen(null);
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete index",
        variant: "destructive",
      });
    }
  };

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
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-headline">OpenSearch Integration Management</h1>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
            </Button>
            <Dialog open={createIndexDialogOpen} onOpenChange={setCreateIndexDialogOpen}>
              <DialogTrigger asChild>
                <Button><PlusCircle className="mr-2 h-4 w-4" /> Create Index</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Index</DialogTitle>
                  <DialogDescription>
                    Configure your new OpenSearch index.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="index-name" className="text-right">Name</Label>
                    <Input
                      id="index-name"
                      className="col-span-3"
                      value={newIndex.name}
                      onChange={(e) => setNewIndex({ ...newIndex, name: e.target.value })}
                      placeholder="my-index-name"
                    />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="shards" className="text-right">Shards</Label>
                    <Input
                      id="shards"
                      type="number"
                      className="col-span-3"
                      value={newIndex.number_of_shards}
                      onChange={(e) => setNewIndex({ ...newIndex, number_of_shards: parseInt(e.target.value) })}
                    />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="replicas" className="text-right">Replicas</Label>
                    <Input
                      id="replicas"
                      type="number"
                      className="col-span-3"
                      value={newIndex.number_of_replicas}
                      onChange={(e) => setNewIndex({ ...newIndex, number_of_replicas: parseInt(e.target.value) })}
                    />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="embedding-dim" className="text-right">Embedding Dimension</Label>
                    <Input
                      id="embedding-dim"
                      type="number"
                      className="col-span-3"
                      value={newIndex.embedding_dimension}
                      onChange={(e) => setNewIndex({ ...newIndex, embedding_dimension: parseInt(e.target.value) })}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateIndexDialogOpen(false)}>Cancel</Button>
                  <Button onClick={handleCreateIndex}>Create Index</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
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
                <CardTitle>OpenSearch Cluster Health</CardTitle>
                <CardDescription>Monitor your OpenSearch cluster status.</CardDescription>
              </CardHeader>
              <CardContent>
                {clusterHealth ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="p-4 bg-muted rounded-lg">
                        <p className="text-sm text-muted-foreground">Cluster Name</p>
                        <p className="font-semibold">{clusterHealth.cluster_name}</p>
                      </div>
                      <div className="p-4 bg-muted rounded-lg">
                        <p className="text-sm text-muted-foreground">Status</p>
                        <StatusBadge status={clusterHealth.status} />
                      </div>
                      <div className="p-4 bg-muted rounded-lg">
                        <p className="text-sm text-muted-foreground">Nodes</p>
                        <p className="font-semibold">{clusterHealth.node_count}</p>
                      </div>
                      <div className="p-4 bg-muted rounded-lg">
                        <p className="text-sm text-muted-foreground">Active Shards</p>
                        <p className="font-semibold">{clusterHealth.active_shards}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div className="p-4 bg-muted rounded-lg">
                        <p className="text-sm text-muted-foreground">Unassigned Shards</p>
                        <p className="font-semibold">{clusterHealth.unassigned_shards}</p>
                      </div>
                      <div className="p-4 bg-muted rounded-lg">
                        <p className="text-sm text-muted-foreground">Relocating Shards</p>
                        <p className="font-semibold">{clusterHealth.relocating_shards}</p>
                      </div>
                      <div className="p-4 bg-muted rounded-lg">
                        <p className="text-sm text-muted-foreground">Shard Health</p>
                        <p className="font-semibold">{clusterHealth.active_shards_percent.toFixed(1)}%</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-muted-foreground">Unable to fetch cluster health</p>
                )}
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
                      <TableHead>Shards</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {indices.map((index) => (
                      <TableRow key={index.name}>
                        <TableCell className="font-medium">{index.name}</TableCell>
                        <TableCell>{index.document_count.toLocaleString()}</TableCell>
                        <TableCell>{index.size_human}</TableCell>
                        <TableCell>{index.number_of_shards}</TableCell>
                        <TableCell><StatusBadge status={index.status as any} /></TableCell>
                        <TableCell className="text-right">
                          <Dialog open={deleteIndexDialogOpen === index.name} onOpenChange={(open) => setDeleteIndexDialogOpen(open ? index.name : null)}>
                            <DialogTrigger asChild>
                              <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" title="Delete">
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Confirm Deletion</DialogTitle>
                                <DialogDescription>
                                  Are you sure you want to delete index "{index.name}"? This action cannot be undone and all data will be lost.
                                </DialogDescription>
                              </DialogHeader>
                              <DialogFooter>
                                <Button variant="outline" onClick={() => setDeleteIndexDialogOpen(null)}>Cancel</Button>
                                <Button variant="destructive" onClick={() => handleDeleteIndex(index.name)}>Delete</Button>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        </TableCell>
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
                {models.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Version</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {models.map((model) => (
                        <TableRow key={model.id}>
                          <TableCell className="font-medium">{model.name}</TableCell>
                          <TableCell>{model.type}</TableCell>
                          <TableCell>{model.version}</TableCell>
                          <TableCell><StatusBadge status={model.status} /></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-muted-foreground text-center py-8">No ML models found. Make sure ML plugin is installed.</p>
                )}
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
                {osPipelines.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Processors</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {osPipelines.map((pipeline) => (
                        <TableRow key={pipeline.id}>
                          <TableCell className="font-medium">{pipeline.name}</TableCell>
                          <TableCell>{pipeline.description}</TableCell>
                          <TableCell>{pipeline.processor_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-muted-foreground text-center py-8">No ingestion pipelines found.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}