"""
포털사이트 인기 검색어 수집 모듈
"""
import os
import re
import json
import logging
import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple

import requests
from bs4 import BeautifulSoup

from utils.http_client import HttpClient
from utils.cache import cached, async_cached, memory_cache, file_cache
from utils.browser import BrowserManager

# 로그 설정
logger = logging.getLogger('portal_collector')

class PortalCollector:
    """
    포털사이트 인기 검색어 수집기 클래스
    - 네이버, 다음, 줌 등의 인기 검색어 수집
    - 웹 스크래핑 방식으로 데이터 수집
    """
    
    def __init__(self, cache_ttl: int = 300):
        """
        포털 수집기 초기화
        
        Args:
            cache_ttl: 캐시 유효 시간(초), 기본 5분
        """
        self.http_client = HttpClient(max_retries=3, retry_delay=1.0, timeout=10.0)
        self.browser_manager = BrowserManager(headless=True)
        self.cache_ttl = cache_ttl
    
    @cached(ttl=300)  # 5분 캐싱
    def fetch_naver_trending_searches(
        self, 
        max_results: int = 20,
        age_group: Optional[str] = None,
        gender: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        네이버 실시간 급상승 검색어를 수집합니다.
        
        Args:
            max_results: 수집할 최대 검색어 수
            age_group: 연령대 필터 ('10', '20', '30', '40', '50', '60')
            gender: 성별 필터 ('m', 'f')
            
        Returns:
            인기 검색어 정보 목록
        """
        url = "https://api.signal.bz/news/realtime"
        params = {}
        
        if age_group:
            params['category'] = f'age_{age_group}'
        if gender:
            params['category'] = f'gender_{gender.lower()}'
            
        try:
            response = self.http_client.get(url, params=params)
            data = response.json()
            
            # 결과 처리
            trending = []
            for idx, item in enumerate(data.get('top20', [])[:max_results], 1):
                trending.append({
                    'rank': idx,
                    'keyword': item.get('keyword', ''),
                    'query': item.get('keyword', ''),  # 검색 쿼리용
                    'count': item.get('search_count', 0),
                    'delta': item.get('rank_change', 0),  # 순위 변동
                    'platform': 'naver',
                    'age_group': age_group,
                    'gender': gender,
                    'collected_at': datetime.now().isoformat()
                })
                
            return trending
            
        except Exception as e:
            logger.error(f"네이버 인기 검색어 API 오류: {str(e)}")
            # API 실패 시 스크래핑으로 대체
            return self._fetch_naver_trending_searches_scrape(max_results)
    
    def _fetch_naver_trending_searches_scrape(self, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        네이버 실시간 급상승 검색어 페이지 스크래핑 (API 실패 시 대체)
        
        Args:
            max_results: 수집할 최대 검색어 수
            
        Returns:
            인기 검색어 정보 목록
        """
        url = "https://datalab.naver.com/keyword/realtimeList.naver"
        
        trending = []
        
        with self.browser_manager.create_driver() as driver:
            try:
                # 네이버 데이터랩 페이지 로드
                driver.get(url)
                
                # 페이지 로드 대기
                time.sleep(2)
                
                # 실시간 검색어 요소 가져오기
                items = driver.find_elements(By.CSS_SELECTOR, ".item_box")
                
                for idx, item in enumerate(items[:max_results], 1):
                    try:
                        # 키워드 텍스트
                        keyword_el = item.find_element(By.CSS_SELECTOR, ".item_title")
                        keyword = keyword_el.text.strip()
                        
                        # 순위 변동 (있을 경우)
                        try:
                            change_el = item.find_element(By.CSS_SELECTOR, ".item_change")
                            change_text = change_el.text.strip()
                            # 상승: ▲2, 하락: ▼3, 유지: -
                            if '▲' in change_text:
                                delta = int(change_text.replace('▲', ''))
                            elif '▼' in change_text:
                                delta = -int(change_text.replace('▼', ''))
                            else:
                                delta = 0
                        except:
                            delta = 0
                            
                        trending.append({
                            'rank': idx,
                            'keyword': keyword,
                            'query': keyword,
                            'delta': delta,
                            'platform': 'naver_scrape',
                            'collected_at': datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.warning(f"네이버 인기 검색어 항목 파싱 오류: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"네이버 인기 검색어 스크래핑 오류: {str(e)}")
                
        return trending
    
    @cached(ttl=300)  # 5분 캐싱
    def fetch_daum_trending_searches(self, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        다음 실시간 급상승 검색어를 수집합니다.
        
        Args:
            max_results: 수집할 최대 검색어 수
            
        Returns:
            인기 검색어 정보 목록
        """
        url = "https://www.daum.net/"
        
        try:
            # 다음 메인 페이지 요청
            response = self.http_client.get(url)
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 실시간 검색어 추출 (CSS 선택자는 페이지 구조에 따라 변경 필요)
            trending = []
            for idx, item in enumerate(soup.select('.list_mini .rank_cont')[:max_results], 1):
                try:
                    # 키워드와 링크
                    keyword_el = item.select_one('.link_issue')
                    if not keyword_el:
                        continue
                        
                    keyword = keyword_el.text.strip()
                    link = keyword_el.get('href', '')
                    
                    # 순위 변동 (있을 경우)
                    change_el = item.select_one('.rank_result .rank_result_num')
                    
                    if change_el:
                        change_text = change_el.text.strip()
                        direction = item.select_one('.rank_result .ico_pctop, .rank_result .ico_pcdown')
                        direction_class = direction.get('class')[0] if direction else None
                        
                        if direction_class == 'ico_pctop':
                            delta = int(change_text)
                        elif direction_class == 'ico_pcdown':
                            delta = -int(change_text)
                        else:
                            delta = 0
                    else:
                        delta = 0
                    
                    trending.append({
                        'rank': idx,
                        'keyword': keyword,
                        'query': keyword,
                        'link': link,
                        'delta': delta,
                        'platform': 'daum',
                        'collected_at': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"다음 인기 검색어 항목 파싱 오류: {str(e)}")
                    continue
            
            return trending
                
        except Exception as e:
            logger.error(f"다음 인기 검색어 수집 오류: {str(e)}")
            return []
    
    @cached(ttl=300)  # 5분 캐싱
    def fetch_zum_trending_searches(self, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        줌 실시간 급상승 검색어를 수집합니다.
        
        Args:
            max_results: 수집할 최대 검색어 수
            
        Returns:
            인기 검색어 정보 목록
        """
        url = "https://m.search.zum.com/search.zum?method=uni&option=accu&qm=f_typing.top"
        
        try:
            # 줌 모바일 검색 페이지 요청 (API 대체)
            response = self.http_client.get(url)
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 실시간 검색어 추출
            trending = []
            for idx, item in enumerate(soup.select('.list_of_issue li')[:max_results], 1):
                try:
                    # 키워드
                    keyword_el = item.select_one('a strong')
                    if not keyword_el:
                        continue
                        
                    keyword = keyword_el.text.strip()
                    link = item.select_one('a').get('href', '') if item.select_one('a') else ''
                    
                    # 순위 변동 (있을 경우)
                    change_el = item.select_one('.rate')
                    delta = 0
                    
                    if change_el:
                        change_text = change_el.text.strip()
                        # 'new', '상승 1', '하락 2', '유지'
                        if '상승' in change_text:
                            delta = int(re.search(r'(\d+)', change_text).group(1))
                        elif '하락' in change_text:
                            delta = -int(re.search(r'(\d+)', change_text).group(1))
                    
                    trending.append({
                        'rank': idx,
                        'keyword': keyword,
                        'query': keyword,
                        'link': link,
                        'delta': delta,
                        'platform': 'zum',
                        'is_new': 'new' in (change_el.text.strip() if change_el else ''),
                        'collected_at': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"줌 인기 검색어 항목 파싱 오류: {str(e)}")
                    continue
            
            return trending
                
        except Exception as e:
            logger.error(f"줌 인기 검색어 수집 오류: {str(e)}")
            return []
    
    @cached(ttl=300)  # 5분 캐싱
    def fetch_google_trending_searches(
        self,
        max_results: int = 20,
        country: str = 'KR'
    ) -> List[Dict[str, Any]]:
        """
        Google 트렌드에서 인기 검색어를 수집합니다.
        
        Args:
            max_results: 수집할 최대 검색어 수
            country: 국가 코드 (예: 'KR', 'US')
            
        Returns:
            인기 검색어 정보 목록
        """
        # Google Trends 일일 트렌드 페이지
        url = f"https://trends.google.com/trends/trendingsearches/daily?geo={country}&hl=ko"
        
        trending = []
        with self.browser_manager.create_driver() as driver:
            try:
                # 페이지 로드
                driver.get(url)
                
                # 페이지 로드 대기
                time.sleep(5)
                
                # 트렌드 아이템 추출
                items = driver.find_elements(By.CSS_SELECTOR, ".feed-item")
                
                for idx, item in enumerate(items[:max_results], 1):
                    try:
                        # 검색어
                        keyword_el = item.find_element(By.CSS_SELECTOR, ".title a")
                        keyword = keyword_el.text.strip()
                        link = keyword_el.get_attribute('href')
                        
                        # 검색량
                        count_el = item.find_element(By.CSS_SELECTOR, ".search-count-title")
                        count_text = count_el.text.strip()  # "1M+ 검색" 형식
                        count_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([KkMm])?', count_text)
                        
                        if count_match:
                            count_num = float(count_match.group(1))
                            count_unit = count_match.group(2)
                            
                            if count_unit and count_unit.upper() == 'K':
                                count = int(count_num * 1000)
                            elif count_unit and count_unit.upper() == 'M':
                                count = int(count_num * 1000000)
                            else:
                                count = int(count_num)
                        else:
                            count = 0
                        
                        # 관련 기사 (있을 경우)
                        related_articles = []
                        try:
                            article_els = item.find_elements(By.CSS_SELECTOR, ".article")
                            for article_el in article_els:
                                article_title = article_el.find_element(By.CSS_SELECTOR, ".article-title").text.strip()
                                article_source = article_el.find_element(By.CSS_SELECTOR, ".source-and-time").text.strip()
                                article_link = article_el.find_element(By.CSS_SELECTOR, "a").get_attribute('href')
                                
                                related_articles.append({
                                    'title': article_title,
                                    'source': article_source,
                                    'link': article_link
                                })
                        except:
                            pass
                        
                        trending.append({
                            'rank': idx,
                            'keyword': keyword,
                            'query': keyword,
                            'link': link,
                            'search_count': count,
                            'related_articles': related_articles,
                            'platform': 'google_trends',
                            'country': country,
                            'collected_at': datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.warning(f"구글 인기 검색어 항목 파싱 오류: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"구글 인기 검색어 수집 오류: {str(e)}")
                
        return trending
    
    @cached(ttl=300)  # 5분 캐싱
    def fetch_nate_trending_searches(self, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        네이트 실시간 급상승 검색어를 수집합니다.
        
        Args:
            max_results: 수집할 최대 검색어 수
            
        Returns:
            인기 검색어 정보 목록
        """
        url = "https://www.nate.com/"
        
        try:
            # 네이트 메인 페이지 요청
            response = self.http_client.get(url)
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 실시간 검색어 추출
            trending = []
            for idx, item in enumerate(soup.select('.kwd_list li')[:max_results], 1):
                try:
                    # 키워드와 링크
                    keyword_el = item.select_one('a.kwd')
                    if not keyword_el:
                        continue
                        
                    keyword = keyword_el.text.strip()
                    link = keyword_el.get('href', '')
                    link = urljoin(url, link) if link else ''
                    
                    # 순위 변동 (있을 경우)
                    delta = 0
                    change_el = item.select_one('.kwd_status')
                    
                    if change_el:
                        # 클래스로 상태 확인
                        if 'up' in change_el.get('class', []):
                            # 숫자 추출
                            delta_text = change_el.text.strip()
                            delta = int(delta_text) if delta_text.isdigit() else 1
                        elif 'down' in change_el.get('class', []):
                            delta_text = change_el.text.strip()
                            delta = -int(delta_text) if delta_text.isdigit() else -1
                    
                    # 신규 여부
                    is_new = 'new' in item.get('class', [])
                    
                    trending.append({
                        'rank': idx,
                        'keyword': keyword,
                        'query': keyword,
                        'link': link,
                        'delta': delta,
                        'is_new': is_new,
                        'platform': 'nate',
                        'collected_at': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"네이트 인기 검색어 항목 파싱 오류: {str(e)}")
                    continue
            
            return trending
                
        except Exception as e:
            logger.error(f"네이트 인기 검색어 수집 오류: {str(e)}")
            return []
    
    async def fetch_all_portal_trending(self, max_per_source: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """
        모든 포털에서 인기 검색어를 비동기적으로 수집합니다.
        
        Args:
            max_per_source: 소스별 최대 결과 수
            
        Returns:
            소스별 인기 검색어 정보를 담은 딕셔너리
        """
        results = {}
        
        # 비동기 작업 생성
        async def fetch_naver():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.fetch_naver_trending_searches(max_per_source)
            )
            return result
            
        async def fetch_daum():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.fetch_daum_trending_searches(max_per_source)
            )
            return result
            
        async def fetch_zum():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.fetch_zum_trending_searches(max_per_source)
            )
            return result
            
        async def fetch_nate():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.fetch_nate_trending_searches(max_per_source)
            )
            return result
            
        # 모든 작업 실행
        naver_task = asyncio.create_task(fetch_naver())
        daum_task = asyncio.create_task(fetch_daum())
        zum_task = asyncio.create_task(fetch_zum())
        nate_task = asyncio.create_task(fetch_nate())
        
        # 결과 수집
        results['naver'] = await naver_task
        results['daum'] = await daum_task
        results['zum'] = await zum_task
        results['nate'] = await nate_task
        
        return results 