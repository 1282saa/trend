"""
데이터 캐싱을 위한 유틸리티 모듈
"""
import os
import json
import time
import hashlib
import inspect
from typing import Any, Dict, Optional, Union, Callable, Tuple, List
import logging
import pickle
from functools import wraps
from pathlib import Path
import threading
from enum import Enum, auto

# 로그 설정
logger = logging.getLogger('cache')

class CacheType(Enum):
    """캐시 유형"""
    MEMORY = auto()
    FILE = auto()

class CacheError(Exception):
    """캐시 관련 예외"""
    pass

class MemoryCache:
    """
    메모리 기반 캐시 클래스
    
    스레드 안전한 메모리 캐시 구현으로, 자동 만료 기능을 제공합니다.
    """
    def __init__(self, ttl: int = 300, cleanup_interval: int = 3600):
        """
        메모리 캐시 초기화
        
        Args:
            ttl: 캐시 항목의 기본 유효 시간(초), 기본값 5분
            cleanup_interval: 자동 정리 간격(초), 기본값 1시간
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = ttl
        self.cleanup_interval = cleanup_interval
        self.lock = threading.RLock()
        
        # 만료된 항목 자동 정리 타이머 시작
        self._start_cleanup_timer()
    
    def _start_cleanup_timer(self) -> None:
        """만료된 항목을 주기적으로 정리하는 타이머 시작"""
        def cleanup_task():
            self.cleanup()
            # 다음 정리 작업 예약
            timer = threading.Timer(self.cleanup_interval, cleanup_task)
            timer.daemon = True  # 데몬 스레드로 설정하여 메인 스레드 종료 시 함께 종료
            timer.start()
        
        # 첫 번째 정리 작업 시작
        timer = threading.Timer(self.cleanup_interval, cleanup_task)
        timer.daemon = True
        timer.start()
    
    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 키에 해당하는 값을 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            캐시된 값 또는 None (없거나 만료된 경우)
        """
        with self.lock:
            if key not in self.cache:
                return None
                
            item = self.cache[key]
            # 만료 확인
            if time.time() > item['expires_at']:
                # 만료된 항목 삭제
                del self.cache[key]
                return None
                
            # 접근 시간 업데이트
            item['last_accessed'] = time.time()
            return item['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        캐시에 값 저장
        
        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: 유효 시간(초), 기본값 사용시 None
        """
        _ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + _ttl
        
        with self.lock:
            self.cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time(),
                'last_accessed': time.time()
            }
    
    def delete(self, key: str) -> bool:
        """
        캐시에서 키 삭제
        
        Args:
            key: 삭제할 캐시 키
            
        Returns:
            삭제 성공 여부
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self.lock:
            self.cache.clear()
    
    def cleanup(self) -> int:
        """
        만료된 캐시 항목 정리
        
        Returns:
            삭제된 항목 수
        """
        with self.lock:
            now = time.time()
            expired_keys = [
                key for key, item in self.cache.items() 
                if now > item['expires_at']
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            cleanup_count = len(expired_keys)
            if cleanup_count > 0:
                logger.debug(f"캐시 정리: {cleanup_count}개 항목 삭제됨")
                
            return cleanup_count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 정보 반환
        
        Returns:
            통계 정보 딕셔너리
        """
        with self.lock:
            now = time.time()
            active_items = sum(1 for item in self.cache.values() if now <= item['expires_at'])
            expired_items = len(self.cache) - active_items
            
            if self.cache:
                avg_age = sum(now - item['created_at'] for item in self.cache.values()) / len(self.cache)
                oldest_item = max(now - item['created_at'] for item in self.cache.values())
                newest_item = min(now - item['created_at'] for item in self.cache.values())
            else:
                avg_age = oldest_item = newest_item = 0
            
            return {
                'total_items': len(self.cache),
                'active_items': active_items,
                'expired_items': expired_items,
                'avg_age': avg_age,
                'oldest_item': oldest_item,
                'newest_item': newest_item,
                'memory_usage': self._estimate_memory_usage()
            }
    
    def _estimate_memory_usage(self) -> int:
        """캐시의 대략적인 메모리 사용량 추정 (바이트 단위)"""
        try:
            import sys
            with self.lock:
                # 메모리 사용량 샘플링 (최대 100개 항목)
                sample_keys = list(self.cache.keys())[:100]
                if not sample_keys:
                    return 0
                
                # 샘플 항목의 메모리 사용량 계산
                sample_size = sum(
                    sys.getsizeof(key) + sys.getsizeof(self.cache[key]) 
                    for key in sample_keys
                )
                
                # 전체 메모리 사용량 추정
                return int(sample_size * (len(self.cache) / len(sample_keys)))
        except Exception as e:
            logger.warning(f"메모리 사용량 추정 오류: {str(e)}")
            return 0


class FileCache:
    """
    파일 기반 캐시 클래스
    
    영구적인 캐시 저장을 위한 파일 기반 캐시 구현입니다.
    """
    def __init__(self, cache_dir: str = '.cache', ttl: int = 3600, cleanup_interval: int = 86400):
        """
        파일 캐시 초기화
        
        Args:
            cache_dir: 캐시 디렉토리
            ttl: 캐시 항목의 기본 유효 시간(초), 기본값 1시간
            cleanup_interval: 자동 정리 간격(초), 기본값 1일
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl = ttl
        self.cleanup_interval = cleanup_interval
        self.lock = threading.RLock()
        
        # 캐시 디렉토리 생성
        with self.lock:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # 만료된 항목 자동 정리 타이머 시작
        self._start_cleanup_timer()
    
    def _start_cleanup_timer(self) -> None:
        """만료된 항목을 주기적으로 정리하는 타이머 시작"""
        def cleanup_task():
            self.cleanup()
            # 다음 정리 작업 예약
            timer = threading.Timer(self.cleanup_interval, cleanup_task)
            timer.daemon = True  # 데몬 스레드로 설정하여 메인 스레드 종료 시 함께 종료
            timer.start()
        
        # 첫 번째 정리 작업 시작
        timer = threading.Timer(self.cleanup_interval, cleanup_task)
        timer.daemon = True
        timer.start()
    
    def _get_cache_path(self, key: str) -> Path:
        """키에 해당하는 캐시 파일 경로 생성"""
        # 키를 해시값으로 변환 (파일명으로 사용)
        hashed_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed_key}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 키에 해당하는 값을 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            캐시된 값 또는 None (없거나 만료된 경우)
        """
        with self.lock:
            cache_file = self._get_cache_path(key)
            
            # 캐시 파일이 없는 경우
            if not cache_file.exists():
                return None
                
            try:
                # 캐시 파일 읽기
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    
                # 만료 확인
                if time.time() > cache_data['expires_at']:
                    # 만료된 파일 삭제
                    os.remove(cache_file)
                    return None
                    
                # 접근 시간 업데이트
                cache_data['last_accessed'] = time.time()
                with open(cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                    
                return cache_data['value']
                
            except (IOError, pickle.PickleError) as e:
                logger.warning(f"캐시 파일 읽기 오류: {str(e)}")
                # 손상된 캐시 파일 삭제
                if cache_file.exists():
                    os.remove(cache_file)
                return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        캐시에 값 저장
        
        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: 유효 시간(초), 기본값 사용시 None
            
        Returns:
            저장 성공 여부
        """
        _ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + _ttl
        
        cache_data = {
            'value': value,
            'expires_at': expires_at,
            'created_at': time.time(),
            'last_accessed': time.time()
        }
        
        with self.lock:
            cache_file = self._get_cache_path(key)
            
            try:
                # 캐시 디렉토리 확인
                os.makedirs(self.cache_dir, exist_ok=True)
                
                # 캐시 파일 쓰기
                with open(cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                    
                return True
                
            except (IOError, pickle.PickleError) as e:
                logger.error(f"캐시 파일 쓰기 오류: {str(e)}")
                return False
    
    def delete(self, key: str) -> bool:
        """
        캐시에서 키 삭제
        
        Args:
            key: 삭제할 캐시 키
            
        Returns:
            삭제 성공 여부
        """
        with self.lock:
            cache_file = self._get_cache_path(key)
            
            if cache_file.exists():
                try:
                    os.remove(cache_file)
                    return True
                except IOError as e:
                    logger.error(f"캐시 파일 삭제 오류: {str(e)}")
                    
            return False
    
    def clear(self) -> bool:
        """
        캐시 전체 삭제
        
        Returns:
            삭제 성공 여부
        """
        with self.lock:
            try:
                # 캐시 디렉토리의 모든 파일 삭제
                deleted = 0
                for cache_file in self.cache_dir.glob('*.cache'):
                    os.remove(cache_file)
                    deleted += 1
                    
                logger.info(f"캐시 클리어: {deleted}개 파일 삭제됨")
                return True
                
            except IOError as e:
                logger.error(f"캐시 디렉토리 비우기 오류: {str(e)}")
                return False
    
    def cleanup(self) -> int:
        """
        만료된 캐시 파일 정리
        
        Returns:
            삭제된 파일 수
        """
        with self.lock:
            count = 0
            now = time.time()
            
            try:
                for cache_file in self.cache_dir.glob('*.cache'):
                    try:
                        with open(cache_file, 'rb') as f:
                            cache_data = pickle.load(f)
                            
                        # 만료된 파일 삭제
                        if now > cache_data['expires_at']:
                            os.remove(cache_file)
                            count += 1
                            
                    except (IOError, pickle.PickleError):
                        # 손상된 파일 삭제
                        os.remove(cache_file)
                        count += 1
                
                if count > 0:
                    logger.info(f"캐시 정리: {count}개 파일 삭제됨")
                return count
                
            except Exception as e:
                logger.error(f"캐시 정리 오류: {str(e)}")
                return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 정보 반환
        
        Returns:
            통계 정보 딕셔너리
        """
        with self.lock:
            now = time.time()
            cache_files = list(self.cache_dir.glob('*.cache'))
            
            total_items = len(cache_files)
            active_items = 0
            oldest_time = 0
            newest_time = float('inf')
            total_age = 0
            total_size = 0
            
            for cache_file in cache_files:
                total_size += cache_file.stat().st_size
                try:
                    with open(cache_file, 'rb') as f:
                        cache_data = pickle.load(f)
                    
                    if now <= cache_data.get('expires_at', 0):
                        active_items += 1
                    
                    created_at = cache_data.get('created_at', now)
                    age = now - created_at
                    total_age += age
                    oldest_time = max(oldest_time, age)
                    newest_time = min(newest_time, age)
                except:
                    pass
            
            if total_items > 0:
                avg_age = total_age / total_items
            else:
                avg_age = oldest_time = newest_time = 0
                newest_time = 0  # 항목이 없을 경우 무한대 값 수정
            
            return {
                'total_items': total_items,
                'active_items': active_items,
                'expired_items': total_items - active_items,
                'avg_age': avg_age,
                'oldest_item': oldest_time,
                'newest_item': newest_time,
                'total_size': total_size
            }


# 글로벌 캐시 인스턴스
memory_cache = MemoryCache()
file_cache = FileCache()

def get_cache_key(func: Callable, args: Tuple, kwargs: Dict) -> str:
    """
    함수와 인자로부터 캐시 키 생성
    
    Args:
        func: 캐시할 함수
        args: 위치 인자
        kwargs: 키워드 인자
        
    Returns:
        캐시 키 문자열
    """
    # 모듈 경로와 함수명 포함
    key_parts = [f"{func.__module__}.{func.__qualname__}"]
    
    # 위치 인자 추가
    for arg in args:
        if isinstance(arg, (str, int, float, bool, type(None))):
            key_parts.append(str(arg))
        elif hasattr(arg, '__dict__'):
            # 객체의 경우 클래스명 사용
            key_parts.append(f"{arg.__class__.__name__}")
        else:
            # 다른 타입의 경우 해시 사용
            key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
    
    # 키워드 인자 추가 (정렬하여 순서 일관성 유지)
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool, type(None))):
            key_parts.append(f"{k}={v}")
        elif hasattr(v, '__dict__'):
            # 객체의 경우 클래스명 사용
            key_parts.append(f"{k}={v.__class__.__name__}")
        else:
            # 다른 타입의 경우 해시 사용
            key_parts.append(f"{k}={hashlib.md5(str(v).encode()).hexdigest()[:8]}")
    
    # 키 조합
    return ":".join(key_parts)

def cached(ttl: int = 300, cache_type: CacheType = CacheType.MEMORY, cache_instance: Optional[Union[MemoryCache, FileCache]] = None):
    """
    함수 결과를 캐시하는 데코레이터
    
    Args:
        ttl: 캐시 유효 시간(초)
        cache_type: 사용할 캐시 유형
        cache_instance: 사용할 캐시 인스턴스 (기본값: 타입에 따라 자동 선택)
    """
    def get_cache_instance():
        if cache_instance is not None:
            return cache_instance
        elif cache_type == CacheType.MEMORY:
            return memory_cache
        elif cache_type == CacheType.FILE:
            return file_cache
        else:
            raise ValueError(f"지원하지 않는 캐시 유형: {cache_type}")
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 인스턴스 가져오기
            _cache = get_cache_instance()
            
            # 캐시 키 생성
            cache_key = get_cache_key(func, args, kwargs)
            
            # 캐시 확인
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"캐시 히트: {func.__name__}")
                return cached_result
                
            # 함수 실행
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 결과 캐싱
            _cache.set(cache_key, result, ttl)
            logger.debug(f"캐시 저장: {func.__name__} (실행 시간: {execution_time:.3f}초)")
            
            return result
        return wrapper
    return decorator

async def async_cached(ttl: int = 300, cache_type: CacheType = CacheType.MEMORY, cache_instance: Optional[Union[MemoryCache, FileCache]] = None):
    """
    비동기 함수 결과를 캐시하는 데코레이터
    
    Args:
        ttl: 캐시 유효 시간(초)
        cache_type: 사용할 캐시 유형
        cache_instance: 사용할 캐시 인스턴스 (기본값: 타입에 따라 자동 선택)
    """
    def get_cache_instance():
        if cache_instance is not None:
            return cache_instance
        elif cache_type == CacheType.MEMORY:
            return memory_cache
        elif cache_type == CacheType.FILE:
            return file_cache
        else:
            raise ValueError(f"지원하지 않는 캐시 유형: {cache_type}")
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 인스턴스 가져오기
            _cache = get_cache_instance()
            
            # 캐시 키 생성
            cache_key = get_cache_key(func, args, kwargs)
            
            # 캐시 확인
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"비동기 캐시 히트: {func.__name__}")
                return cached_result
                
            # 비동기 함수 실행
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 결과 캐싱
            _cache.set(cache_key, result, ttl)
            logger.debug(f"비동기 캐시 저장: {func.__name__} (실행 시간: {execution_time:.3f}초)")
            
            return result
        return wrapper
    return decorator

def cache_invalidate(func_or_pattern: Union[Callable, str], *args, **kwargs) -> int:
    """
    특정 함수나 패턴에 대한 캐시를 무효화합니다.
    
    Args:
        func_or_pattern: 무효화할 함수 또는 패턴 문자열
        *args: 함수의 경우 위치 인자 (선택적)
        **kwargs: 함수의 경우 키워드 인자 (선택적)
        
    Returns:
        무효화된 캐시 항목 수
    """
    invalidated = 0
    
    # 함수인 경우 특정 키 무효화
    if callable(func_or_pattern):
        key = get_cache_key(func_or_pattern, args, kwargs)
        if memory_cache.delete(key):
            invalidated += 1
        if file_cache.delete(key):
            invalidated += 1
    
    # 패턴 문자열인 경우 패턴 매칭
    elif isinstance(func_or_pattern, str):
        pattern = func_or_pattern
        
        # 메모리 캐시 무효화
        with memory_cache.lock:
            keys_to_delete = [
                key for key in list(memory_cache.cache.keys())
                if pattern in key
            ]
            for key in keys_to_delete:
                memory_cache.delete(key)
                invalidated += 1
        
        # 파일 캐시 무효화 (해시로 변환되어 있으므로 패턴 매칭이 어려움)
        # 파일 캐시는 전체 삭제만 지원
        if pattern == '*':
            file_cache.clear()
            invalidated += 1
    
    return invalidated

def cache_stats() -> Dict[str, Dict[str, Any]]:
    """
    모든 캐시의 통계 정보를 반환합니다.
    
    Returns:
        캐시 유형별 통계 정보
    """
    return {
        'memory': memory_cache.get_stats(),
        'file': file_cache.get_stats()
    }