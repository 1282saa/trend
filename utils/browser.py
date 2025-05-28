"""
Selenium을 활용한 브라우저 자동화 유틸리티 모듈
"""
import os
import time
import logging
import random
from typing import Optional, Dict, Any, List, Union, Tuple
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# 로그 설정
logger = logging.getLogger('browser')

# User-Agent 목록 (봇 차단 방지용)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
]

class BrowserManager:
    """
    브라우저 자동화 관리 클래스
    - 여러 브라우저 타입 지원 (Chrome, Firefox, Edge)
    - 헤드리스 모드 지원
    - User-Agent 자동 교체
    - 프록시 설정 지원
    """
    
    def __init__(
        self, 
        browser_type: str = 'chrome',
        headless: bool = True,
        user_agent: Optional[str] = None,
        proxy: Optional[str] = None,
        timeout: int = 10,
        browser_args: Optional[List[str]] = None,
        download_dir: Optional[str] = None
    ):
        """
        브라우저 관리자 초기화
        
        Args:
            browser_type: 브라우저 유형 ('chrome', 'firefox', 'edge')
            headless: 헤드리스 모드 사용 여부
            user_agent: User-Agent 문자열 (None이면 자동 선택)
            proxy: 프록시 서버 (예: 'http://user:pass@host:port')
            timeout: 기본 대기 시간(초)
            browser_args: 브라우저 시작시 추가 인자 목록
            download_dir: 다운로드 디렉토리
        """
        self.browser_type = browser_type.lower()
        self.headless = headless
        self.user_agent = user_agent or random.choice(USER_AGENTS)
        self.proxy = proxy
        self.timeout = timeout
        self.browser_args = browser_args or []
        self.download_dir = download_dir
        
        # 브라우저 설정
        self._setup_browser_options()
        
    def _setup_browser_options(self):
        """브라우저 옵션 설정"""
        if self.browser_type == 'chrome':
            self.options = ChromeOptions()
            
            # 헤드리스 모드
            if self.headless:
                self.options.add_argument('--headless=new')  # 신형 헤드리스 모드
            
            # 기본 설정
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-gpu')
            self.options.add_argument('--disable-extensions')
            self.options.add_argument('--disable-popup-blocking')
            self.options.add_argument('--blink-settings=imagesEnabled=false')  # 이미지 로딩 비활성화
            
            # User-Agent 설정
            self.options.add_argument(f'--user-agent={self.user_agent}')
            
            # 프록시 설정
            if self.proxy:
                self.options.add_argument(f'--proxy-server={self.proxy}')
            
            # 추가 인자
            for arg in self.browser_args:
                self.options.add_argument(arg)
                
            # 다운로드 디렉토리 설정
            if self.download_dir:
                os.makedirs(self.download_dir, exist_ok=True)
                prefs = {
                    'download.default_directory': os.path.abspath(self.download_dir),
                    'download.prompt_for_download': False
                }
                self.options.add_experimental_option('prefs', prefs)
                
        elif self.browser_type == 'firefox':
            self.options = FirefoxOptions()
            
            # 헤드리스 모드
            if self.headless:
                self.options.add_argument('--headless')
            
            # User-Agent 설정
            self.options.set_preference('general.useragent.override', self.user_agent)
            
            # 프록시 설정
            if self.proxy:
                proxy_parts = self.proxy.split('://')
                protocol = proxy_parts[0] if len(proxy_parts) > 1 else 'http'
                proxy_addr = proxy_parts[-1]
                
                if '@' in proxy_addr:
                    auth, addr = proxy_addr.split('@')
                    user, pwd = auth.split(':')
                    host, port = addr.split(':')
                    
                    self.options.set_preference('network.proxy.type', 1)
                    self.options.set_preference(f'network.proxy.{protocol}', host)
                    self.options.set_preference(f'network.proxy.{protocol}_port', int(port))
                    self.options.set_preference('network.proxy.username', user)
                    self.options.set_preference('network.proxy.password', pwd)
                else:
                    host, port = proxy_addr.split(':')
                    
                    self.options.set_preference('network.proxy.type', 1)
                    self.options.set_preference(f'network.proxy.{protocol}', host)
                    self.options.set_preference(f'network.proxy.{protocol}_port', int(port))
            
            # 다운로드 디렉토리 설정
            if self.download_dir:
                os.makedirs(self.download_dir, exist_ok=True)
                self.options.set_preference('browser.download.folderList', 2)
                self.options.set_preference('browser.download.dir', os.path.abspath(self.download_dir))
                self.options.set_preference('browser.download.useDownloadDir', True)
                self.options.set_preference('browser.helperApps.neverAsk.saveToDisk', 'application/octet-stream')
                
        elif self.browser_type == 'edge':
            self.options = EdgeOptions()
            
            # 헤드리스 모드
            if self.headless:
                self.options.add_argument('--headless=new')
            
            # 기본 설정
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-gpu')
            self.options.add_argument('--disable-extensions')
            
            # User-Agent 설정
            self.options.add_argument(f'--user-agent={self.user_agent}')
            
            # 프록시 설정
            if self.proxy:
                self.options.add_argument(f'--proxy-server={self.proxy}')
            
            # 추가 인자
            for arg in self.browser_args:
                self.options.add_argument(arg)
                
            # 다운로드 디렉토리 설정
            if self.download_dir:
                os.makedirs(self.download_dir, exist_ok=True)
                prefs = {
                    'download.default_directory': os.path.abspath(self.download_dir),
                    'download.prompt_for_download': False
                }
                self.options.add_experimental_option('prefs', prefs)
        else:
            raise ValueError(f"지원하지 않는 브라우저 유형: {self.browser_type}")
    
    @contextmanager
    def create_driver(self):
        """
        웹드라이버 생성 및 관리 (with 구문용 컨텍스트 매니저)
        
        Yields:
            WebDriver: 초기화된 웹드라이버 인스턴스
        """
        driver = None
        try:
            if self.browser_type == 'chrome':
                driver = webdriver.Chrome(options=self.options)
            elif self.browser_type == 'firefox':
                driver = webdriver.Firefox(options=self.options)
            elif self.browser_type == 'edge':
                driver = webdriver.Edge(options=self.options)
            
            # 브라우저 설정
            driver.set_page_load_timeout(self.timeout)
            driver.implicitly_wait(self.timeout)
            
            yield driver
            
        except WebDriverException as e:
            logger.error(f"브라우저 초기화 오류: {str(e)}")
            raise
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"브라우저 종료 오류: {str(e)}")

    def get_page(self, url: str, wait_time: Optional[int] = None) -> Tuple[Optional[webdriver.Chrome], bool]:
        """
        URL로 페이지 로드
        
        Args:
            url: 방문할 URL
            wait_time: 페이지 로드 후 추가 대기 시간(초)
            
        Returns:
            (드라이버 인스턴스, 성공 여부) 튜플
        """
        driver = None
        try:
            if self.browser_type == 'chrome':
                driver = webdriver.Chrome(options=self.options)
            elif self.browser_type == 'firefox':
                driver = webdriver.Firefox(options=self.options)
            elif self.browser_type == 'edge':
                driver = webdriver.Edge(options=self.options)
                
            # 페이지 로드
            driver.get(url)
            
            # 추가 대기 (JavaScript 로딩 등)
            if wait_time:
                time.sleep(wait_time)
                
            return driver, True
            
        except Exception as e:
            logger.error(f"페이지 로드 오류: {str(e)}")
            if driver:
                driver.quit()
            return None, False

    @staticmethod
    def wait_for_element(
        driver: Union[webdriver.Chrome, webdriver.Firefox, webdriver.Edge],
        selector: str, 
        by: str = By.CSS_SELECTOR, 
        timeout: int = 10, 
        condition: str = 'presence'
    ) -> Any:
        """
        요소가 나타날 때까지 대기
        
        Args:
            driver: 웹드라이버 인스턴스
            selector: 요소 선택자
            by: 선택자 유형 (예: By.CSS_SELECTOR, By.XPATH)
            timeout: 최대 대기 시간(초)
            condition: 대기 조건 ('presence', 'visibility', 'clickable')
            
        Returns:
            발견된 요소 또는 None
        
        Raises:
            TimeoutException: 요소를 찾지 못한 경우
        """
        wait = WebDriverWait(driver, timeout)
        
        try:
            if condition == 'presence':
                element = wait.until(EC.presence_of_element_located((by, selector)))
            elif condition == 'visibility':
                element = wait.until(EC.visibility_of_element_located((by, selector)))
            elif condition == 'clickable':
                element = wait.until(EC.element_to_be_clickable((by, selector)))
            else:
                raise ValueError(f"지원하지 않는 대기 조건: {condition}")
                
            return element
            
        except TimeoutException:
            logger.warning(f"요소를 찾지 못함: {selector} (조건: {condition})")
            return None

    @staticmethod
    def scroll_down(
        driver: Union[webdriver.Chrome, webdriver.Firefox, webdriver.Edge],
        scroll_amount: Optional[int] = None,
        scroll_pause: float = 1.0,
        max_scrolls: Optional[int] = None
    ) -> None:
        """
        페이지 아래로 스크롤
        
        Args:
            driver: 웹드라이버 인스턴스
            scroll_amount: 각 스크롤 단계의 픽셀 수 (None이면 화면 높이)
            scroll_pause: 스크롤 간 대기 시간(초)
            max_scrolls: 최대 스크롤 횟수 (None이면 페이지 끝까지)
        """
        # 현재 스크롤 위치
        current_position = driver.execute_script("return window.pageYOffset;")
        
        # 스크롤 수행
        scrolls = 0
        while True:
            # 다음 스크롤 위치 계산
            if scroll_amount:
                next_position = current_position + scroll_amount
                driver.execute_script(f"window.scrollTo(0, {next_position});")
            else:
                # 화면 높이만큼 스크롤
                driver.execute_script("window.scrollBy(0, window.innerHeight);")
            
            # 대기
            time.sleep(scroll_pause)
            
            # 스크롤 횟수 증가
            scrolls += 1
            
            # 새로운 스크롤 위치
            new_position = driver.execute_script("return window.pageYOffset;")
            
            # 스크롤 끝에 도달했거나 최대 스크롤 횟수에 도달
            if (new_position == current_position or 
                (max_scrolls is not None and scrolls >= max_scrolls)):
                break
                
            current_position = new_position

    @staticmethod
    def extract_elements(
        driver: Union[webdriver.Chrome, webdriver.Firefox, webdriver.Edge],
        selector: str,
        by: str = By.CSS_SELECTOR,
        attribute: Optional[str] = None,
        extract_text: bool = True
    ) -> List[str]:
        """
        페이지에서 요소 추출
        
        Args:
            driver: 웹드라이버 인스턴스
            selector: 요소 선택자
            by: 선택자 유형 (예: By.CSS_SELECTOR, By.XPATH)
            attribute: 추출할 속성명 (예: 'href', 'src')
            extract_text: True이면 텍스트 추출, False면 속성값 추출
            
        Returns:
            추출된 텍스트 또는 속성값 리스트
        """
        try:
            elements = driver.find_elements(by, selector)
            
            if extract_text:
                return [el.text.strip() for el in elements if el.text.strip()]
            elif attribute:
                return [el.get_attribute(attribute) for el in elements if el.get_attribute(attribute)]
            else:
                return []
                
        except Exception as e:
            logger.error(f"요소 추출 오류: {str(e)}")
            return [] 