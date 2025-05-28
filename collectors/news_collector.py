"""
뉴스 포털에서 인기 기사를 수집하는 모듈
"""
import os
import re
import json
import logging
import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from utils.http_client import HttpClient
from utils.cache import cached, async_cached, memory_cache, file_cache
from utils.browser import BrowserManager

# 로그 설정
logger = logging.getLogger('news_collector')

class NewsCollector:
    """
    뉴스 인기 기사 수집기 클래스
    - 네이버, 다음, 구글 뉴스 등에서 인기 기사 수집
    - 웹 스크래핑 및 API를 통한 수집
    """
    
    def __init__(self, cache_ttl: int = 900):
        """
        뉴스 수집기 초기화
        
        Args:
            cache_ttl: 캐시 유효 시간(초), 기본 15분
        """
        self.http_client = HttpClient(max_retries=3, retry_delay=1.0, timeout=10.0)
        self.browser_manager = BrowserManager(headless=True)
        self.cache_ttl = cache_ttl
        
        # 네이버 API 키 (있을 경우)
        self.naver_client_id = os.getenv('NAVER_CLIENT_ID')
        self.naver_client_secret = os.getenv('NAVER_CLIENT_SECRET')
    
    @cached(ttl=900)  # 15분 캐싱
    def fetch_naver_news_trending(
        self, 
        category: Optional[str] = None, 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        네이버 뉴스 인기 기사를 수집합니다.
        
        Args:
            category: 뉴스 카테고리 (None, 'politics', 'economy', 'society', 'life', 'world', 'it')
            max_results: 수집할 최대 기사 수
            
        Returns:
            인기 뉴스 기사 정보 목록
        """
        # 카테고리별 URL 매핑
        category_urls = {
            None: 'https://news.naver.com/main/ranking/popularDay.naver',  # 전체
            'politics': 'https://news.naver.com/main/ranking/popularDay.naver?rankingType=popular_day&sectionId=100',  # 정치
            'economy': 'https://news.naver.com/main/ranking/popularDay.naver?rankingType=popular_day&sectionId=101',  # 경제
            'society': 'https://news.naver.com/main/ranking/popularDay.naver?rankingType=popular_day&sectionId=102',  # 사회
            'life': 'https://news.naver.com/main/ranking/popularDay.naver?rankingType=popular_day&sectionId=103',     # 생활/문화
            'world': 'https://news.naver.com/main/ranking/popularDay.naver?rankingType=popular_day&sectionId=104',    # 세계
            'it': 'https://news.naver.com/main/ranking/popularDay.naver?rankingType=popular_day&sectionId=105',       # IT/과학
        }
        
        # 요청 URL 결정
        url = category_urls.get(category)
        if not url:
            logger.warning(f"지원하지 않는 카테고리: {category}, 전체 카테고리로 대체합니다.")
            url = category_urls[None]
        
        try:
            # 네이버 뉴스 랭킹 페이지 요청
            response = self.http_client.get(url)
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 인기 뉴스 추출 (CSS 선택자는 페이지 구조에 따라 변경 필요)
            news_items = []
            for item in soup.select('.rankingnews_box')[:max_results]:
                try:
                    # 기사 제목과 링크
                    title_el = item.select_one('.list_title')
                    if not title_el:
                        continue
                        
                    title = title_el.text.strip()
                    link = title_el.get('href', '')
                    link = urljoin(url, link) if link else ''
                    
                    # 언론사
                    press = item.select_one('.list_press')
                    press_name = press.text.strip() if press else ''
                    
                    # 요약 또는 설명
                    desc_el = item.select_one('.list_lead')
                    description = desc_el.text.strip() if desc_el else ''
                    
                    # 썸네일
                    thumbnail_el = item.select_one('.list_img img')
                    thumbnail = thumbnail_el.get('src', '') if thumbnail_el else ''
                    
                    # 시간
                    time_el = item.select_one('.list_time')
                    pub_time = time_el.text.strip() if time_el else ''
                    
                    news_items.append({
                        'title': title,
                        'link': link,
                        'source': press_name,
                        'description': description,
                        'thumbnail': thumbnail,
                        'published_time': pub_time,
                        'category': category or '전체',
                        'platform': 'naver',
                        'collected_at': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"네이버 뉴스 항목 파싱 오류: {str(e)}")
                    continue
            
            return news_items[:max_results]
                
        except Exception as e:
            logger.error(f"네이버 뉴스 수집 오류: {str(e)}")
            return []
    
    @cached(ttl=900)  # 15분 캐싱
    def fetch_daum_news_trending(
        self, 
        category: Optional[str] = None, 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        다음 뉴스 인기 기사를 수집합니다.
        
        Args:
            category: 뉴스 카테고리 (None, 'society', 'politics', 'economic', 'foreign', 'culture', 'digital')
            max_results: 수집할 최대 기사 수
            
        Returns:
            인기 뉴스 기사 정보 목록
        """
        # 카테고리별 URL 매핑
        category_urls = {
            None: 'https://news.daum.net/ranking/popular',  # 전체
            'society': 'https://news.daum.net/ranking/popular/society',  # 사회
            'politics': 'https://news.daum.net/ranking/popular/politics',  # 정치
            'economic': 'https://news.daum.net/ranking/popular/economic',  # 경제
            'foreign': 'https://news.daum.net/ranking/popular/foreign',    # 국제
            'culture': 'https://news.daum.net/ranking/popular/culture',    # 문화
            'digital': 'https://news.daum.net/ranking/popular/digital',    # IT
        }
        
        # 요청 URL 결정
        url = category_urls.get(category)
        if not url:
            logger.warning(f"지원하지 않는 카테고리: {category}, 전체 카테고리로 대체합니다.")
            url = category_urls[None]
        
        try:
            # 다음 뉴스 랭킹 페이지 요청
            response = self.http_client.get(url)
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 인기 뉴스 추출 (CSS 선택자는 페이지 구조에 따라 변경 필요)
            news_items = []
            for item in soup.select('.list_news2 li')[:max_results]:
                try:
                    # 기사 제목과 링크
                    title_el = item.select_one('.tit_thumb a')
                    if not title_el:
                        continue
                        
                    title = title_el.text.strip()
                    link = title_el.get('href', '')
                    
                    # 언론사
                    press_el = item.select_one('.info_news')
                    press_name = press_el.text.strip() if press_el else ''
                    
                    # 썸네일
                    thumbnail_el = item.select_one('.thumb_g img')
                    thumbnail = thumbnail_el.get('src', '') if thumbnail_el else ''
                    
                    # 설명/요약 (있을 경우)
                    desc_el = item.select_one('.desc_thumb')
                    description = desc_el.text.strip() if desc_el else ''
                    
                    news_items.append({
                        'title': title,
                        'link': link,
                        'source': press_name,
                        'description': description,
                        'thumbnail': thumbnail,
                        'category': category or '전체',
                        'platform': 'daum',
                        'collected_at': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"다음 뉴스 항목 파싱 오류: {str(e)}")
                    continue
            
            return news_items[:max_results]
                
        except Exception as e:
            logger.error(f"다음 뉴스 수집 오류: {str(e)}")
            return []

    @cached(ttl=900)  # 15분 캐싱
    def fetch_google_news_trending(
        self, 
        region: str = 'ko-KR', 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        구글 뉴스 인기 기사를 수집합니다.
        
        Args:
            region: 지역 코드 (예: 'ko-KR', 'en-US')
            max_results: 수집할 최대 기사 수
            
        Returns:
            인기 뉴스 기사 정보 목록
        """
        # 구글 뉴스는 JavaScript 렌더링이 필요하므로 Selenium 사용
        url = f"https://news.google.com/?hl={region}"
        
        news_items = []
        with self.browser_manager.create_driver() as driver:
            try:
                # 구글 뉴스 페이지 로드
                driver.get(url)
                
                # 페이지 로드 대기
                time.sleep(3)
                
                # 스크롤하여 더 많은 기사 로드
                self.browser_manager.scroll_down(
                    driver, 
                    scroll_pause=1.0,
                    max_scrolls=3
                )
                
                # 뉴스 기사 추출
                articles = driver.find_elements(By.CSS_SELECTOR, 'article')
                
                for article in articles[:max_results]:
                    try:
                        # 기사 제목과 링크
                        title_el = article.find_element(By.CSS_SELECTOR, 'h3 a')
                        title = title_el.text.strip()
                        # 구글 뉴스는 클릭 시 리다이렉트하는 URL 사용
                        link = title_el.get_attribute('href')
                        
                        # 언론사
                        source_el = article.find_element(By.CSS_SELECTOR, 'div[data-n-tid]')
                        source = source_el.text.strip() if source_el else ''
                        
                        # 시간
                        time_el = article.find_element(By.CSS_SELECTOR, 'time')
                        pub_time = time_el.text.strip() if time_el else ''
                        pub_datetime = time_el.get_attribute('datetime') if time_el else ''
                        
                        # 이미지
                        img_el = article.find_element(By.CSS_SELECTOR, 'img')
                        img_url = img_el.get_attribute('src') if img_el else ''
                        
                        # 설명 (존재할 경우)
                        desc_el = None
                        try:
                            desc_el = article.find_element(By.CSS_SELECTOR, 'h4')
                        except:
                            pass
                            
                        description = desc_el.text.strip() if desc_el else ''
                        
                        news_items.append({
                            'title': title,
                            'link': link,
                            'source': source,
                            'description': description,
                            'thumbnail': img_url,
                            'published_time': pub_time,
                            'published_datetime': pub_datetime,
                            'platform': 'google',
                            'collected_at': datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.warning(f"구글 뉴스 항목 파싱 오류: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"구글 뉴스 수집 오류: {str(e)}")
        
        return news_items[:max_results]
    
    @cached(ttl=1800)  # 30분 캐싱
    def fetch_naver_news_by_keyword(
        self, 
        keyword: str, 
        sort: str = 'sim', 
        max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """
        네이버 뉴스 검색 API를 사용하여 특정 키워드의 뉴스를 검색합니다.
        (네이버 API 키가 있는 경우)
        
        Args:
            keyword: 검색 키워드
            sort: 정렬 방식 ('sim': 정확도, 'date': 날짜)
            max_results: 최대 결과 수
            
        Returns:
            뉴스 기사 정보 목록
        """
        if not self.naver_client_id or not self.naver_client_secret:
            logger.warning("네이버 API 키가 설정되지 않아 웹 스크래핑으로 대체합니다.")
            return self._fetch_naver_news_by_keyword_scrape(keyword, sort, max_results)
            
        # 네이버 검색 API 사용
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret
        }
        params = {
            "query": keyword,
            "sort": sort,
            "display": min(100, max_results),  # 최대 100개
            "start": 1
        }
        
        try:
            response = self.http_client.get(url, params=params, headers=headers)
            data = response.json()
            
            # 결과 처리
            news_items = []
            for item in data.get('items', []):
                # HTML 태그 제거
                title = re.sub('<[^<]+?>', '', item.get('title', '')).strip()
                description = re.sub('<[^<]+?>', '', item.get('description', '')).strip()
                
                news_items.append({
                    'title': title,
                    'link': item.get('link', ''),
                    'source': item.get('pubDate', ''),
                    'description': description,
                    'published_time': item.get('pubDate', ''),
                    'category': '검색',
                    'keyword': keyword,
                    'platform': 'naver_api',
                    'collected_at': datetime.now().isoformat()
                })
            
            return news_items[:max_results]
                
        except Exception as e:
            logger.error(f"네이버 뉴스 API 오류: {str(e)}")
            # API 실패 시 스크래핑으로 대체
            return self._fetch_naver_news_by_keyword_scrape(keyword, sort, max_results)
    
    def _fetch_naver_news_by_keyword_scrape(
        self, 
        keyword: str, 
        sort: str = 'sim', 
        max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """
        네이버 뉴스 검색 페이지 스크래핑을 통해 특정 키워드의 뉴스를 검색합니다.
        (API 키가 없는 경우 또는 API 호출 실패 시 사용)
        
        Args:
            keyword: 검색 키워드
            sort: 정렬 방식 ('sim': 정확도, 'date': 날짜)
            max_results: 최대 결과 수
            
        Returns:
            뉴스 기사 정보 목록
        """
        # 정렬 방식 매핑
        sort_param = 'so:r' if sort == 'sim' else 'so:dd'
        
        # 검색 URL
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&{sort_param}"
        
        news_items = []
        try:
            # 검색 결과 페이지 요청
            response = self.http_client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 뉴스 아이템 추출 (CSS 선택자는 페이지 구조에 따라 변경 필요)
            for item in soup.select('.list_news .bx')[:max_results]:
                try:
                    # 기사 제목과 링크
                    title_el = item.select_one('.news_tit')
                    if not title_el:
                        continue
                        
                    title = title_el.text.strip()
                    link = title_el.get('href', '')
                    
                    # 언론사
                    press_el = item.select_one('.info.press')
                    press_name = press_el.text.strip() if press_el else ''
                    
                    # 요약
                    desc_el = item.select_one('.news_dsc')
                    description = desc_el.text.strip() if desc_el else ''
                    
                    # 시간
                    time_el = item.select_one('.info.time')
                    pub_time = time_el.text.strip() if time_el else ''
                    
                    # 썸네일
                    thumb_el = item.select_one('img')
                    thumbnail = thumb_el.get('src', '') if thumb_el else ''
                    
                    news_items.append({
                        'title': title,
                        'link': link,
                        'source': press_name,
                        'description': description,
                        'thumbnail': thumbnail,
                        'published_time': pub_time,
                        'category': '검색',
                        'keyword': keyword,
                        'platform': 'naver_scrape',
                        'collected_at': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"네이버 뉴스 항목 파싱 오류: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"네이버 뉴스 스크래핑 오류: {str(e)}")
            
        return news_items[:max_results]
    
    async def fetch_all_news_trending(
        self, 
        category: Optional[str] = None, 
        max_per_source: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        모든 뉴스 소스에서 인기 기사를 비동기적으로 수집합니다.
        
        Args:
            category: 뉴스 카테고리 (지원되는 경우)
            max_per_source: 소스별 최대 결과 수
            
        Returns:
            소스별 뉴스 기사 정보를 담은 딕셔너리
        """
        results = {}
        
        # 비동기 작업 생성
        async def fetch_naver():
            # 동기 함수를 비동기 컨텍스트에서 실행
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.fetch_naver_news_trending(category, max_per_source)
            )
            return result
            
        async def fetch_daum():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.fetch_daum_news_trending(category, max_per_source)
            )
            return result
            
        async def fetch_google():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.fetch_google_news_trending('ko-KR', max_per_source)
            )
            return result
        
        # 모든 작업 실행 및 결과 수집
        naver_task = asyncio.create_task(fetch_naver())
        daum_task = asyncio.create_task(fetch_daum())
        google_task = asyncio.create_task(fetch_google())
        
        # 결과 수집
        results['naver'] = await naver_task
        results['daum'] = await daum_task
        results['google'] = await google_task
        
        return results 