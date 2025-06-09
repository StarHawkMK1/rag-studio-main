"use client";

import { useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { PlusCircle, Play, Settings, Trash2, Edit3, CheckCircle2, AlertCircle, Clock, Loader2 } from 'lucide-react';
import { apiClient, type Pipeline } from '@/lib/api';
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
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function PipelineStatusBadge({ status }: { status: Pipeline['status'] }) {
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
  const [activeTab, setActiveTab] = useState<'all' | 'graph_rag' | 'naive_rag'>('all');
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState<string | null>(null);
  const [newPipeline, setNewPipeline] = useState({
    name: '',
    description: '',
    pipeline_type: 'naive_rag' as 'naive_rag' | 'graph_rag',
    index_name: 'rag-documents',
  });

  const fetchPipelines = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getPipelines();
      setPipelines(response.items);
    } catch (error) {
      console.error('Failed to fetch pipelines:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPipelines();
  }, []);

  const filteredPipelines = pipelines.filter(pipeline => {
    if (activeTab === 'all') return true;
    return pipeline.pipeline_type === activeTab;
  });

  const handleCreatePipeline = async () => {
    try {
      await apiClient.createPipeline({
        ...newPipeline,
        config: {
          retrieval_top_k: 5,
          temperature: 0.7,
          max_tokens: 2000,
          search_filters: {}
        }
      });
      toast({
        title: "Success",
        description: "Pipeline created successfully",
      });
      setCreateDialogOpen(false);
      setNewPipeline({
        name: '',
        description: '',
        pipeline_type: 'naive_rag',
        index_name: 'rag-documents',
      });
      fetchPipelines();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create pipeline",
        variant: "destructive",
      });
    }
  };

  const handleDeletePipeline = async (id: string) => {
    try {
      await apiClient.deletePipeline(id);
      toast({
        title: "Success",
        description: "Pipeline deleted successfully",
      });
      setDeleteDialogOpen(null);
      fetchPipelines();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete pipeline",
        variant: "destructive",
      });
    }
  };

  const handleRunPipeline = async (id: string) => {
    try {
      const result = await apiClient.executePipeline(id, {
        query_text: "Test query for pipeline execution",
        top_k: 5
      });
      toast({
        title: "Pipeline Executed",
        description: `Query processed in ${result.latency_ms}ms`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to execute pipeline",
        variant: "destructive",
      });
    }
  };

  const handleToggleStatus = async (pipeline: Pipeline) => {
    try {
      if (pipeline.status === 'active') {
        await apiClient.deactivatePipeline(pipeline.id);
      } else {
        await apiClient.activatePipeline(pipeline.id);
      }
      fetchPipelines();
      toast({
        title: "Success",
        description: `Pipeline ${pipeline.status === 'active' ? 'deactivated' : 'activated'} successfully`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to toggle pipeline status",
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
          <h1 className="text-2xl font-headline">RAG Pipeline Management</h1>
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <PlusCircle className="mr-2 h-4 w-4" /> Create New Pipeline
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Pipeline</DialogTitle>
                <DialogDescription>
                  Configure your new RAG pipeline.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="name" className="text-right">Name</Label>
                  <Input
                    id="name"
                    className="col-span-3"
                    value={newPipeline.name}
                    onChange={(e) => setNewPipeline({ ...newPipeline, name: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="description" className="text-right">Description</Label>
                  <Textarea
                    id="description"
                    className="col-span-3"
                    value={newPipeline.description}
                    onChange={(e) => setNewPipeline({ ...newPipeline, description: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="type" className="text-right">Type</Label>
                  <Select
                    value={newPipeline.pipeline_type}
                    onValueChange={(value: 'naive_rag' | 'graph_rag') => setNewPipeline({ ...newPipeline, pipeline_type: value })}
                  >
                    <SelectTrigger className="col-span-3">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="naive_rag">Naive RAG</SelectItem>
                      <SelectItem value="graph_rag">Graph RAG</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="index" className="text-right">Index</Label>
                  <Input
                    id="index"
                    className="col-span-3"
                    value={newPipeline.index_name}
                    onChange={(e) => setNewPipeline({ ...newPipeline, index_name: e.target.value })}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleCreatePipeline}>Create Pipeline</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <Card className="shadow-lg">
          <CardHeader>
            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
              <TabsList className="grid w-full grid-cols-3 md:w-[400px]">
                <TabsTrigger value="all">All Pipelines</TabsTrigger>
                <TabsTrigger value="graph_rag">GraphRAG</TabsTrigger>
                <TabsTrigger value="naive_rag">Naive RAG</TabsTrigger>
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
                      <Badge variant={pipeline.pipeline_type === 'graph_rag' ? 'default' : 'secondary'}>
                        {pipeline.pipeline_type === 'graph_rag' ? 'GraphRAG' : 'Naive RAG'}
                      </Badge>
                    </TableCell>
                    <TableCell><PipelineStatusBadge status={pipeline.status} /></TableCell>
                    <TableCell>
                      {pipeline.last_run ? new Date(pipeline.last_run).toLocaleDateString() : 'Never'}
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        title="Run"
                        onClick={() => handleRunPipeline(pipeline.id)}
                      >
                        <Play className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        title={pipeline.status === 'active' ? 'Deactivate' : 'Activate'}
                        onClick={() => handleToggleStatus(pipeline)}
                      >
                        {pipeline.status === 'active' ? (
                          <Clock className="h-4 w-4" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4" />
                        )}
                      </Button>
                      <Dialog open={deleteDialogOpen === pipeline.id} onOpenChange={(open) => setDeleteDialogOpen(open ? pipeline.id : null)}>
                        <DialogTrigger asChild>
                          <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" title="Delete">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Confirm Deletion</DialogTitle>
                            <DialogDescription>
                              Are you sure you want to delete "{pipeline.name}"? This action cannot be undone.
                            </DialogDescription>
                          </DialogHeader>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setDeleteDialogOpen(null)}>Cancel</Button>
                            <Button variant="destructive" onClick={() => handleDeletePipeline(pipeline.id)}>Delete</Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
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