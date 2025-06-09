"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SidebarMenu, SidebarMenuItem, SidebarMenuButton } from '@/components/ui/sidebar';
import { LayoutDashboard, Blocks, BrainCircuit, Network, BarChartBig, SearchCheck } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/pipelines', label: 'Pipelines', icon: Network },
  { href: '/rag-builder', label: 'RAG Builder', icon: Blocks },
  { href: '/opensearch', label: 'OpenSearch', icon: SearchCheck },
  { href: '/benchmarking', label: 'Benchmarking', icon: BarChartBig },
  { href: '/ai-configurator', label: 'AI Configurator', icon: BrainCircuit },
];

export default function SidebarNav() {
  const pathname = usePathname();

  return (
    <SidebarMenu className="p-5">
      {navItems.map((item) => (
        <SidebarMenuItem key={item.href}>
          <Link href={item.href} passHref legacyBehavior>
            <SidebarMenuButton
              className={cn(
                pathname === item.href ? 'bg-sidebar-accent text-sidebar-accent-foreground' : 'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                'w-full justify-start'
              )}
              isActive={pathname === item.href}
              tooltip={item.label}
            >
              <item.icon className="h-5 w-5 mr-3" />
              <span className="font-medium">{item.label}</span>
            </SidebarMenuButton>
          </Link>
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  );
}
