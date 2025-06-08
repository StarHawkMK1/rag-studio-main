// Placeholder for common types used across the application

export interface RagPipeline {
  id: string;
  name: string;
  type: 'GraphRAG' | 'NaiveRAG';
  status: 'active' | 'inactive' | 'error';
  lastRun: string; // ISO date string
  performance?: {
    latency: number; // ms
    recall: number; // 0-1
    precision: number; // 0-1
  };
}

export interface OpenSearchCluster {
  id: string;
  name: string;
  status: 'green' | 'yellow' | 'red';
  nodeCount: number;
  totalShards: number;
}

export interface OpenSearchIndex {
  id: string;
  name: string;
  documentCount: number;
  size: string; // e.g., "1.2GB"
  status: 'open' | 'closed';
}

export interface OpenSearchModel {
  id: string;
  name: string;
  type: string; // e.g., "text_embedding"
  status: 'loaded' | 'unloaded';
}

export interface OpenSearchPipeline {
    id: string;
    name: string;
    description: string;
    processorCount: number;
}
