import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Play, Save, Share2, PlusCircle } from 'lucide-react';

// Placeholder components for the RAG builder
function ComponentPalette() {
  const components = [
    { name: 'Data Loader', icon: '📄' },
    { name: 'Text Splitter', icon: '✂️' },
    { name: 'Embedding Model', icon: '🧠' },
    { name: 'Vector Store', icon: '📦' },
    { name: 'Retriever', icon: '🔍' },
    { name: 'LLM Chain', icon: '🔗' },
    { name: 'Output Parser', icon: '💡' },
  ];

  return (
    <Card className="shadow-lg h-full">
      <CardHeader>
        <CardTitle>Components</CardTitle>
        <CardDescription>Drag components to the canvas.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3">
        {components.map(comp => (
          <Button variant="outline" key={comp.name} className="h-20 flex flex-col items-center justify-center text-center p-2 cursor-grab">
            <span className="text-2xl mb-1">{comp.icon}</span>
            <span className="text-xs">{comp.name}</span>
          </Button>
        ))}
      </CardContent>
    </Card>
  );
}

function RAGCanvas() {
  return (
    <Card className="shadow-lg h-full flex-grow">
      <CardHeader className="flex flex-row justify-between items-center">
        <div>
          <CardTitle>My GraphRAG Pipeline</CardTitle>
          <CardDescription>Visually construct your RAG pipeline.</CardDescription>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm"><PlusCircle className="mr-2 h-4 w-4"/> Add Node</Button>
          <Button variant="secondary" size="sm"><Play className="mr-2 h-4 w-4"/> Run</Button>
          <Button size="sm"><Save className="mr-2 h-4 w-4"/> Save</Button>
        </div>
      </CardHeader>
      <CardContent className="h-[500px] bg-muted/30 rounded-md border-2 border-dashed border-muted-foreground/30 flex items-center justify-center">
        <p className="text-muted-foreground">Drag and drop components here to build your pipeline.</p>
        {/* Placeholder for actual drag-and-drop canvas elements */}
      </CardContent>
    </Card>
  );
}


export default function RAGBuilderPage() {
  return (
    <AppLayout>
      <div className="flex flex-col gap-5 h-full">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-headline">Visual RAG Builder (LangGraph)</h1>
          <Button variant="outline">
            <Share2 className="mr-2 h-4 w-4" /> Share
          </Button>
        </div>
        <p className="text-muted-foreground">
          Note: The drag-and-drop functionality is a complex feature. This UI provides a static representation.
          A full implementation would require a dedicated library (e.g., React Flow).
        </p>
        <div className="flex flex-col md:flex-row gap-5 flex-grow min-h-[600px]">
          <div className="w-full md:w-1/4 lg:w-1/5">
            <ComponentPalette />
          </div>
          <div className="w-full md:w-3/4 lg:w-4/5">
            <RAGCanvas />
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
