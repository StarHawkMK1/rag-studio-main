# rag-studio/backend/app/services/benchmark_service.py
"""
RAG 파이프라인 벤치마킹 서비스

여러 파이프라인의 성능을 비교 평가하는 기능을 제공합니다.
"""

import asyncio
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from app.core.config import settings
from app.utils.logger import logger
from app.services.rag_executor import pipeline_manager, PipelineConfig
from app.schemas.benchmark import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkMetrics,
    QueryTestCase,
    ComparisonResult
)
from app.schemas.pipeline import QueryInput, PipelineType


@dataclass
class BenchmarkStats:
    """벤치마크 통계 데이터"""
    latencies: List[float]
    retrieval_scores: List[float]
    success_count: int
    failure_count: int
    error_messages: List[str]


class BenchmarkService:
    """
    파이프라인 벤치마킹 서비스
    
    여러 파이프라인을 동일한 테스트 세트로 평가하고
    성능 메트릭을 비교 분석합니다.
    """
    
    def __init__(self):
        """벤치마킹 서비스 초기화"""
        self.running_benchmarks: Dict[str, bool] = {}
        self._lock = asyncio.Lock()
        
        logger.info("벤치마킹 서비스가 초기화되었습니다.")
    
    async def run_benchmark(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
        test_cases: List[QueryTestCase]
    ) -> BenchmarkResult:
        """
        벤치마크 실행
        
        Args:
            benchmark_id: 벤치마크 ID
            config: 벤치마크 설정
            test_cases: 테스트 케이스 리스트
            
        Returns:
            BenchmarkResult: 벤치마크 결과
        """
        async with self._lock:
            if benchmark_id in self.running_benchmarks:
                raise ValueError(f"벤치마크 '{benchmark_id}'가 이미 실행 중입니다.")
            self.running_benchmarks[benchmark_id] = True
        
        try:
            start_time = datetime.utcnow()
            logger.info(f"벤치마크 시작: {benchmark_id}")
            
            # 파이프라인별 결과 저장
            pipeline_results: Dict[str, BenchmarkStats] = {}
            
            # 각 파이프라인에 대해 테스트 실행
            for pipeline_id in config.pipeline_ids:
                logger.info(f"파이프라인 '{pipeline_id}' 테스트 시작")
                
                # 파이프라인 설정 조회 (실제로는 DB에서 조회)
                pipeline_config = await self._get_pipeline_config(pipeline_id)
                
                # 파이프라인 인스턴스 가져오기
                pipeline = await pipeline_manager.get_pipeline(pipeline_id, pipeline_config)
                
                # 테스트 실행
                stats = await self._run_pipeline_tests(
                    pipeline,
                    pipeline_id,
                    test_cases,
                    config
                )
                
                pipeline_results[pipeline_id] = stats
            
            # 결과 분석 및 메트릭 계산
            metrics = self._calculate_metrics(pipeline_results)
            
            # 파이프라인 간 비교 분석
            comparisons = self._compare_pipelines(pipeline_results, metrics)
            
            # 최종 결과 구성
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            result = BenchmarkResult(
                benchmark_id=benchmark_id,
                config=config,
                metrics=metrics,
                comparisons=comparisons,
                total_queries=len(test_cases),
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                status="completed"
            )
            
            logger.info(f"벤치마크 완료: {benchmark_id} (소요시간: {duration:.2f}초)")
            
            return result
            
        except Exception as e:
            logger.error(f"벤치마크 실행 중 오류: {str(e)}")
            
            # 오류 결과 반환
            error_result = BenchmarkResult(
                benchmark_id=benchmark_id,
                config=config,
                metrics={},
                comparisons=[],
                total_queries=len(test_cases),
                start_time=start_time,
                end_time=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                status="failed",
                error=str(e)
            )
            
            return error_result
            
        finally:
            async with self._lock:
                self.running_benchmarks.pop(benchmark_id, None)
    
    async def _run_pipeline_tests(
        self,
        pipeline: Any,
        pipeline_id: str,
        test_cases: List[QueryTestCase],
        config: BenchmarkConfig
    ) -> BenchmarkStats:
        """
        특정 파이프라인에 대한 테스트 실행
        
        Args:
            pipeline: 파이프라인 인스턴스
            pipeline_id: 파이프라인 ID
            test_cases: 테스트 케이스
            config: 벤치마크 설정
            
        Returns:
            BenchmarkStats: 테스트 통계
        """
        latencies = []
        retrieval_scores = []
        success_count = 0
        failure_count = 0
        error_messages = []
        
        # 워밍업 실행 (선택적)
        if config.warmup_queries > 0:
            logger.info(f"워밍업 쿼리 {config.warmup_queries}개 실행 중...")
            for i in range(min(config.warmup_queries, len(test_cases))):
                query = QueryInput(
                    query_text=test_cases[i].query,
                    top_k=config.top_k
                )
                try:
                    await pipeline.process_query(query)
                except Exception:
                    pass  # 워밍업 오류는 무시
        
        # 실제 테스트 실행
        for i, test_case in enumerate(test_cases):
            # 타임아웃 체크
            if config.timeout_seconds and i * 5 > config.timeout_seconds:
                logger.warning(f"타임아웃으로 인해 테스트 중단: {pipeline_id}")
                break
            
            query = QueryInput(
                query_id=f"{benchmark_id}_{pipeline_id}_{i}",
                query_text=test_case.query,
                top_k=config.top_k
            )
            
            try:
                # 쿼리 실행
                result = await pipeline.process_query(query)
                
                # 메트릭 수집
                latencies.append(result.latency_ms)
                
                # 검색 점수 수집
                if result.retrieved_documents:
                    scores = [doc["score"] for doc in result.retrieved_documents]
                    avg_score = sum(scores) / len(scores)
                    retrieval_scores.append(avg_score)
                
                success_count += 1
                
                # 정답이 있는 경우 정확도 평가
                if test_case.expected_answer:
                    # TODO: 답변 품질 평가 로직 추가
                    pass
                
            except Exception as e:
                failure_count += 1
                error_messages.append(f"Query {i}: {str(e)}")
                logger.error(f"테스트 케이스 {i} 실행 실패: {str(e)}")
            
            # 진행률 로깅
            if (i + 1) % 10 == 0:
                logger.info(f"파이프라인 {pipeline_id}: {i + 1}/{len(test_cases)} 완료")
        
        return BenchmarkStats(
            latencies=latencies,
            retrieval_scores=retrieval_scores,
            success_count=success_count,
            failure_count=failure_count,
            error_messages=error_messages
        )
    
    def _calculate_metrics(
        self,
        pipeline_results: Dict[str, BenchmarkStats]
    ) -> Dict[str, BenchmarkMetrics]:
        """
        파이프라인별 메트릭 계산
        
        Args:
            pipeline_results: 파이프라인별 실행 결과
            
        Returns:
            Dict[str, BenchmarkMetrics]: 파이프라인별 메트릭
        """
        metrics = {}
        
        for pipeline_id, stats in pipeline_results.items():
            # 지연시간 통계
            if stats.latencies:
                latency_array = np.array(stats.latencies)
                latency_metrics = {
                    "mean": float(np.mean(latency_array)),
                    "median": float(np.median(latency_array)),
                    "std": float(np.std(latency_array)),
                    "min": float(np.min(latency_array)),
                    "max": float(np.max(latency_array)),
                    "p95": float(np.percentile(latency_array, 95)),
                    "p99": float(np.percentile(latency_array, 99))
                }
            else:
                latency_metrics = {
                    "mean": 0.0, "median": 0.0, "std": 0.0,
                    "min": 0.0, "max": 0.0, "p95": 0.0, "p99": 0.0
                }
            
            # 검색 점수 통계
            if stats.retrieval_scores:
                score_array = np.array(stats.retrieval_scores)
                retrieval_metrics = {
                    "mean": float(np.mean(score_array)),
                    "median": float(np.median(score_array)),
                    "std": float(np.std(score_array)),
                    "min": float(np.min(score_array)),
                    "max": float(np.max(score_array))
                }
            else:
                retrieval_metrics = {
                    "mean": 0.0, "median": 0.0, "std": 0.0,
                    "min": 0.0, "max": 0.0
                }
            
            # 성공률 계산
            total_queries = stats.success_count + stats.failure_count
            success_rate = stats.success_count / total_queries if total_queries > 0 else 0.0
            
            # 처리량 계산 (초당 쿼리 수)
            total_time_seconds = sum(stats.latencies) / 1000.0 if stats.latencies else 0
            throughput = stats.success_count / total_time_seconds if total_time_seconds > 0 else 0.0
            
            # 메트릭 객체 생성
            benchmark_metrics = BenchmarkMetrics(
                pipeline_id=pipeline_id,
                latency_ms=latency_metrics,
                retrieval_score=retrieval_metrics,
                success_rate=success_rate,
                throughput_qps=throughput,
                total_queries=total_queries,
                failed_queries=stats.failure_count,
                error_rate=stats.failure_count / total_queries if total_queries > 0 else 0.0
            )
            
            metrics[pipeline_id] = benchmark_metrics
        
        return metrics
    
    def _compare_pipelines(
        self,
        pipeline_results: Dict[str, BenchmarkStats],
        metrics: Dict[str, BenchmarkMetrics]
    ) -> List[ComparisonResult]:
        """
        파이프라인 간 성능 비교
        
        Args:
            pipeline_results: 파이프라인별 실행 결과
            metrics: 계산된 메트릭
            
        Returns:
            List[ComparisonResult]: 비교 결과 리스트
        """
        comparisons = []
        pipeline_ids = list(metrics.keys())
        
        # 모든 파이프라인 쌍에 대해 비교
        for i in range(len(pipeline_ids)):
            for j in range(i + 1, len(pipeline_ids)):
                pipeline_a = pipeline_ids[i]
                pipeline_b = pipeline_ids[j]
                
                metrics_a = metrics[pipeline_a]
                metrics_b = metrics[pipeline_b]
                
                # 지연시간 비교
                latency_diff = metrics_b.latency_ms["mean"] - metrics_a.latency_ms["mean"]
                latency_improvement = (latency_diff / metrics_a.latency_ms["mean"]) * 100 if metrics_a.latency_ms["mean"] > 0 else 0
                
                # 검색 점수 비교
                score_diff = metrics_b.retrieval_score["mean"] - metrics_a.retrieval_score["mean"]
                score_improvement = (score_diff / metrics_a.retrieval_score["mean"]) * 100 if metrics_a.retrieval_score["mean"] > 0 else 0
                
                # 처리량 비교
                throughput_diff = metrics_b.throughput_qps - metrics_a.throughput_qps
                throughput_improvement = (throughput_diff / metrics_a.throughput_qps) * 100 if metrics_a.throughput_qps > 0 else 0
                
                # 승자 결정 (다중 기준)
                winner_criteria = {
                    "latency": pipeline_a if latency_diff > 0 else pipeline_b,
                    "retrieval_score": pipeline_b if score_diff > 0 else pipeline_a,
                    "throughput": pipeline_b if throughput_diff > 0 else pipeline_a,
                    "success_rate": pipeline_a if metrics_a.success_rate > metrics_b.success_rate else pipeline_b
                }
                
                # 종합 승자 (가중 평균)
                winner_scores = {pipeline_a: 0, pipeline_b: 0}
                for criterion, winner in winner_criteria.items():
                    winner_scores[winner] += 1
                
                overall_winner = max(winner_scores, key=winner_scores.get)
                
                # 비교 결과 생성
                comparison = ComparisonResult(
                    pipeline_a=pipeline_a,
                    pipeline_b=pipeline_b,
                    metrics_comparison={
                        "latency_difference_ms": latency_diff,
                        "latency_improvement_percent": latency_improvement,
                        "retrieval_score_difference": score_diff,
                        "retrieval_score_improvement_percent": score_improvement,
                        "throughput_difference_qps": throughput_diff,
                        "throughput_improvement_percent": throughput_improvement,
                        "success_rate_difference": metrics_b.success_rate - metrics_a.success_rate
                    },
                    winner=overall_winner,
                    winner_criteria=winner_criteria,
                    summary=f"{overall_winner}가 {len([w for w in winner_criteria.values() if w == overall_winner])}/4 기준에서 우수한 성능을 보였습니다."
                )
                
                comparisons.append(comparison)
        
        return comparisons
    
    async def _get_pipeline_config(self, pipeline_id: str) -> PipelineConfig:
        """
        파이프라인 설정 조회 (임시 구현)
        
        실제로는 데이터베이스에서 조회해야 합니다.
        """
        # TODO: 데이터베이스에서 실제 설정 조회
        return PipelineConfig(
            name=f"Pipeline {pipeline_id}",
            pipeline_type=PipelineType.NAIVE_RAG,  # 기본값
            index_name="test_index",
            retrieval_top_k=5,
            temperature=0.7,
            max_tokens=2000
        )
    
    def generate_test_cases(
        self,
        num_cases: int,
        query_types: Optional[List[str]] = None
    ) -> List[QueryTestCase]:
        """
        테스트 케이스 자동 생성
        
        Args:
            num_cases: 생성할 테스트 케이스 수
            query_types: 쿼리 유형 리스트
            
        Returns:
            List[QueryTestCase]: 생성된 테스트 케이스
        """
        if not query_types:
            query_types = ["factual", "analytical", "comparative", "explanatory"]
        
        # 샘플 쿼리 템플릿
        query_templates = {
            "factual": [
                "What is {}?",
                "Define {}.",
                "When was {} established?",
                "Who invented {}?",
                "Where is {} located?"
            ],
            "analytical": [
                "What are the advantages of {}?",
                "How does {} work?",
                "What factors influence {}?",
                "Analyze the impact of {} on {}.",
                "What are the key components of {}?"
            ],
            "comparative": [
                "Compare {} and {}.",
                "What is the difference between {} and {}?",
                "Which is better: {} or {}?",
                "How does {} differ from {}?",
                "Contrast {} with {}."
            ],
            "explanatory": [
                "Explain the concept of {}.",
                "Why is {} important?",
                "How can {} be improved?",
                "What causes {}?",
                "Describe the process of {}."
            ]
        }
        
        # 샘플 토픽
        topics = [
            "machine learning", "natural language processing", "computer vision",
            "deep learning", "reinforcement learning", "neural networks",
            "transformers", "attention mechanism", "gradient descent",
            "backpropagation", "convolutional networks", "recurrent networks"
        ]
        
        test_cases = []
        
        for i in range(num_cases):
            # 쿼리 유형 선택
            query_type = query_types[i % len(query_types)]
            
            # 템플릿 선택
            template = query_templates[query_type][i % len(query_templates[query_type])]
            
            # 토픽 선택
            if "{}" in template:
                topic_count = template.count("{}")
                selected_topics = np.random.choice(topics, topic_count, replace=False)
                query = template.format(*selected_topics)
            else:
                query = template
            
            # 테스트 케이스 생성
            test_case = QueryTestCase(
                query_id=f"test_{i:04d}",
                query=query,
                query_type=query_type,
                expected_answer=None,  # 자동 생성된 경우 정답 없음
                metadata={
                    "auto_generated": True,
                    "template": template,
                    "index": i
                }
            )
            
            test_cases.append(test_case)
        
        logger.info(f"{num_cases}개의 테스트 케이스가 자동 생성되었습니다.")
        
        return test_cases
    
    async def export_results(
        self,
        result: BenchmarkResult,
        format: str = "json"
    ) -> str:
        """
        벤치마크 결과 내보내기
        
        Args:
            result: 벤치마크 결과
            format: 출력 형식 (json, csv, html)
            
        Returns:
            str: 포맷팅된 결과 문자열
        """
        if format == "json":
            return json.dumps(result.dict(), indent=2, default=str)
        
        elif format == "csv":
            # CSV 형식으로 변환
            csv_lines = ["Pipeline ID,Mean Latency (ms),Retrieval Score,Success Rate,Throughput (QPS)"]
            
            for pipeline_id, metrics in result.metrics.items():
                line = f"{pipeline_id},{metrics.latency_ms['mean']:.2f},{metrics.retrieval_score['mean']:.4f},{metrics.success_rate:.2%},{metrics.throughput_qps:.2f}"
                csv_lines.append(line)
            
            return "\n".join(csv_lines)
        
        elif format == "html":
            # HTML 리포트 생성
            html = f"""
            <html>
            <head>
                <title>Benchmark Report - {result.benchmark_id}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #4CAF50; color: white; }}
                    tr:nth-child(even) {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h1>Benchmark Report</h1>
                <p><strong>ID:</strong> {result.benchmark_id}</p>
                <p><strong>Duration:</strong> {result.duration_seconds:.2f} seconds</p>
                <p><strong>Total Queries:</strong> {result.total_queries}</p>
                
                <h2>Pipeline Performance</h2>
                <table>
                    <tr>
                        <th>Pipeline</th>
                        <th>Mean Latency (ms)</th>
                        <th>P95 Latency (ms)</th>
                        <th>Retrieval Score</th>
                        <th>Success Rate</th>
                        <th>Throughput (QPS)</th>
                    </tr>
            """
            
            for pipeline_id, metrics in result.metrics.items():
                html += f"""
                    <tr>
                        <td>{pipeline_id}</td>
                        <td>{metrics.latency_ms['mean']:.2f}</td>
                        <td>{metrics.latency_ms['p95']:.2f}</td>
                        <td>{metrics.retrieval_score['mean']:.4f}</td>
                        <td>{metrics.success_rate:.2%}</td>
                        <td>{metrics.throughput_qps:.2f}</td>
                    </tr>
                """
            
            html += """
                </table>
                
                <h2>Pipeline Comparisons</h2>
            """
            
            for comp in result.comparisons:
                html += f"""
                    <h3>{comp.pipeline_a} vs {comp.pipeline_b}</h3>
                    <p><strong>Winner:</strong> {comp.winner}</p>
                    <p>{comp.summary}</p>
                """
            
            html += """
            </body>
            </html>
            """
            
            return html
        
        else:
            raise ValueError(f"지원하지 않는 형식: {format}")


# 전역 벤치마킹 서비스 인스턴스
benchmark_service = BenchmarkService()