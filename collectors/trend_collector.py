"""
여러 데이터 소스에서 트렌드 데이터를 통합 수집하는 모듈
"""
import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, Set, Tuple
from datetime import datetime
import time
from dataclasses import dataclass
from abc import ABC, abstractmethod

from collectors.youtube_collector import YouTubeCollector
from collectors.news_collector import NewsCollector
from collectors.portal_collector import PortalCollector
from collectors.google_trends_collector import GoogleTrendsCollector, Country, TimeFrame

# 로그 설정
logger = logging.getLogger('trend_collector')

@dataclass
class CollectorStatus:
    """수집기 상태 정보"""
    available: bool
    error_message: Optional[str] = None
    
    @property
    def is_ok(self) -> bool:
        return self.available and self.error_message is None

class DataSource(ABC):
    """데이터 소스 인터페이스"""
    
    @abstractmethod
    def is_available(self) -> bool:
        """소스가 사용 가능한지 확인"""
        pass
    
    @abstractmethod
    def get_status(self) -> CollectorStatus:
        """소스의 상태 정보 반환"""
        pass

class TrendCollector:
    """
    통합 트렌드 데이터 수집기 클래스
    - 유튜브, 뉴스, 포털, 구글 트렌드 등의 트렌드 데이터를 통합 수집
    - 비동기 수집 지원
    """
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        트렌드 통합 수집기 초기화
        
        Args:
            max_retries: 수집 실패 시 최대 재시도 횟수
            retry_delay: 재시도 간 대기 시간(초)
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # 수집기 초기화
        self.collectors = {}
        self._initialize_collectors()
    
    def _initialize_collectors(self) -> None:
        """각 수집기 초기화"""
        # 유튜브 수집기 초기화 (API 키 필요)
        youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        if youtube_api_key:
            try:
                self.collectors['youtube'] = YouTubeCollector(api_key=youtube_api_key)
                logger.info("YouTube 수집기 초기화 성공")
            except Exception as e:
                logger.error(f"YouTube 수집기 초기화 오류: {str(e)}")
                self.collectors['youtube'] = None
        else:
            logger.warning("YOUTUBE_API_KEY가 설정되지 않아 YouTube 수집 기능이 비활성화됩니다.")
            self.collectors['youtube'] = None
        
        # 뉴스 수집기 초기화
        try:
            self.collectors['news'] = NewsCollector()
            logger.info("뉴스 수집기 초기화 성공")
        except Exception as e:
            logger.error(f"뉴스 수집기 초기화 오류: {str(e)}")
            self.collectors['news'] = None
        
        # 포털 수집기 초기화
        try:
            self.collectors['portal'] = PortalCollector()
            logger.info("포털 수집기 초기화 성공")
        except Exception as e:
            logger.error(f"포털 수집기 초기화 오류: {str(e)}")
            self.collectors['portal'] = None
            
        # 구글 트렌드 수집기 초기화
        try:
            self.collectors['google_trends'] = GoogleTrendsCollector()
            logger.info("Google Trends 수집기 초기화 성공")
        except Exception as e:
            logger.error(f"Google Trends 수집기 초기화 오류: {str(e)}")
            self.collectors['google_trends'] = None
    
    def check_collectors(self) -> Dict[str, bool]:
        """
        각 수집기의 가용성을 확인합니다.
        
        Returns:
            소스별 가용성 정보
        """
        return {
            name: collector is not None 
            for name, collector in self.collectors.items()
        }
    
    def get_collector_details(self) -> Dict[str, CollectorStatus]:
        """
        각 수집기의 상세 상태를 확인합니다.
        
        Returns:
            소스별 상태 정보
        """
        statuses = {}
        
        # YouTube 수집기 상태
        if self.collectors['youtube']:
            try:
                statuses['youtube'] = CollectorStatus(
                    available=True,
                    error_message=None
                )
            except Exception as e:
                statuses['youtube'] = CollectorStatus(
                    available=False,
                    error_message=str(e)
                )
        else:
            statuses['youtube'] = CollectorStatus(
                available=False,
                error_message="YouTube 수집기가 초기화되지 않았습니다"
            )
        
        # 뉴스 수집기 상태
        if self.collectors['news']:
            try:
                statuses['news'] = CollectorStatus(
                    available=True,
                    error_message=None
                )
            except Exception as e:
                statuses['news'] = CollectorStatus(
                    available=False,
                    error_message=str(e)
                )
        else:
            statuses['news'] = CollectorStatus(
                available=False,
                error_message="뉴스 수집기가 초기화되지 않았습니다"
            )
        
        # 포털 수집기 상태
        if self.collectors['portal']:
            try:
                statuses['portal'] = CollectorStatus(
                    available=True,
                    error_message=None
                )
            except Exception as e:
                statuses['portal'] = CollectorStatus(
                    available=False,
                    error_message=str(e)
                )
        else:
            statuses['portal'] = CollectorStatus(
                available=False,
                error_message="포털 수집기가 초기화되지 않았습니다"
            )
        
        # Google Trends 수집기 상태
        if self.collectors['google_trends']:
            try:
                health_ok, health_msg = self.collectors['google_trends'].health_check()
                statuses['google_trends'] = CollectorStatus(
                    available=health_ok,
                    error_message=None if health_ok else health_msg
                )
            except Exception as e:
                statuses['google_trends'] = CollectorStatus(
                    available=False,
                    error_message=str(e)
                )
        else:
            statuses['google_trends'] = CollectorStatus(
                available=False,
                error_message="Google Trends 수집기가 초기화되지 않았습니다"
            )
            
        return statuses
    
    async def collect_all_trends(
        self, 
        include_youtube: bool = True,
        include_news: bool = True,
        include_portal: bool = True,
        include_google_trends: bool = True,
        max_per_source: int = 50
    ) -> Dict[str, Any]:
        """
        모든 소스에서 트렌드 데이터를 수집합니다.
        
        Args:
            include_youtube: YouTube 데이터 포함 여부
            include_news: 뉴스 데이터 포함 여부
            include_portal: 포털 검색어 데이터 포함 여부
            include_google_trends: Google Trends 데이터 포함 여부
            max_per_source: 소스별 최대 결과 수
            
        Returns:
            통합된 트렌드 데이터
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'sources': {}
        }
        
        # 수집기 상태 확인
        collectors_status = self.check_collectors()
        tasks = []
        
        # YouTube 트렌드 수집 태스크
        if include_youtube and collectors_status['youtube']:
            tasks.append(self._collect_youtube_trends(max_per_source))
        
        # 뉴스 트렌드 수집 태스크
        if include_news and collectors_status['news']:
            tasks.append(self._collect_news_trends(max_per_source))
        
        # 포털 인기 검색어 수집 태스크
        if include_portal and collectors_status['portal']:
            tasks.append(self._collect_portal_trends(max_per_source))
        
        # Google Trends 수집 태스크
        if include_google_trends and collectors_status['google_trends']:
            tasks.append(self._collect_google_trends(max_per_source))
        
        # 모든 태스크 병렬 실행
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            for result in task_results:
                if isinstance(result, Exception):
                    logger.error(f"수집 중 오류 발생: {str(result)}")
                elif isinstance(result, tuple) and len(result) == 2:
                    source_name, source_data = result
                    results['sources'][source_name] = source_data
        
        return results
    
    async def _collect_youtube_trends(self, max_results: int) -> Tuple[str, List[Dict[str, Any]]]:
        """YouTube 트렌드 수집 헬퍼 메서드"""
        for attempt in range(self.max_retries):
            try:
                loop = asyncio.get_event_loop()
                youtube_results = await loop.run_in_executor(
                    None, 
                    lambda: self.collectors['youtube'].fetch_trending_videos(
                        region_code='KR', 
                        max_results=max_results
                    )
                )
                return ('youtube', youtube_results)
            except Exception as e:
                logger.error(f"YouTube 트렌드 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"YouTube 트렌드 수집 최대 재시도 횟수 초과")
        return ('youtube', [])
    
    async def _collect_news_trends(self, max_per_source: int) -> Tuple[str, Dict[str, List[Dict[str, Any]]]]:
        """뉴스 트렌드 수집 헬퍼 메서드"""
        for attempt in range(self.max_retries):
            try:
                news_results = await self.collectors['news'].fetch_all_news_trending(
                    max_per_source=max_per_source
                )
                return ('news', news_results)
            except Exception as e:
                logger.error(f"뉴스 트렌드 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"뉴스 트렌드 수집 최대 재시도 횟수 초과")
        return ('news', {})
    
    async def _collect_portal_trends(self, max_per_source: int) -> Tuple[str, Dict[str, List[Dict[str, Any]]]]:
        """포털 인기 검색어 수집 헬퍼 메서드"""
        for attempt in range(self.max_retries):
            try:
                portal_results = await self.collectors['portal'].fetch_all_portal_trending(
                    max_per_source=max_per_source
                )
                return ('portal', portal_results)
            except Exception as e:
                logger.error(f"포털 인기 검색어 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"포털 인기 검색어 수집 최대 재시도 횟수 초과")
        return ('portal', {})
    
    async def _collect_google_trends(self, max_results: int) -> Tuple[str, List[Dict[str, Any]]]:
        """Google Trends 수집 헬퍼 메서드"""
        for attempt in range(self.max_retries):
            try:
                loop = asyncio.get_event_loop()
                google_trends_results = await loop.run_in_executor(
                    None, 
                    lambda: self.collectors['google_trends'].fetch_realtime_trends(
                        max_results=max_results
                    )
                )
                return ('google_trends', google_trends_results)
            except Exception as e:
                logger.error(f"Google Trends 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"Google Trends 수집 최대 재시도 횟수 초과")
        return ('google_trends', [])
    
    def collect_youtube_trends(
        self, 
        region_code: str = 'KR', 
        max_results: int = 100,
        by_category: bool = False,
        max_categories: Optional[int] = None,
        max_per_category: int = 10
    ) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """
        YouTube 인기 동영상을 수집합니다.
        
        Args:
            region_code: 국가 코드
            max_results: 최대 결과 수 (by_category=False일 때)
            by_category: 카테고리별로 수집할지 여부
            max_categories: 최대 카테고리 수 (by_category=True일 때)
            max_per_category: 카테고리당 최대 결과 수 (by_category=True일 때)
            
        Returns:
            인기 동영상 목록 또는 카테고리별 동영상 목록
            
        Raises:
            RuntimeError: 수집기가 초기화되지 않은 경우
        """
        if not self.collectors['youtube']:
            raise RuntimeError("YouTube 수집기가 초기화되지 않았습니다")
        
        for attempt in range(self.max_retries):
            try:
                if by_category:
                    # 카테고리별 인기 동영상 수집
                    return self.collectors['youtube'].fetch_trending_videos_by_category(
                        region_code=region_code,
                        max_per_category=max_per_category,
                        max_categories=max_categories
                    )
                else:
                    # 전체 인기 동영상 수집
                    return self.collectors['youtube'].fetch_trending_videos(
                        region_code=region_code,
                        max_results=max_results
                    )
            except Exception as e:
                logger.error(f"YouTube 트렌드 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"YouTube 트렌드 수집 최대 재시도 횟수 초과")
        return [] if not by_category else {}
    
    async def collect_news_trends(
        self, 
        sources: Optional[List[str]] = None,
        category: Optional[str] = None,
        max_per_source: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        뉴스 인기 기사를 수집합니다.
        
        Args:
            sources: 수집할 소스 목록 ('naver', 'daum', 'google')
            category: 뉴스 카테고리
            max_per_source: 소스별 최대 결과 수
            
        Returns:
            소스별 뉴스 기사 정보
            
        Raises:
            RuntimeError: 수집기가 초기화되지 않은 경우
        """
        if not self.collectors['news']:
            raise RuntimeError("뉴스 수집기가 초기화되지 않았습니다")
            
        # 기본값: 모든 소스
        if sources is None:
            sources = ['naver', 'daum', 'google']
        
        for attempt in range(self.max_retries):
            try:
                if len(sources) > 1:
                    # 여러 소스에서 병렬 수집
                    all_news = await self.collectors['news'].fetch_all_news_trending(
                        category=category,
                        max_per_source=max_per_source
                    )
                    
                    # 지정된 소스만 필터링
                    return {src: all_news.get(src, []) for src in sources if src in all_news}
                elif len(sources) == 1:
                    # 단일 소스에서만 수집
                    source = sources[0]
                    results = {}
                    
                    loop = asyncio.get_event_loop()
                    
                    if source == 'naver':
                        results[source] = await loop.run_in_executor(
                            None,
                            lambda: self.collectors['news'].fetch_naver_news_trending(
                                category=category,
                                max_results=max_per_source
                            )
                        )
                    elif source == 'daum':
                        results[source] = await loop.run_in_executor(
                            None,
                            lambda: self.collectors['news'].fetch_daum_news_trending(
                                category=category,
                                max_results=max_per_source
                            )
                        )
                    elif source == 'google':
                        results[source] = await loop.run_in_executor(
                            None,
                            lambda: self.collectors['news'].fetch_google_news_trending(
                                region='ko-KR',
                                max_results=max_per_source
                            )
                        )
                    
                    return results
                else:
                    return {}
            except Exception as e:
                logger.error(f"뉴스 트렌드 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"뉴스 트렌드 수집 최대 재시도 횟수 초과")
        return {}
    
    async def collect_portal_trends(
        self, 
        sources: Optional[List[str]] = None,
        max_per_source: int = 20
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        포털 인기 검색어를 수집합니다.
        
        Args:
            sources: 수집할 소스 목록 ('naver', 'daum', 'zum', 'nate')
            max_per_source: 소스별 최대 결과 수
            
        Returns:
            소스별 인기 검색어 정보
            
        Raises:
            RuntimeError: 수집기가 초기화되지 않은 경우
        """
        if not self.collectors['portal']:
            raise RuntimeError("포털 수집기가 초기화되지 않았습니다")
            
        # 기본값: 모든 소스
        if sources is None:
            sources = ['naver', 'daum', 'zum', 'nate']
        
        for attempt in range(self.max_retries):
            try:
                if len(sources) > 1:
                    # 여러 소스에서 병렬 수집
                    all_trends = await self.collectors['portal'].fetch_all_portal_trending(
                        max_per_source=max_per_source
                    )
                    
                    # 지정된 소스만 필터링
                    return {src: all_trends.get(src, []) for src in sources if src in all_trends}
                elif len(sources) == 1:
                    # 단일 소스에서만 수집
                    source = sources[0]
                    results = {}
                    loop = asyncio.get_event_loop()
                    
                    if source == 'naver':
                        results[source] = await loop.run_in_executor(
                            None,
                            lambda: self.collectors['portal'].fetch_naver_trending_searches(
                                max_results=max_per_source
                            )
                        )
                    elif source == 'daum':
                        results[source] = await loop.run_in_executor(
                            None,
                            lambda: self.collectors['portal'].fetch_daum_trending_searches(
                                max_results=max_per_source
                            )
                        )
                    elif source == 'zum':
                        results[source] = await loop.run_in_executor(
                            None,
                            lambda: self.collectors['portal'].fetch_zum_trending_searches(
                                max_results=max_per_source
                            )
                        )
                    elif source == 'nate':
                        results[source] = await loop.run_in_executor(
                            None,
                            lambda: self.collectors['portal'].fetch_nate_trending_searches(
                                max_results=max_per_source
                            )
                        )
                    
                    return results
                else:
                    return {}
            except Exception as e:
                logger.error(f"포털 인기 검색어 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"포털 인기 검색어 수집 최대 재시도 횟수 초과")
        return {}
            
    def collect_google_trends(
        self, 
        country: Union[str, Country] = Country.SOUTH_KOREA,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Google Trends 실시간 인기 검색어를 수집합니다.
        
        Args:
            country: 국가 코드 또는 Country 열거형 (기본: Country.SOUTH_KOREA)
            max_results: 최대 결과 수
            
        Returns:
            실시간 트렌드 목록
            
        Raises:
            RuntimeError: 수집기가 초기화되지 않은 경우
        """
        if not self.collectors['google_trends']:
            raise RuntimeError("Google Trends 수집기가 초기화되지 않았습니다")
        
        for attempt in range(self.max_retries):
            try:
                return self.collectors['google_trends'].fetch_realtime_trends(
                    country=country,
                    max_results=max_results
                )
            except Exception as e:
                logger.error(f"Google Trends 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"Google Trends 수집 최대 재시도 횟수 초과")
        return []
            
    def collect_keyword_interest(
        self, 
        keywords: List[str],
        timeframe: Union[str, TimeFrame] = TimeFrame.PAST_DAY,
        geo: str = 'KR'
    ) -> Dict[str, Any]:
        """
        특정 키워드들의 검색 관심도를 수집합니다.
        
        Args:
            keywords: 검색할 키워드 목록 (최대 5개)
            timeframe: 시간 범위 문자열 또는 TimeFrame 열거형
            geo: 지역 코드
            
        Returns:
            키워드별 관심도 데이터
            
        Raises:
            RuntimeError: 수집기가 초기화되지 않은 경우
        """
        if not self.collectors['google_trends']:
            raise RuntimeError("Google Trends 수집기가 초기화되지 않았습니다")
        
        for attempt in range(self.max_retries):
            try:
                return self.collectors['google_trends'].fetch_keyword_interest(
                    keywords=keywords,
                    timeframe=timeframe,
                    geo=geo
                )
            except Exception as e:
                logger.error(f"키워드 관심도 수집 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"키워드 관심도 수집 최대 재시도 횟수 초과")
        return {'error': '키워드 관심도 수집에 실패했습니다'}
    
    def get_combined_trending_keywords(
        self, 
        portal_results: Dict[str, List[Dict[str, Any]]], 
        min_sources: int = 2,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        여러 포털에서 수집한 인기 검색어를 통합하여 순위를 매깁니다.
        
        Args:
            portal_results: 포털별 인기 검색어 결과
            min_sources: 최소 등장 소스 수 (필터링)
            max_results: 최대 결과 수
            
        Returns:
            통합 인기 검색어 목록 (순위화)
        """
        # 모든 키워드 수집 및 점수 계산
        keyword_scores = {}
        keyword_data = {}
        
        # 각 포털의 모든 키워드 처리
        for source, trends in portal_results.items():
            for trend in trends:
                keyword = trend.get('keyword', '').lower()
                if not keyword:
                    continue
                    
                # 이 키워드가 처음 등장하면 초기화
                if keyword not in keyword_scores:
                    keyword_scores[keyword] = 0
                    keyword_data[keyword] = {
                        'keyword': trend.get('keyword'),  # 원본 키워드(대소문자 유지)
                        'sources': set(),
                        'ranks': {},
                        'score': 0
                    }
                
                # 소스 추가
                keyword_data[keyword]['sources'].add(source)
                
                # 순위 저장
                rank = trend.get('rank', 999)
                keyword_data[keyword]['ranks'][source] = rank
                
                # 점수 계산 (순위 역수, 높은 순위일수록 높은 점수)
                # 1위: 20점, 2위: 19점, ..., 20위: 1점
                keyword_scores[keyword] += max(21 - rank, 1)
        
        # 최종 점수 저장 및 소스 수 기반 필터링
        result_keywords = []
        for keyword, data in keyword_data.items():
            # 소스 수 필터링
            if len(data['sources']) >= min_sources:
                data['sources'] = list(data['sources'])  # Set을 List로 변환
                data['score'] = keyword_scores[keyword]
                result_keywords.append(data)
        
        # 점수 기준 내림차순 정렬
        result_keywords.sort(key=lambda x: x['score'], reverse=True)
        
        # 최종 결과 포맷팅
        results = []
        for idx, data in enumerate(result_keywords[:max_results], 1):
            results.append({
                'rank': idx,
                'keyword': data['keyword'],
                'sources': data['sources'],
                'source_ranks': data['ranks'],
                'score': data['score'],
                'collected_at': datetime.now().isoformat()
            })
        
        return results