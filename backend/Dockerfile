# Python 3.11 슬림 이미지를 베이스로 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치 (PostgreSQL 클라이언트, 빌드 도구 등)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 업로드 디렉토리 생성
RUN mkdir -p /app/uploads

# 비루트 사용자 생성 및 권한 설정
RUN useradd -m -u 1000 ragstudio && \
    chown -R ragstudio:ragstudio /app

# 비루트 사용자로 전환
USER ragstudio

# 포트 노출
EXPOSE 8000

# 기본 실행 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]