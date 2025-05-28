"""
Google Trends 데이터 수집 모듈
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

import pandas as pd
from pytrends.request import TrendReq

from utils.cache import cached, memory_cache, file_cache

# 로그 설정
logger = logging.getLogger('google_trends_collector')

class GoogleTrendsCollector:
    """Google Trends API를 통한 데이터 수집기"""
    
    def __init__(self, hl: str = 'ko', tz: int = 540, cache_ttl: int = 1800, timeout: int = 30):
        """
        Google Trends 수집기 초기화
        
        Args:
            hl: 언어 설정 (기본: 한국어)
            tz: 타임존 설정 (기본: 한국 표준시 GMT+9)
            cache_ttl: 캐시 유효 시간(초), 기본 30분
            timeout: 요청 타임아웃(초)
        """
        self.hl = hl
        self.tz = tz
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        
        # 환경 변수에서 설정 가져오기
        self.hl = os.getenv('LOCALE', self.hl)
        self.tz = int(os.getenv('TIMEZONE', self.tz))
        
        # pytrends 클라이언트 초기화
        self.pytrends = TrendReq(
            hl=self.hl, 
            tz=self.tz,
            timeout=self.timeout,
            retries=3,
            backoff_factor=1.5
        )
    
    @cached(ttl=1800)  # 30분 캐싱
    def fetch_realtime_trends(self, pn: str = 'south_korea', max_results: int = 20) -> List[Dict[str, Any]]:
        """
        실시간 트렌드(인기 검색어)를 가져옵니다.
        
        Args:
            pn: 국가/지역 코드 (기본: 'south_korea')
            max_results: 가져올 최대 결과 수
            
        Returns:
            실시간 트렌드 목록
        """
        try:
            # 국가/지역별 실시간 트렌드 가져오기
            df = self.pytrends.trending_searches(pn=pn)
            
            # DataFrame을 리스트로 변환
            trends = []
            for idx, row in df.head(max_results).iterrows():
                keyword = row[0]
                trends.append({
                    'rank': idx + 1,
                    'keyword': keyword,
                    'query': keyword,
                    'country': pn,
                    'platform': 'google_trends',
                    'collected_at': datetime.now().isoformat()
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"Google Trends 실시간 트렌드 수집 오류: {str(e)}")
            return []
    
    @cached(ttl=3600)  # 1시간 캐싱
    def fetch_keyword_interest(self, keywords: List[str], timeframe: str = 'now 1-d', geo: str = 'KR') -> Dict[str, Any]:
        """
        특정 키워드들의 검색 관심도를 가져옵니다.
        
        Args:
            keywords: 검색할 키워드 목록 (최대 5개)
            timeframe: 시간 범위 ('now X-H', 'today X-m', 'now 4-H' 등)
            geo: 지역 코드 (예: 'KR', 'US')
            
        Returns:
            키워드별 관심도 데이터
        """
        if not keywords:
            return {'error': '키워드가 필요합니다.'}
            
        if len(keywords) > 5:
            logger.warning(f"키워드는 최대 5개까지만 가능합니다. 처음 5개만 사용합니다: {keywords[:5]}")
            keywords = keywords[:5]
        
        try:
            # 페이로드 빌드
            self.pytrends.build_payload(
                kw_list=keywords,
                cat=0,  # 카테고리 (0 = 전체)
                timeframe=timeframe,
                geo=geo
            )
            
            # 시간에 따른 관심도
            interest_over_time = self.pytrends.interest_over_time()
            if interest_over_time.empty:
                interest_over_time_data = {}
            else:
                interest_over_time_data = interest_over_time.to_dict()
            
            # 지역별 관심도
            interest_by_region = self.pytrends.interest_by_region(resolution='COUNTRY', inc_low_vol=True)
            if interest_by_region.empty:
                interest_by_region_data = {}
            else:
                interest_by_region_data = interest_by_region.to_dict()
            
            # 연관 주제 및 쿼리
            related_topics = self.pytrends.related_topics()
            related_queries = self.pytrends.related_queries()
            
            # 결과 포맷팅
            result = {
                'keywords': keywords,
                'timeframe': timeframe,
                'geo': geo,
                'interest_over_time': interest_over_time_data,
                'interest_by_region': interest_by_region_data,
                'related_topics': self._process_related_topics(related_topics),
                'related_queries': self._process_related_queries(related_queries),
                'collected_at': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Google Trends 키워드 관심도 수집 오류: {str(e)}")
            return {'error': str(e)}
    
    def _process_related_topics(self, related_topics: Dict) -> Dict:
        """연관 주제 데이터 처리"""
        result = {}
        
        for keyword, data in related_topics.items():
            result[keyword] = {}
            
            for topic_type, df in data.items():
                if df is not None and not df.empty:
                    result[keyword][topic_type] = df.to_dict(orient='records')
                else:
                    result[keyword][topic_type] = []
        
        return result
    
    def _process_related_queries(self, related_queries: Dict) -> Dict:
        """연관 쿼리 데이터 처리"""
        result = {}
        
        for keyword, data in related_queries.items():
            result[keyword] = {}
            
            for query_type, df in data.items():
                if df is not None and not df.empty:
                    result[keyword][query_type] = df.to_dict(orient='records')
                else:
                    result[keyword][query_type] = []
        
        return result
    
    @cached(ttl=86400)  # 24시간 캐싱
    def fetch_trending_topics(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        특정 날짜의 인기 주제를 가져옵니다.
        
        Args:
            date: 날짜 (YYYY-MM-DD 형식, None이면 최신)
            
        Returns:
            인기 주제 데이터
        """
        try:
            # 인기 주제 가져오기
            daily_trends = self.pytrends.daily_trends(geo='KR')
            
            # 결과 포맷팅
            if daily_trends.empty:
                return {'error': '인기 주제 데이터가 없습니다.'}
                
            # DataFrame을 리스트로 변환
            trends_data = daily_trends.to_dict(orient='records')
            
            result = {
                'date': date or datetime.now().strftime('%Y-%m-%d'),
                'country': 'KR',
                'trends': trends_data,
                'collected_at': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Google Trends 인기 주제 수집 오류: {str(e)}")
            return {'error': str(e)}
            
    def fetch_interest_by_country(
        self, 
        keyword: str, 
        timeframe: str = 'today 12-m'
    ) -> Dict[str, Any]:
        """
        특정 키워드의 국가별 관심도를 가져옵니다.
        
        Args:
            keyword: 검색할 키워드
            timeframe: 시간 범위
            
        Returns:
            국가별 관심도 데이터
        """
        try:
            # 페이로드 빌드
            self.pytrends.build_payload(
                kw_list=[keyword],
                timeframe=timeframe
            )
            
            # 국가별 관심도
            interest_by_region = self.pytrends.interest_by_region(
                resolution='COUNTRY', 
                inc_low_vol=True
            )
            
            # 결과 포맷팅
            if interest_by_region.empty:
                return {
                    'keyword': keyword,
                    'timeframe': timeframe,
                    'countries': [],
                    'collected_at': datetime.now().isoformat()
                }
            
            # 국가별 관심도를 내림차순으로 정렬
            interest_by_region = interest_by_region.sort_values(
                by=keyword, 
                ascending=False
            )
            
            # 데이터 변환
            countries = []
            for country, value in interest_by_region[keyword].items():
                countries.append({
                    'country': country,
                    'value': value
                })
            
            return {
                'keyword': keyword,
                'timeframe': timeframe,
                'countries': countries,
                'collected_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Google Trends 국가별 관심도 수집 오류: {str(e)}")
            return {'error': str(e)}
            
    def fetch_suggestions(self, keyword: str) -> List[Dict[str, str]]:
        """
        특정 키워드에 대한 검색어 제안을 가져옵니다.
        
        Args:
            keyword: 검색할 키워드
            
        Returns:
            검색어 제안 목록
        """
        try:
            # 검색어 제안 가져오기
            suggestions = self.pytrends.suggestions(keyword)
            
            # 불필요한 정보 제거
            for suggestion in suggestions:
                if 'mid' in suggestion:
                    del suggestion['mid']
                    
            return suggestions
            
        except Exception as e:
            logger.error(f"Google Trends 검색어 제안 수집 오류: {str(e)}")
            return [] 