"""
여러 데이터 소스에서 트렌드 데이터를 통합 수집하는 모듈
"""
import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import time

from collectors.youtube_collector import YouTubeCollector
from collectors.news_collector import NewsCollector
from collectors.portal_collector import PortalCollector
from collectors.google_trends_collector import GoogleTrendsCollector

# 로그 설정
logger = logging.getLogger('trend_collector')

class TrendCollector:
    """
    통합 트렌드 데이터 수집기 클래스
    - 유튜브, 뉴스, 포털, 구글 트렌드 등의 트렌드 데이터를 통합 수집
    - 비동기 수집 지원
    """
    
    def __init__(self):
        """트렌드 통합 수집기 초기화"""
        # 수집기 초기화
        try:
            # 유튜브 수집기 초기화 (API 키 필요)
            youtube_api_key = os.getenv('YOUTUBE_API_KEY')
            self.youtube_collector = YouTubeCollector(api_key=youtube_api_key) if youtube_api_key else None
            
            if not youtube_api_key:
                logger.warning("YOUTUBE_API_KEY가 설정되지 않아 유튜브 수집 기능이 비활성화됩니다.")
        except Exception as e:
            logger.error(f"유튜브 수집기 초기화 오류: {str(e)}")
            self.youtube_collector = None
        
        try:
            # 뉴스 수집기 초기화
            self.news_collector = NewsCollector()
        except Exception as e:
            logger.error(f"뉴스 수집기 초기화 오류: {str(e)}")
            self.news_collector = None
        
        try:
            # 포털 수집기 초기화
            self.portal_collector = PortalCollector()
        except Exception as e:
            logger.error(f"포털 수집기 초기화 오류: {str(e)}")
            self.portal_collector = None
            
        try:
            # 구글 트렌드 수집기 초기화
            self.google_trends_collector = GoogleTrendsCollector()
        except Exception as e:
            logger.error(f"구글 트렌드 수집기 초기화 오류: {str(e)}")
            self.google_trends_collector = None
    
    def check_collectors(self) -> Dict[str, bool]:
        """각 수집기의 가용성을 확인합니다."""
        return {
            'youtube': self.youtube_collector is not None,
            'news': self.news_collector is not None,
            'portal': self.portal_collector is not None,
            'google_trends': self.google_trends_collector is not None
        }
    
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
            include_youtube: 유튜브 데이터 포함 여부
            include_news: 뉴스 데이터 포함 여부
            include_portal: 포털 검색어 데이터 포함 여부
            include_google_trends: 구글 트렌드 데이터 포함 여부
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
        
        # 유튜브 트렌드 수집
        if include_youtube and collectors_status['youtube']:
            try:
                # 비동기 컨텍스트에서 동기 함수 실행
                loop = asyncio.get_event_loop()
                youtube_results = await loop.run_in_executor(
                    None, 
                    lambda: self.youtube_collector.fetch_trending_videos(
                        region_code='KR', 
                        max_results=max_per_source
                    )
                )
                results['sources']['youtube'] = youtube_results
            except Exception as e:
                logger.error(f"유튜브 트렌드 수집 오류: {str(e)}")
                results['sources']['youtube'] = []
        
        # 뉴스 트렌드 수집
        if include_news and collectors_status['news']:
            try:
                news_results = await self.news_collector.fetch_all_news_trending(
                    max_per_source=max_per_source
                )
                results['sources']['news'] = news_results
            except Exception as e:
                logger.error(f"뉴스 트렌드 수집 오류: {str(e)}")
                results['sources']['news'] = {}
        
        # 포털 인기 검색어 수집
        if include_portal and collectors_status['portal']:
            try:
                portal_results = await self.portal_collector.fetch_all_portal_trending(
                    max_per_source=max_per_source
                )
                results['sources']['portal'] = portal_results
            except Exception as e:
                logger.error(f"포털 인기 검색어 수집 오류: {str(e)}")
                results['sources']['portal'] = {}
                
        # 구글 트렌드 수집
        if include_google_trends and collectors_status['google_trends']:
            try:
                # 비동기 컨텍스트에서 동기 함수 실행
                loop = asyncio.get_event_loop()
                google_trends_results = await loop.run_in_executor(
                    None, 
                    lambda: self.google_trends_collector.fetch_realtime_trends(
                        max_results=max_per_source
                    )
                )
                results['sources']['google_trends'] = google_trends_results
            except Exception as e:
                logger.error(f"구글 트렌드 수집 오류: {str(e)}")
                results['sources']['google_trends'] = []
        
        return results
    
    def collect_youtube_trends(
        self, 
        region_code: str = 'KR', 
        max_results: int = 100,
        by_category: bool = False,
        max_categories: Optional[int] = None,
        max_per_category: int = 10
    ) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """
        유튜브 인기 동영상을 수집합니다.
        
        Args:
            region_code: 국가 코드
            max_results: 최대 결과 수 (by_category=False일 때)
            by_category: 카테고리별로 수집할지 여부
            max_categories: 최대 카테고리 수 (by_category=True일 때)
            max_per_category: 카테고리당 최대 결과 수 (by_category=True일 때)
            
        Returns:
            인기 동영상 목록 또는 카테고리별 동영상 목록
        """
        if not self.youtube_collector:
            logger.error("유튜브 수집기가 초기화되지 않았습니다.")
            return [] if not by_category else {}
        
        try:
            if by_category:
                # 카테고리별 인기 동영상 수집
                return self.youtube_collector.fetch_trending_videos_by_category(
                    region_code=region_code,
                    max_per_category=max_per_category,
                    max_categories=max_categories
                )
            else:
                # 전체 인기 동영상 수집
                return self.youtube_collector.fetch_trending_videos(
                    region_code=region_code,
                    max_results=max_results
                )
        except Exception as e:
            logger.error(f"유튜브 트렌드 수집 오류: {str(e)}")
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
        """
        if not self.news_collector:
            logger.error("뉴스 수집기가 초기화되지 않았습니다.")
            return {}
            
        # 기본값: 모든 소스
        if sources is None:
            sources = ['naver', 'daum', 'google']
            
        try:
            if len(sources) > 1:
                # 여러 소스에서 병렬 수집
                all_news = await self.news_collector.fetch_all_news_trending(
                    category=category,
                    max_per_source=max_per_source
                )
                
                # 지정된 소스만 필터링
                return {src: all_news.get(src, []) for src in sources if src in all_news}
            elif len(sources) == 1:
                # 단일 소스에서만 수집
                source = sources[0]
                results = {}
                
                if source == 'naver':
                    loop = asyncio.get_event_loop()
                    results[source] = await loop.run_in_executor(
                        None,
                        lambda: self.news_collector.fetch_naver_news_trending(
                            category=category,
                            max_results=max_per_source
                        )
                    )
                elif source == 'daum':
                    loop = asyncio.get_event_loop()
                    results[source] = await loop.run_in_executor(
                        None,
                        lambda: self.news_collector.fetch_daum_news_trending(
                            category=category,
                            max_results=max_per_source
                        )
                    )
                elif source == 'google':
                    loop = asyncio.get_event_loop()
                    results[source] = await loop.run_in_executor(
                        None,
                        lambda: self.news_collector.fetch_google_news_trending(
                            region='ko-KR',
                            max_results=max_per_source
                        )
                    )
                
                return results
            else:
                return {}
                
        except Exception as e:
            logger.error(f"뉴스 트렌드 수집 오류: {str(e)}")
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
        """
        if not self.portal_collector:
            logger.error("포털 수집기가 초기화되지 않았습니다.")
            return {}
            
        # 기본값: 모든 소스
        if sources is None:
            sources = ['naver', 'daum', 'zum', 'nate']
            
        try:
            if len(sources) > 1:
                # 여러 소스에서 병렬 수집
                all_trends = await self.portal_collector.fetch_all_portal_trending(
                    max_per_source=max_per_source
                )
                
                # 지정된 소스만 필터링
                return {src: all_trends.get(src, []) for src in sources if src in all_trends}
            elif len(sources) == 1:
                # 단일 소스에서만 수집
                source = sources[0]
                results = {}
                
                if source == 'naver':
                    loop = asyncio.get_event_loop()
                    results[source] = await loop.run_in_executor(
                        None,
                        lambda: self.portal_collector.fetch_naver_trending_searches(
                            max_results=max_per_source
                        )
                    )
                elif source == 'daum':
                    loop = asyncio.get_event_loop()
                    results[source] = await loop.run_in_executor(
                        None,
                        lambda: self.portal_collector.fetch_daum_trending_searches(
                            max_results=max_per_source
                        )
                    )
                elif source == 'zum':
                    loop = asyncio.get_event_loop()
                    results[source] = await loop.run_in_executor(
                        None,
                        lambda: self.portal_collector.fetch_zum_trending_searches(
                            max_results=max_per_source
                        )
                    )
                elif source == 'nate':
                    loop = asyncio.get_event_loop()
                    results[source] = await loop.run_in_executor(
                        None,
                        lambda: self.portal_collector.fetch_nate_trending_searches(
                            max_results=max_per_source
                        )
                    )
                
                return results
            else:
                return {}
                
        except Exception as e:
            logger.error(f"포털 인기 검색어 수집 오류: {str(e)}")
            return {}
            
    def collect_google_trends(
        self, 
        country: str = 'south_korea',
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        구글 트렌드 실시간 인기 검색어를 수집합니다.
        
        Args:
            country: 국가 코드 (기본: 'south_korea')
            max_results: 최대 결과 수
            
        Returns:
            실시간 트렌드 목록
        """
        if not self.google_trends_collector:
            logger.error("구글 트렌드 수집기가 초기화되지 않았습니다.")
            return []
            
        try:
            return self.google_trends_collector.fetch_realtime_trends(
                pn=country,
                max_results=max_results
            )
        except Exception as e:
            logger.error(f"구글 트렌드 수집 오류: {str(e)}")
            return []
            
    def collect_keyword_interest(
        self, 
        keywords: List[str],
        timeframe: str = 'now 1-d',
        geo: str = 'KR'
    ) -> Dict[str, Any]:
        """
        특정 키워드들의 검색 관심도를 수집합니다.
        
        Args:
            keywords: 검색할 키워드 목록 (최대 5개)
            timeframe: 시간 범위
            geo: 지역 코드
            
        Returns:
            키워드별 관심도 데이터
        """
        if not self.google_trends_collector:
            logger.error("구글 트렌드 수집기가 초기화되지 않았습니다.")
            return {'error': '구글 트렌드 수집기가 초기화되지 않았습니다.'}
            
        try:
            return self.google_trends_collector.fetch_keyword_interest(
                keywords=keywords,
                timeframe=timeframe,
                geo=geo
            )
        except Exception as e:
            logger.error(f"키워드 관심도 수집 오류: {str(e)}")
            return {'error': str(e)}
    
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
                        'sources': [],
                        'ranks': {},
                        'score': 0
                    }
                
                # 소스 추가
                if source not in keyword_data[keyword]['sources']:
                    keyword_data[keyword]['sources'].append(source)
                
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