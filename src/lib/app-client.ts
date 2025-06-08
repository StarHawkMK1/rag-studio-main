/**
 * API 클라이언트 모듈
 * 
 * 백엔드 API와 통신하기 위한 클라이언트 함수들을 제공합니다.
 */

import { RagPipeline, OpenSearchCluster, OpenSearchIndex, OpenSearchModel, OpenSearchPipeline } from '@/lib/types';

// API 기본 URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// 기본 헤더
const defaultHeaders = {
  'Content-Type': 'application/json',
};

/**
 * API 요청 헬퍼 함수
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('access_token');
  
  const headers = {
    ...defaultHeaders,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

/**
 * 인증 API
 */
export const authApi = {
  // 로그인
  async login(username: string, password: string) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Login failed');
    }

    const data = await response.json();
    localStorage.setItem('access_token', data.access_token);
    return data;
  },

  // 로그아웃
  async logout() {
    try {
      await apiRequest('/auth/logout', { method: 'POST' });
    } finally {
      localStorage.removeItem('access_token');
    }
  },

  // 현재 사용자 정보
  async getCurrentUser() {
    return apiRequest('/auth/me');
  },

  // 회원가입
  async register(userData: {
    email: string;
    username: string;
    password: string;
    full_name?: string;
  }) {
    return apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  },
};

/**
 * 파이프라인 API
 */
