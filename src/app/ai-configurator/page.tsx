import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import AIConfigForm from '@/components/ai-configurator/ai-config-form';

export default function AIConfiguratorPage() {
  return (
    <AppLayout>
      <div className="flex flex-col gap-5">
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle className="text-2xl font-headline">AI-Powered RAG Configuration Tool</CardTitle>
            <CardDescription>
              Describe your current RAG setup, performance metrics, and cost constraints. 
              Our AI will suggest improvements to optimize your system.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AIConfigForm />
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
