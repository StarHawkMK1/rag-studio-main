import type { ReactNode } from 'react';
import { SidebarProvider, Sidebar, SidebarTrigger, SidebarInset, SidebarHeader, SidebarContent, SidebarFooter } from '@/components/ui/sidebar';
import SidebarNav from '@/components/layout/sidebar-nav';
import { Button } from '@/components/ui/button';
import { LogOut, Settings, UserCircle2 } from 'lucide-react';
import Link from 'next/link';

interface AppLayoutProps {
  children: ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  return (
    <SidebarProvider defaultOpen>
      <Sidebar>
        <SidebarHeader className="p-5 border-b">
          <Link href="/" className="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 text-primary">
              <path d="M12.378 1.602a.75.75 0 00-.756 0L3.366 6.026A.75.75 0 003 6.732V11.25a.75.75 0 00.75.75h8.25a.75.75 0 00.75-.75V6.732a.75.75 0 00-.366-.706L12.378 1.602zM12 7.518L15.922 5.25l3.922-2.25L12 7.518zM12 7.518L8.078 5.25 4.156 3 12 7.518zM11.25 12.75H3.75v5.518c0 .43.338.79.768.822A48.02 48.02 0 0012 19.5a48.02 48.02 0 007.482-.41c.43-.032.768-.392.768-.822V12.75H12.75v-1.5h8.25a.75.75 0 00.75-.75V6.732a.75.75 0 00-.366-.706l-3.54-2.042a.75.75 0 00-.9/.3l-2.68 4.643a.75.75 0 00.012.807l.12.207V11.25a.75.75 0 01-.75.75h-1.5V12.75z" />
            </svg>
            <h1 className="text-2xl font-headline font-semibold">RAGPilot</h1>
          </Link>
        </SidebarHeader>
        <SidebarContent>
          <SidebarNav />
        </SidebarContent>
        <SidebarFooter className="p-5 border-t gap-2">
          <Button variant="ghost" className="w-full justify-start">
            <UserCircle2 className="mr-2 h-5 w-5" /> Profile
          </Button>
          <Button variant="ghost" className="w-full justify-start">
            <Settings className="mr-2 h-5 w-5" /> Settings
          </Button>
          <Button variant="ghost" className="w-full justify-start">
            <LogOut className="mr-2 h-5 w-5" /> Logout
          </Button>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="flex flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b bg-background/80 backdrop-blur-sm px-5 md:justify-end">
            <div className="md:hidden">
                <SidebarTrigger />
            </div>
            <div className="flex items-center gap-3">
                <Button variant="outline" size="icon">
                    <Settings className="h-5 w-5" />
                </Button>
                <UserCircle2 className="h-8 w-8 text-muted-foreground" />
            </div>
        </header>
        <main className="flex-1 overflow-auto p-5">
            {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
