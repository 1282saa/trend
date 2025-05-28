"""
Google Trends 데이터 수집 모듈
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
from enum import Enum, auto

import pandas as pd
from pytrends.request import TrendReq

from utils.cache import cached

# 로그 설정
logger = logging.getLogger('google_trends_collector')

class TimeFrame(Enum):
    """Google Trends 시간 범위 상수"""
    PAST_HOUR = "now 1-H"
    PAST_4_HOURS = "now 4-H"
    PAST_DAY = "now 1-d"
    PAST_7_DAYS = "now 7-d"
    PAST_MONTH = "today 1-m"
    PAST_3_MONTHS = "today 3-m"
    PAST_12_MONTHS = "today 12-m"
    PAST_5_YEARS = "today 5-y"

class Country(Enum):
    """국가 코드 상수"""
    SOUTH_KOREA = "south_korea"
    UNITED_STATES = "united_states"
    JAPAN = "japan"
    UNITED_KINGDOM = "united_kingdom"
    GERMANY = "germany"

class GoogleTrendsCollector:
    """Google Trends API를 통한 데이터 수집기"""
    
    def __init__(self, 
                 hl: str = 'ko', 
                 tz: int = 540, 
                 cache_ttl: int = 1800, 
                 timeout: int = 30,
                 retries: int = 3,
                 backoff_factor: float = 1.5):
        """
        Google Trends 수집기 초기화
        
        Args:
            hl: 언어 설정 (기본: 한국어)
            tz: 타임존 설정 (기본: 한국 표준시 GMT+9)
            cache_ttl: 캐시 유효 시간(초), 기본 30분
            timeout: 요청 타임아웃(초)
            retries: 요청 재시도 횟수
            backoff_factor: 요청 재시도 시 대기 시간 증가 비율
        """
        self.hl = os.getenv('LOCALE', hl)
        self.tz = int(os.getenv('TIMEZONE', tz))
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        
        # pytrends 클라이언트 초기화
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """pytrends 클라이언트 초기화 및 예외 처리"""
        try:
            self.pytrends = TrendReq(
                hl=self.hl, 
                tz=self.tz,
                timeout=self.timeout,
                retries=self.retries,
                backoff_factor=self.backoff_factor
            )
            logger.info(f"Google Trends 클라이언트 초기화 성공 (언어: {self.hl}, 시간대: {self.tz})")
        except Exception as e:
            logger.warning(f"표준 설정으로 Google Trends 클라이언트 초기화 실패: {str(e)}")
            try:
                # 기본 설정으로 재시도
                self.pytrends = TrendReq()
                logger.info("기본 설정으로 Google Trends 클라이언트 초기화 성공")
            except Exception as e:
                logger.error(f"Google Trends 클라이언트 초기화 실패: {str(e)}")
                self.pytrends = None
                raise RuntimeError(f"Google Trends 클라이언트를 초기화할 수 없습니다: {str(e)}")
    
    @cached(ttl=1800)  # 30분 캐싱
    def fetch_realtime_trends(self, 
                              country: Union[str, Country] = Country.SOUTH_KOREA, 
                              max_results: int = 20) -> List[Dict[str, Any]]:
        """
        실시간 트렌드(인기 검색어)를 가져옵니다.
        
        Args:
            country: 국가/지역 코드 또는 Country 열거형 (기본: 한국)
            max_results: 가져올 최대 결과 수
            
        Returns:
            실시간 트렌드 목록
        
        Raises:
            RuntimeError: pytrends 클라이언트가 초기화되지 않은 경우
        """
        if self.pytrends is None:
            raise RuntimeError("Google Trends 클라이언트가 초기화되지 않았습니다")
            
        # Country 열거형 처리
        country_code = country.value if isinstance(country, Country) else country
        
        try:
            logger.info(f"국가 '{country_code}'의 실시간 트렌드 수집 시작")
            # 국가/지역별 실시간 트렌드 가져오기
            df = self.pytrends.trending_searches(pn=country_code)
            
            if df.empty:
                logger.warning(f"국가 '{country_code}'의 실시간 트렌드 데이터가 비어 있습니다")
                return []
                
            # DataFrame을 리스트로 변환
            trends = []
            for idx, row in df.head(max_results).iterrows():
                keyword = row[0]
                trends.append({
                    'rank': idx + 1,
                    'keyword': keyword,
                    'query': keyword,
                    'country': country_code,
                    'platform': 'google_trends',
                    'collected_at': datetime.now().isoformat()
                })
            
            logger.info(f"국가 '{country_code}'에서 {len(trends)}개의 트렌드 수집 완료")
            return trends
            
        except Exception as e:
            logger.error(f"Google Trends 실시간 트렌드 수집 오류 (국가: {country_code}): {str(e)}")
            return []
    
    @cached(ttl=3600)  # 1시간 캐싱
    def fetch_keyword_interest(self, 
                               keywords: List[str], 
                               timeframe: Union[str, TimeFrame] = TimeFrame.PAST_DAY, 
                               geo: str = 'KR') -> Dict[str, Any]:
        """
        특정 키워드들의 검색 관심도를 가져옵니다.
        
        Args:
            keywords: 검색할 키워드 목록 (최대 5개)
            timeframe: 시간 범위 문자열 또는 TimeFrame 열거형
            geo: 지역 코드 (예: 'KR', 'US')
            
        Returns:
            키워드별 관심도 데이터
            
        Raises:
            ValueError: 키워드가 없거나 너무 많은 경우
            RuntimeError: pytrends 클라이언트가 초기화되지 않은 경우
        """
        if self.pytrends is None:
            raise RuntimeError("Google Trends 클라이언트가 초기화되지 않았습니다")
            
        if not keywords:
            return {'error': '키워드가 필요합니다.'}
            
        # 키워드 수 제한 확인 (Google Trends API 제한)
        if len(keywords) > 5:
            logger.warning(f"키워드는 최대 5개까지만 가능합니다. 처음 5개만 사용합니다: {keywords[:5]}")
            keywords = keywords[:5]
        
        # TimeFrame 열거형 처리
        time_frame_value = timeframe.value if isinstance(timeframe, TimeFrame) else timeframe
        
        try:
            logger.info(f"키워드 관심도 수집 시작: 키워드={keywords}, 기간={time_frame_value}, 지역={geo}")
            
            # 페이로드 빌드
            self.pytrends.build_payload(
                kw_list=keywords,
                cat=0,  # 카테고리 (0 = 전체)
                timeframe=time_frame_value,
                geo=geo
            )
            
            # 각 데이터 요청 및 처리
            result = self._collect_interest_data(keywords, time_frame_value, geo)
            
            logger.info(f"키워드 관심도 수집 완료: {len(keywords)}개 키워드")
            return result
            
        except Exception as e:
            error_msg = f"Google Trends 키워드 관심도 수집 오류: {str(e)}"
            logger.error(error_msg)
            return {'error': error_msg}
    
    def _collect_interest_data(self, 
                               keywords: List[str], 
                               timeframe: str, 
                               geo: str) -> Dict[str, Any]:
        """
        관심도 데이터 수집 및 가공
        
        Args:
            keywords: 검색할 키워드 목록
            timeframe: 시간 범위
            geo: 지역 코드
            
        Returns:
            가공된 관심도 데이터
        """
        # 시간에 따른 관심도
        interest_over_time = self._safe_get_dataframe(
            lambda: self.pytrends.interest_over_time()
        )
        
        # 지역별 관심도
        interest_by_region = self._safe_get_dataframe(
            lambda: self.pytrends.interest_by_region(resolution='COUNTRY', inc_low_vol=True)
        )
        
        # 연관 주제 및 쿼리
        related_topics = self._safe_get_dict(
            lambda: self.pytrends.related_topics()
        )
        
        related_queries = self._safe_get_dict(
            lambda: self.pytrends.related_queries()
        )
        
        # 결과 포맷팅
        return {
            'keywords': keywords,
            'timeframe': timeframe,
            'geo': geo,
            'interest_over_time': interest_over_time.to_dict() if not interest_over_time.empty else {},
            'interest_by_region': interest_by_region.to_dict() if not interest_by_region.empty else {},
            'related_topics': self._process_related_topics(related_topics),
            'related_queries': self._process_related_queries(related_queries),
            'collected_at': datetime.now().isoformat()
        }
    
    def _safe_get_dataframe(self, operation: callable) -> pd.DataFrame:
        """안전하게 DataFrame을 가져오는 헬퍼 메서드"""
        try:
            return operation()
        except Exception as e:
            logger.warning(f"데이터 가져오기 실패: {str(e)}")
            return pd.DataFrame()
            
    def _safe_get_dict(self, operation: callable) -> Dict:
        """안전하게 Dict를 가져오는 헬퍼 메서드"""
        try:
            return operation()
        except Exception as e:
            logger.warning(f"데이터 가져오기 실패: {str(e)}")
            return {}
    
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
    def fetch_trending_topics(self, date: Optional[str] = None, geo: str = 'KR') -> Dict[str, Any]:
        """
        특정 날짜의 인기 주제를 가져옵니다.
        
        Args:
            date: 날짜 (YYYY-MM-DD 형식, None이면 최신)
            geo: 지역 코드 (예: 'KR', 'US')
            
        Returns:
            인기 주제 데이터
            
        Raises:
            RuntimeError: pytrends 클라이언트가 초기화되지 않은 경우
        """
        if self.pytrends is None:
            raise RuntimeError("Google Trends 클라이언트가 초기화되지 않았습니다")
            
        try:
            logger.info(f"인기 주제 수집 시작: 지역={geo}")
            # 인기 주제 가져오기
            daily_trends = self.pytrends.daily_trends(geo=geo)
            
            # 결과 포맷팅
            if daily_trends.empty:
                logger.warning(f"지역 '{geo}'의 인기 주제 데이터가 비어 있습니다")
                return {'error': '인기 주제 데이터가 없습니다.'}
                
            # DataFrame을 리스트로 변환
            trends_data = daily_trends.to_dict(orient='records')
            
            result = {
                'date': date or datetime.now().strftime('%Y-%m-%d'),
                'country': geo,
                'trends': trends_data,
                'collected_at': datetime.now().isoformat()
            }
            
            logger.info(f"인기 주제 수집 완료: {len(trends_data)}개 주제")
            return result
            
        except Exception as e:
            error_msg = f"Google Trends 인기 주제 수집 오류: {str(e)}"
            logger.error(error_msg)
            return {'error': error_msg}
            
    def fetch_interest_by_country(self, 
                                 keyword: str, 
                                 timeframe: Union[str, TimeFrame] = TimeFrame.PAST_12_MONTHS) -> Dict[str, Any]:
        """
        특정 키워드의 국가별 관심도를 가져옵니다.
        
        Args:
            keyword: 검색할 키워드
            timeframe: 시간 범위 문자열 또는 TimeFrame 열거형
            
        Returns:
            국가별 관심도 데이터
            
        Raises:
            ValueError: 키워드가 비어있는 경우
            RuntimeError: pytrends 클라이언트가 초기화되지 않은 경우
        """
        if self.pytrends is None:
            raise RuntimeError("Google Trends 클라이언트가 초기화되지 않았습니다")
            
        if not keyword:
            raise ValueError("키워드는 비어있을 수 없습니다")
            
        # TimeFrame 열거형 처리
        time_frame_value = timeframe.value if isinstance(timeframe, TimeFrame) else timeframe
        
        try:
            logger.info(f"국가별 관심도 수집 시작: 키워드='{keyword}', 기간={time_frame_value}")
            
            # 페이로드 빌드
            self.pytrends.build_payload(
                kw_list=[keyword],
                timeframe=time_frame_value
            )
            
            # 국가별 관심도
            interest_by_region = self.pytrends.interest_by_region(
                resolution='COUNTRY', 
                inc_low_vol=True
            )
            
            # 결과 포맷팅
            if interest_by_region.empty:
                logger.warning(f"키워드 '{keyword}'의 국가별 관심도 데이터가 비어 있습니다")
                return {
                    'keyword': keyword,
                    'timeframe': time_frame_value,
                    'countries': [],
                    'collected_at': datetime.now().isoformat()
                }
            
            # 국가별 관심도를 내림차순으로 정렬
            interest_by_region = interest_by_region.sort_values(
                by=keyword, 
                ascending=False
            )
            
            # 데이터 변환
            countries = [
                {'country': country, 'value': value}
                for country, value in interest_by_region[keyword].items()
            ]
            
            result = {
                'keyword': keyword,
                'timeframe': time_frame_value,
                'countries': countries,
                'collected_at': datetime.now().isoformat()
            }
            
            logger.info(f"국가별 관심도 수집 완료: {len(countries)}개 국가")
            return result
            
        except Exception as e:
            error_msg = f"Google Trends 국가별 관심도 수집 오류: {str(e)}"
            logger.error(error_msg)
            return {'error': error_msg}
            
    def fetch_suggestions(self, keyword: str) -> List[Dict[str, str]]:
        """
        특정 키워드에 대한 검색어 제안을 가져옵니다.
        
        Args:
            keyword: 검색할 키워드
            
        Returns:
            검색어 제안 목록
            
        Raises:
            ValueError: 키워드가 비어있는 경우
            RuntimeError: pytrends 클라이언트가 초기화되지 않은 경우
        """
        if self.pytrends is None:
            raise RuntimeError("Google Trends 클라이언트가 초기화되지 않았습니다")
            
        if not keyword:
            raise ValueError("키워드는 비어있을 수 없습니다")
            
        try:
            logger.info(f"검색어 제안 수집 시작: 키워드='{keyword}'")
            
            # 검색어 제안 가져오기
            suggestions = self.pytrends.suggestions(keyword)
            
            # 불필요한 정보 제거
            for suggestion in suggestions:
                if 'mid' in suggestion:
                    del suggestion['mid']
            
            logger.info(f"검색어 제안 수집 완료: {len(suggestions)}개 제안")
            return suggestions
            
        except Exception as e:
            logger.error(f"Google Trends 검색어 제안 수집 오류: {str(e)}")
            return []
    
    def get_available_categories(self) -> List[Dict[str, str]]:
        """
        사용 가능한 카테고리 목록을 가져옵니다.
        
        Returns:
            카테고리 ID와 이름 목록
            
        Raises:
            RuntimeError: pytrends 클라이언트가 초기화되지 않은 경우
        """
        if self.pytrends is None:
            raise RuntimeError("Google Trends 클라이언트가 초기화되지 않았습니다")
            
        try:
            category_df = pd.DataFrame(self.pytrends.categories())
            
            categories = [
                {'id': row['id'], 'name': row['name']}
                for _, row in category_df.iterrows()
            ]
            
            return categories
        except Exception as e:
            logger.error(f"카테고리 목록 가져오기 실패: {str(e)}")
            return []
    
    def is_available(self) -> bool:
        """Google Trends 클라이언트가 사용 가능한지 확인"""
        return self.pytrends is not None
    
    def health_check(self) -> Tuple[bool, str]:
        """
        수집기의 상태를 확인합니다.
        
        Returns:
            (정상 여부, 상태 메시지) 튜플
        """
        if not self.is_available():
            return False, "Google Trends 클라이언트가 초기화되지 않았습니다"
            
        try:
            # 간단한 요청으로 서비스 가용성 확인
            self.pytrends.trending_searches(pn='united_states')
            return True, "정상"
        except Exception as e:
            return False, f"오류: {str(e)}"