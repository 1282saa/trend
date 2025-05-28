"""
데이터 캐싱을 위한 유틸리티 모듈
"""
import os
import json
import time
import hashlib
from typing import Any, Dict, Optional, Union, Callable
import logging
import pickle
from functools import wraps
from pathlib import Path

# 로그 설정
logger = logging.getLogger('cache')

class MemoryCache:
    """
    메모리 기반 캐시 클래스
    """
    def __init__(self, ttl: int = 300):
        """
        메모리 캐시 초기화
        
        Args:
            ttl: 캐시 항목의 기본 유효 시간(초), 기본값 5분
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 키에 해당하는 값을 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            캐시된 값 또는 None (없거나 만료된 경우)
        """
        if key not in self.cache:
            return None
            
        item = self.cache[key]
        # 만료 확인
        if time.time() > item['expires_at']:
            # 만료된 항목 삭제
            del self.cache[key]
            return None
            
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
        
        self.cache[key] = {
            'value': value,
            'expires_at': expires_at
        }
    
    def delete(self, key: str) -> bool:
        """
        캐시에서 키 삭제
        
        Args:
            key: 삭제할 캐시 키
            
        Returns:
            삭제 성공 여부
        """
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        self.cache.clear()
    
    def cleanup(self) -> int:
        """
        만료된 캐시 항목 정리
        
        Returns:
            삭제된 항목 수
        """
        now = time.time()
        expired_keys = [
            key for key, item in self.cache.items() 
            if now > item['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
            
        return len(expired_keys)


class FileCache:
    """
    파일 기반 캐시 클래스
    """
    def __init__(self, cache_dir: str = '.cache', ttl: int = 3600):
        """
        파일 캐시 초기화
        
        Args:
            cache_dir: 캐시 디렉토리
            ttl: 캐시 항목의 기본 유효 시간(초), 기본값 1시간
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl = ttl
        
        # 캐시 디렉토리 생성
        os.makedirs(self.cache_dir, exist_ok=True)
    
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
            'expires_at': expires_at
        }
        
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
        try:
            # 캐시 디렉토리의 모든 파일 삭제
            for cache_file in self.cache_dir.glob('*.cache'):
                os.remove(cache_file)
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
                    
            return count
            
        except Exception as e:
            logger.error(f"캐시 정리 오류: {str(e)}")
            return count


# 글로벌 캐시 인스턴스
memory_cache = MemoryCache()
file_cache = FileCache()

def cached(ttl: int = 300, cache_instance: Optional[Union[MemoryCache, FileCache]] = None):
    """
    함수 결과를 캐시하는 데코레이터
    
    Args:
        ttl: 캐시 유효 시간(초)
        cache_instance: 사용할 캐시 인스턴스 (기본값: memory_cache)
    """
    _cache = cache_instance or memory_cache
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성 (함수명 + 인자)
            key_parts = [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)
            
            # 캐시 확인
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"캐시 히트: {cache_key}")
                return cached_result
                
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐싱
            _cache.set(cache_key, result, ttl)
            logger.debug(f"캐시 저장: {cache_key}")
            
            return result
        return wrapper
    return decorator

def async_cached(ttl: int = 300, cache_instance: Optional[Union[MemoryCache, FileCache]] = None):
    """
    비동기 함수 결과를 캐시하는 데코레이터
    
    Args:
        ttl: 캐시 유효 시간(초)
        cache_instance: 사용할 캐시 인스턴스 (기본값: memory_cache)
    """
    _cache = cache_instance or memory_cache
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성 (함수명 + 인자)
            key_parts = [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)
            
            # 캐시 확인
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"비동기 캐시 히트: {cache_key}")
                return cached_result
                
            # 비동기 함수 실행
            result = await func(*args, **kwargs)
            
            # 결과 캐싱
            _cache.set(cache_key, result, ttl)
            logger.debug(f"비동기 캐시 저장: {cache_key}")
            
            return result
        return wrapper
    return decorator 