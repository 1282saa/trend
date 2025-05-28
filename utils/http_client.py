"""
HTTP 요청 처리를 위한 유틸리티 클래스
"""
import time
import random
import logging
import asyncio
from typing import Dict, Any, Optional, Union, List
import os

import requests
import aiohttp
from requests.exceptions import RequestException
from aiohttp.client_exceptions import ClientError

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('http_client')

# User-Agent 목록 (봇 차단 방지용)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
]

class HttpClient:
    """
    HTTP 요청 처리를 위한 클라이언트 클래스
    - 동기 및 비동기 요청 모두 지원
    - 재시도 로직 내장
    - User-Agent 자동 순환
    """
    
    def __init__(
        self, 
        max_retries: int = 3, 
        retry_delay: float = 1.0,
        timeout: float = 10.0,
        proxy: Optional[str] = None,
        rotate_user_agent: bool = True
    ):
        """
        HTTP 클라이언트 초기화
        
        Args:
            max_retries: 최대 재시도 횟수
            retry_delay: 재시도 간 지연 시간(초)
            timeout: 요청 타임아웃(초)
            proxy: 프록시 서버 (예: 'http://user:pass@host:port')
            rotate_user_agent: User-Agent 자동 교체 사용 여부
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.rotate_user_agent = rotate_user_agent
        
        # 프록시 설정
        self.proxies = None
        if proxy:
            self.proxies = {'http': proxy, 'https': proxy}
        
        # 환경 변수에서 프록시 가져오기
        elif os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY'):
            self.proxies = {
                'http': os.getenv('HTTP_PROXY'),
                'https': os.getenv('HTTPS_PROXY')
            }
    
    def get_headers(self) -> Dict[str, str]:
        """기본 헤더 생성"""
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'DNT': '1',  # Do Not Track
            'Upgrade-Insecure-Requests': '1',
        }
        
        # User-Agent 자동 교체
        if self.rotate_user_agent:
            headers['User-Agent'] = random.choice(USER_AGENTS)
            
        return headers
    
    def get(
        self, 
        url: str, 
        params: Optional[Dict[str, Any]] = None, 
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> requests.Response:
        """
        GET 요청 실행
        
        Args:
            url: 요청 URL
            params: URL 매개변수
            headers: HTTP 헤더
            cookies: 쿠키
            **kwargs: requests.get에 전달할 추가 인자
            
        Returns:
            응답 객체
            
        Raises:
            RequestException: 최대 재시도 후에도 실패한 경우
        """
        _headers = self.get_headers()
        if headers:
            _headers.update(headers)
            
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url, 
                    params=params, 
                    headers=_headers,
                    cookies=cookies,
                    timeout=self.timeout,
                    proxies=self.proxies,
                    **kwargs
                )
                
                # 응답 상태 코드 확인
                response.raise_for_status()
                return response
                
            except RequestException as e:
                logger.warning(f"요청 실패 ({attempt+1}/{self.max_retries}): {url} - {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # 재시도 간 지연 (지터 추가)
                    jitter = random.uniform(0, 0.5)
                    delay = self.retry_delay * (2 ** attempt) + jitter
                    time.sleep(delay)
                else:
                    logger.error(f"최대 재시도 횟수 초과: {url}")
                    raise
    
    async def async_get(
        self, 
        url: str, 
        params: Optional[Dict[str, Any]] = None, 
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        비동기 GET 요청 실행
        
        Args:
            url: 요청 URL
            params: URL 매개변수
            headers: HTTP 헤더
            cookies: 쿠키
            **kwargs: aiohttp.ClientSession.get에 전달할 추가 인자
            
        Returns:
            응답 텍스트
            
        Raises:
            ClientError: 최대 재시도 후에도 실패한 경우
        """
        _headers = self.get_headers()
        if headers:
            _headers.update(headers)
            
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, 
                        params=params, 
                        headers=_headers,
                        cookies=cookies,
                        timeout=self.timeout,
                        proxy=self.proxies['http'] if self.proxies else None,
                        **kwargs
                    ) as response:
                        response.raise_for_status()
                        return await response.text()
                        
            except (ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"비동기 요청 실패 ({attempt+1}/{self.max_retries}): {url} - {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # 재시도 간 지연 (지터 추가)
                    jitter = random.uniform(0, 0.5)
                    delay = self.retry_delay * (2 ** attempt) + jitter
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"비동기 요청 최대 재시도 횟수 초과: {url}")
                    raise
                    
    async def async_get_multiple(
        self, 
        urls: List[str], 
        params_list: Optional[List[Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> List[Optional[str]]:
        """
        여러 URL에 대한 비동기 GET 요청 실행
        
        Args:
            urls: 요청 URL 목록
            params_list: URL별 매개변수 목록 (없으면 None으로 처리)
            headers: 모든 요청에 적용할 공통 HTTP 헤더
            **kwargs: aiohttp.ClientSession.get에 전달할 추가 인자
            
        Returns:
            응답 텍스트 목록 (실패한 요청은 None)
        """
        if params_list is None:
            params_list = [None] * len(urls)
        
        # 모든 요청의 결과를 담을 리스트    
        results = []
        
        # 비동기 작업 생성
        tasks = []
        for url, params in zip(urls, params_list):
            task = asyncio.create_task(
                self.async_get(url, params=params, headers=headers, **kwargs)
            )
            tasks.append(task)
        
        # 완료된 작업 처리
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                logger.error(f"다중 요청 중 오류 발생: {str(e)}")
                results.append(None)
                
        return results 