# RAGPilot - Comprehensive RAG Lifecycle Management Platform

RAGPilot은 RAG (Retrieval Augmented Generation) 파이프라인의 전체 생명주기를 관리하는 종합 플랫폼입니다. LangGraph 기반의 고급 GraphRAG와 기본 Naive RAG 구현을 모두 지원하며, OpenSearch와 통합되어 문서 임베딩 및 검색 작업을 수행합니다.

## 🚀 주요 기능

- **듀얼 RAG 파이프라인**: GraphRAG (LangGraph) 및 Naive RAG 구현 지원
- **시각적 RAG 빌더**: 드래그 앤 드롭 방식의 LangGraph 컴포넌트 GUI
- **OpenSearch 통합**: 문서 임베딩, 인덱싱, 검색 워크플로우
- **성능 벤치마킹**: RAG 접근 방식 비교 및 성능 메트릭 평가
- **실시간 모니터링**: WebSocket을 통한 파이프라인 실행 상태 업데이트
- **AI 기반 최적화**: RAG 구성 개선을 위한 AI 제안 도구

## 📋 시스템 요구사항

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+
- Redis 7+
- OpenSearch 2.11+
- Docker & Docker Compose (선택사항)

## 🛠️ 설치 및 실행

### 1. 저장소 클론

```bash
git clone https://github.com/your-org/ragpilot.git
cd ragpilot
```

### 2. 백엔드 설정

#### 2.1 Python 가상환경 생성

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

#### 2.2 의존성 설치

```bash
pip install -r requirements.txt
```

#### 2.3 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 입력
```

#### 2.4 Docker로 서비스 실행 (권장)

```bash
docker-compose up -d
```

이 명령은 다음 서비스들을 실행합니다:
- PostgreSQL (5432 포트)
- Redis (6379 포트)
- OpenSearch (9200 포트)
- OpenSearch Dashboards (5601 포트)

#### 2.5 데이터베이스 마이그레이션

```bash
# 데이터베이스 테이블 생성
alembic upgrade head

# 초기 데이터 설정
python scripts/init_db.py
```

#### 2.6 백엔드 서버 실행

```bash
# 개발 서버
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 또는 Docker를 사용하는 경우
docker-compose up backend
```

### 3. 프론트엔드 설정

새 터미널을 열고:

```bash
# 프로젝트 루트로 이동
cd ..

# 의존성 설치
npm install
```

#### 3.1 환경 변수 설정

```bash
cp .env.local.example .env.local
# .env.local 파일을 편집하여 API URL 등 설정
```

#### 3.2 개발 서버 실행

```bash
npm run dev
```

프론트엔드는 http://localhost:3000 에서 접근 가능합니다.

### 4. 초기 로그인

기본 관리자 계정:
- 사용자명: `admin`
- 비밀번호: `admin123!@#`

⚠️ **보안 주의**: 프로덕션 환경에서는 반드시 비밀번호를 변경하세요!

## 📁 프로젝트 구조

```
ragpilot/
├── backend/                 # Python FastAPI 백엔드
│   ├── app/
│   │   ├── api/            # API 엔드포인트
│   │   ├── core/           # 핵심 설정 및 보안
│   │   ├── db/             # 데이터베이스 모델 및 세션
│   │   ├── models/         # SQLAlchemy 모델
│   │   ├── schemas/        # Pydantic 스키마
│   │   ├── services/       # 비즈니스 로직
│   │   └── utils/          # 유틸리티 함수
│   ├── tests/              # 테스트 파일
│   ├── docker-compose.yml  # Docker 설정
│   ├── Dockerfile          # 백엔드 Docker 이미지
│   └── requirements.txt    # Python 의존성
│
├── src/                    # Next.js 프론트엔드
│   ├── app/               # Next.js 13+ App Router
│   ├── components/        # React 컴포넌트
│   ├── lib/              # 유틸리티 및 API 클라이언트
│   └── hooks/            # React 커스텀 훅
│
├── docs/                  # 프로젝트 문서
├── scripts/              # 유틸리티 스크립트
└── README.md            # 이 파일
```

## 🔧 주요 API 엔드포인트

### 인증
- `POST /api/v1/auth/login` - 로그인
- `POST /api/v1/auth/register` - 회원가입
- `GET /api/v1/auth/me` - 현재 사용자 정보

### 파이프라인 관리
- `GET /api/v1/pipelines` - 파이프라인 목록
- `POST /api/v1/pipelines` - 파이프라인 생성
- `POST /api/v1/pipelines/{id}/execute` - 파이프라인 실행

### OpenSearch
- `GET /api/v1/opensearch/health` - 클러스터 상태
- `POST /api/v1/opensearch/indices` - 인덱스 생성
- `POST /api/v1/opensearch/search` - 문서 검색

### 벤치마킹
- `POST /api/v1/benchmarks` - 벤치마크 생성
- `GET /api/v1/benchmarks/{id}` - 결과 조회

## 🧪 테스트 실행

### 백엔드 테스트

```bash
cd backend
pytest
```

### 프론트엔드 테스트

```bash
npm test
```

## 🚀 프로덕션 배포

### Docker를 사용한 배포

1. 프로덕션용 환경 변수 설정:
```bash
cp .env.example .env.production
# 프로덕션 설정으로 편집
```

2. Docker 이미지 빌드:
```bash
docker-compose -f docker-compose.prod.yml build
```

3. 서비스 실행:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes 배포

Kubernetes 매니페스트 파일은 `k8s/` 디렉토리에 있습니다:

```bash
kubectl apply -f k8s/
```

## 📊 모니터링

- **OpenSearch Dashboards**: http://localhost:5601
- **API 문서 (Swagger)**: http://localhost:8000/api/v1/docs
- **Prometheus 메트릭**: http://localhost:8000/metrics

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🙋‍♂️ 지원

문제가 발생하거나 질문이 있으시면:
- GitHub Issues를 통해 버그 리포트
- 프로젝트 Wiki 참조
- 팀에 문의: support@ragpilot.com

## 🔐 보안 고려사항

프로덕션 환경에서는 다음을 확인하세요:

1. 모든 기본 비밀번호 변경
2. HTTPS 활성화
3. 적절한 CORS 설정
4. 환경 변수의 안전한 관리
5. 정기적인 보안 업데이트

---

**Happy RAG Building! 🚀**

---

# Firebase Studio

This is a NextJS starter in Firebase Studio.

To get started, take a look at src/app/page.tsx.
