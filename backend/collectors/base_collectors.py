from pytrends.request import TrendReq
import pandas as pd
import time
from typing import List, Optional

def fetch_google_trends_daily(keywords: List[str], locale: str='ko', tz: int=540, retries: int=3) -> pd.DataFrame:
    """
    pytrends를 이용해 지정 키워드의 일간 관심도 데이터를 반환합니다.
    
    Args:
        keywords: 검색할 키워드 리스트 (예: ['금리', '코인', ...])
        locale: 언어 설정 (예: 'ko')
        tz: 타임존 (서울은 540)
        retries: 실패 시 재시도 횟수
        
    Returns:
        pandas DataFrame (컬럼: date, 각 키워드, isPartial)
    """
    for attempt in range(retries):
        try:
            pt = TrendReq(hl=locale, tz=tz)
            pt.build_payload(keywords, cat=0, timeframe='now 1-d')
            df = pt.interest_over_time()
            
            if df is None or df.empty:
                print(f"경고: '{keywords}' 키워드에 대한 데이터가 없습니다.")
                return pd.DataFrame()
                
            return df.reset_index()
            
        except Exception as e:
            if attempt < retries - 1:
                print(f"오류 발생: {e}. {attempt+1}번째 재시도 중...")
                time.sleep(2)  # API 제한 방지를 위한 대기
            else:
                print(f"최대 재시도 횟수 초과: {e}")
                return pd.DataFrame()

def fetch_google_trends_hotlist(locale: str='ko', tz: int=540, top_n: int=20, country: str='south_korea') -> List[str]:
    """
    하루 단위 인기 급상승 검색어 목록을 반환합니다.
    
    Args:
        locale: 언어 설정 (예: 'ko')
        tz: 타임존 (서울은 540)
        top_n: 반환할 인기 검색어 수
        country: 국가 코드 (예: 'south_korea')
        
    Returns:
        인기 검색어 리스트
    """
    try:
        pt = TrendReq(hl=locale, tz=tz)
        hot = pt.trending_searches(pn=country)
        
        if hot is None or hot.empty:
            print(f"경고: 인기 검색어 데이터를 가져올 수 없습니다.")
            return []
            
        return hot.head(top_n)[0].tolist()  # Series → list
        
    except Exception as e:
        print(f"인기 검색어 가져오기 실패: {e}")
        return []

def fetch_google_trends_related(keyword: str, locale: str='ko', tz: int=540) -> Optional[dict]:
    """
    특정 키워드와 관련된 검색어 및 주제를 반환합니다.
    
    Args:
        keyword: 검색할 키워드
        locale: 언어 설정 (예: 'ko')
        tz: 타임존 (서울은 540)
        
    Returns:
        관련 검색어 및 주제를 담은 딕셔너리 또는 None
    """
    try:
        pt = TrendReq(hl=locale, tz=tz)
        pt.build_payload([keyword], cat=0, timeframe='now 7-d')
        
        # 관련 검색어
        related_queries = pt.related_queries()
        
        # 관련 주제
        related_topics = pt.related_topics()
        
        if not related_queries or not related_topics:
            print(f"경고: '{keyword}' 키워드에 대한 관련 데이터가 없습니다.")
            return None
            
        return {
            'related_queries': related_queries,
            'related_topics': related_topics
        }
        
    except Exception as e:
        print(f"관련 검색어 및 주제 가져오기 실패: {e}")
        return None 