export const pipelineApi = {
  // 파이프라인 목록
  async list(params?: {
    skip?: number;
    limit?: number;
    pipeline_type?: string;
    status?: string;
  }) {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          queryParams.append(key, String(value));
        }
      });
    }

    return apiRequest<{
      items: RagPipeline[];
      total: number;
      skip: number;
      limit: number;
    }>(`/pipelines?${queryParams}`);
  },

  // 파이프라인 생성
  async create(data: RagPipeline) {
    return apiRequest<RagPipeline>('/pipelines', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 파이프라인 조회
  async get(pipelineId: string) {
    return apiRequest<RagPipeline>(`/pipelines/${pipelineId}`);
  },

  // 파이프라인 수정
  async update(pipelineId: string, data: Partial<RagPipeline>) {
    return apiRequest<RagPipeline>(`/pipelines/${pipelineId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  // 파이프라인 삭제
  async delete(pipelineId: string) {
    return apiRequest(`/pipelines/${pipelineId}`, {
      method: 'DELETE',
    });
  },

  // 파이프라인 실행
  async execute(pipelineId: string, query: RagPipeline) {
    return apiRequest<RagPipeline>(`/pipelines/${pipelineId}/execute`, {
      method: 'POST',
      body: JSON.stringify(query),
    });
  },

  // 파이프라인 활성화
  async activate(pipelineId: string) {
    return apiRequest<RagPipeline>(`/pipelines/${pipelineId}/activate`, {
      method: 'POST',
    });
  },

  // 파이프라인 비활성화
  async deactivate(pipelineId: string) {
    return apiRequest<RagPipeline>(`/pipelines/${pipelineId}/deactivate`, {
      method: 'POST',
    });
  },

  // 파이프라인 메트릭
  async getMetrics(pipelineId: string) {
    return apiRequest(`/pipelines/${pipelineId}/metrics`);
  },
};

/**
 * OpenSearch API
 */
export const opensearchApi = {
  // 클러스터 상태
  async getHealth() {
    return apiRequest('/opensearch/health');
  },

  // 인덱스 목록
  async listIndices(pattern: string = '*', includeSystem: boolean = false) {
    return apiRequest(`/opensearch/indices?pattern=${pattern}&include_system=${includeSystem}`);
  },

  // 인덱스 생성
  async createIndex(indexName: string, config: any) {
    return apiRequest('/opensearch/indices', {
      method: 'POST',
      body: JSON.stringify({ index_name: indexName, ...config }),
    });
  },

  // 인덱스 삭제
  async deleteIndex(indexName: string) {
    return apiRequest(`/opensearch/indices/${indexName}`, {
      method: 'DELETE',
    });
  },

  // 문서 색인
  async indexDocuments(indexName: string, documents: any[]) {
    return apiRequest(`/opensearch/indices/${indexName}/documents`, {
      method: 'POST',
      body: JSON.stringify(documents),
    });
  },

  // 문서 검색
  async search(query: {
    index_name: string;
    query_text: string;
    top_k?: number;
    filters?: any;
  }) {
    return apiRequest('/opensearch/search', {
      method: 'POST',
      body: JSON.stringify(query),
    });
  },

  // 모델 목록
  async listModels() {
    return apiRequest('/opensearch/models');
  },

  // 파이프라인 목록
  async listPipelines() {
    return apiRequest('/opensearch/pipelines');
  },
};

/**
 * 벤치마크 API
 */
export const benchmarkApi = {
  // 벤치마크 목록
  async list(params?: {
    skip?: number;
    limit?: number;
    status?: string;
  }) {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          queryParams.append(key, String(value));
        }
      });
    }

    return apiRequest(`/benchmarks?${queryParams}`);
  },

  // 벤치마크 생성
  async create(data: any) {
    return apiRequest('/benchmarks', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 벤치마크 결과 조회
  async getResult(benchmarkId: string) {
    return apiRequest(`/benchmarks/${benchmarkId}`);
  },

  // 벤치마크 결과 내보내기
  async export(benchmarkId: string, format: 'json' | 'csv' | 'html' = 'json') {
    const response = await fetch(
      `${API_BASE_URL}/benchmarks/${benchmarkId}/export?format=${format}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error('Export failed');
    }

    return response.blob();
  },

  // 테스트 케이스 생성
  async generateTestCases(numCases: number, queryTypes?: string[]) {
    const params = new URLSearchParams({ num_cases: String(numCases) });
    if (queryTypes) {
      queryTypes.forEach(type => params.append('query_types', type));
    }

    return apiRequest(`/benchmarks/test-cases/generate?${params}`);
  },

  // 벤치마크 비교
  async compare(benchmarkId1: string, benchmarkId2: string) {
    return apiRequest(`/benchmarks/compare/${benchmarkId1}/${benchmarkId2}`);
  },

  // 벤치마크 삭제
  async delete(benchmarkId: string) {
    return apiRequest(`/benchmarks/${benchmarkId}`, {
      method: 'DELETE',
    });
  },
};

/**
 * RAG Builder API
 */
export const ragBuilderApi = {
  // 컴포넌트 목록
  async getComponents() {
    return apiRequest('/rag-builder/components');
  },

  // 컴포넌트 상세
  async getComponentDetails(componentId: string) {
    return apiRequest(`/rag-builder/components/${componentId}`);
  },

  // 그래프 검증
  async validateGraph(graph: any) {
    return apiRequest('/rag-builder/validate', {
      method: 'POST',
      body: JSON.stringify(graph),
    });
  },

  // 그래프 컴파일
  async compileGraph(graph: any, pipelineName: string) {
    return apiRequest('/rag-builder/compile', {
      method: 'POST',
      body: JSON.stringify({ ...graph, pipeline_name: pipelineName }),
    });
  },

  // 템플릿 목록
  async getTemplates() {
    return apiRequest('/rag-builder/templates');
  },

  // 템플릿 복제
  async cloneTemplate(templateId: string) {
    return apiRequest(`/rag-builder/templates/${templateId}/clone`, {
      method: 'POST',
    });
  },
};

/**
 * WebSocket 연결 관리
 */
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  constructor(
    private endpoint: string,
    private handlers: {
      onMessage?: (data: any) => void;
      onError?: (error: Event) => void;
      onClose?: () => void;
      onOpen?: () => void;
    }
  ) {}

  connect() {
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.error('No authentication token found');
      return;
    }

    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}${this.endpoint}?token=${token}`;
    
    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.handlers.onOpen?.();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handlers.onMessage?.(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.handlers.onError?.(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        this.handlers.onClose?.();
        this.attemptReconnect();
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
      
      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay * this.reconnectAttempts);
    }
  }

  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

/**
 * 파일 업로드 헬퍼
 */
export async function uploadFile(
  endpoint: string,
  file: File,
  additionalData?: Record<string, string>
): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  
  if (additionalData) {
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, value);
    });
  }

  const token = localStorage.getItem('access_token');
  
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail);
  }

  return response.json();
}