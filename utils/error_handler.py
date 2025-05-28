"""
에러 처리 및 로깅 유틸리티 모듈

애플리케이션의 예외 처리와 로깅을 위한 유틸리티 모듈입니다.
구조화된 로깅, 오류 추적, 사용자 정의 예외 등을 제공합니다.
"""
import os
import sys
import logging
import traceback
import time
import json
import functools
import inspect
from typing import Any, Dict, Optional, Union, List, Callable, Type, Tuple
from pathlib import Path
from datetime import datetime
from enum import Enum, auto
import asyncio

# 로그 설정
logger = logging.getLogger('error_handler')

class ErrorSeverity(Enum):
    """오류 심각도 수준"""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()
    
    def to_log_level(self) -> int:
        """로그 레벨로 변환"""
        return {
            ErrorSeverity.DEBUG: logging.DEBUG,
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }[self]

class CollectorError(Exception):
    """
    수집기 관련 기본 예외 클래스
    
    모든 수집기 관련 예외의 기본 클래스입니다.
    """
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.ERROR):
        self.message = message
        self.severity = severity
        self.timestamp = datetime.now()
        super().__init__(self.message)

class NetworkError(CollectorError):
    """네트워크 관련 오류"""
    def __init__(self, message: str, 
                 url: Optional[str] = None, 
                 status_code: Optional[int] = None,
                 severity: ErrorSeverity = ErrorSeverity.ERROR):
        self.url = url
        self.status_code = status_code
        super().__init__(message, severity)
        
    def __str__(self) -> str:
        if self.url and self.status_code:
            return f"{self.message} (URL: {self.url}, Status: {self.status_code})"
        elif self.url:
            return f"{self.message} (URL: {self.url})"
        else:
            return self.message

class ParsingError(CollectorError):
    """데이터 파싱 관련 오류"""
    def __init__(self, message: str,
                 source: Optional[str] = None,
                 field: Optional[str] = None,
                 severity: ErrorSeverity = ErrorSeverity.ERROR):
        self.source = source
        self.field = field
        super().__init__(message, severity)
        
    def __str__(self) -> str:
        if self.source and self.field:
            return f"{self.message} (Source: {self.source}, Field: {self.field})"
        elif self.source:
            return f"{self.message} (Source: {self.source})"
        else:
            return self.message

class ApiError(CollectorError):
    """API 관련 오류"""
    def __init__(self, message: str,
                 api_name: Optional[str] = None,
                 endpoint: Optional[str] = None,
                 error_code: Optional[str] = None,
                 severity: ErrorSeverity = ErrorSeverity.ERROR):
        self.api_name = api_name
        self.endpoint = endpoint
        self.error_code = error_code
        super().__init__(message, severity)
        
    def __str__(self) -> str:
        parts = [self.message]
        if self.api_name:
            parts.append(f"API: {self.api_name}")
        if self.endpoint:
            parts.append(f"Endpoint: {self.endpoint}")
        if self.error_code:
            parts.append(f"Error Code: {self.error_code}")
        
        return f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]

class ConfigError(CollectorError):
    """설정 관련 오류"""
    def __init__(self, message: str,
                 config_key: Optional[str] = None,
                 severity: ErrorSeverity = ErrorSeverity.ERROR):
        self.config_key = config_key
        super().__init__(message, severity)
        
    def __str__(self) -> str:
        if self.config_key:
            return f"{self.message} (Config Key: {self.config_key})"
        else:
            return self.message

class CacheError(CollectorError):
    """캐시 관련 오류"""
    def __init__(self, message: str,
                 cache_key: Optional[str] = None,
                 severity: ErrorSeverity = ErrorSeverity.WARNING):
        self.cache_key = cache_key
        super().__init__(message, severity)
        
    def __str__(self) -> str:
        if self.cache_key:
            return f"{self.message} (Cache Key: {self.cache_key})"
        else:
            return self.message

class ErrorContext:
    """
    오류 컨텍스트 클래스
    
    오류 발생 시 추가 정보를 수집하고 저장합니다.
    """
    def __init__(self, 
                 exception: Exception,
                 collector_name: Optional[str] = None,
                 operation: Optional[str] = None):
        self.exception = exception
        self.collector_name = collector_name
        self.operation = operation
        self.timestamp = datetime.now()
        self.traceback = traceback.format_exc()
        
        # 시스템 정보
        self.python_version = sys.version
        self.platform = sys.platform
        
        # 추가 컨텍스트 정보
        self.extra_context = {}
    
    def add_context(self, key: str, value: Any) -> None:
        """컨텍스트 정보 추가"""
        self.extra_context[key] = value
    
    def get_severity(self) -> ErrorSeverity:
        """예외의 심각도 수준 반환"""
        if isinstance(self.exception, CollectorError):
            return self.exception.severity
        else:
            return ErrorSeverity.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        """사전 형태로 변환"""
        result = {
            'timestamp': self.timestamp.isoformat(),
            'exception_type': type(self.exception).__name__,
            'exception_message': str(self.exception),
            'severity': self.get_severity().name
        }
        
        if self.collector_name:
            result['collector_name'] = self.collector_name
            
        if self.operation:
            result['operation'] = self.operation
            
        if self.extra_context:
            result['context'] = self.extra_context
            
        return result
    
    def __str__(self) -> str:
        """문자열 표현"""
        parts = []
        
        if self.collector_name:
            parts.append(f"Collector: {self.collector_name}")
            
        if self.operation:
            parts.append(f"Operation: {self.operation}")
        
        parts.append(f"Exception: {type(self.exception).__name__}")
        parts.append(f"Message: {str(self.exception)}")
        parts.append(f"Severity: {self.get_severity().name}")
        parts.append(f"Time: {self.timestamp.isoformat()}")
        
        if self.extra_context:
            parts.append("Context:")
            for key, value in self.extra_context.items():
                parts.append(f"  {key}: {value}")
        
        return "\n".join(parts)

class ErrorHandler:
    """
    오류 처리기 클래스
    
    애플리케이션의 오류를 처리하고 로깅합니다.
    """
    
    def __init__(self, 
                 log_dir: Optional[str] = None,
                 notification_callback: Optional[Callable[[ErrorContext], None]] = None):
        """
        오류 처리기 초기화
        
        Args:
            log_dir: 오류 로그 디렉토리
            notification_callback: 오류 발생 시 호출할 콜백 함수
        """
        self.log_dir = log_dir
        self.notification_callback = notification_callback
        
        # 로그 디렉토리 생성
        if self.log_dir:
            os.makedirs(self.log_dir, exist_ok=True)
    
    def handle_error(self, 
                     error_context: ErrorContext, 
                     reraise: bool = False) -> None:
        """
        오류 처리
        
        Args:
            error_context: 오류 컨텍스트
            reraise: 처리 후 예외를 다시 발생시킬지 여부
        """
        # 오류 로깅
        self._log_error(error_context)
        
        # 오류 파일 저장
        if self.log_dir:
            self._save_error_to_file(error_context)
        
        # 알림 콜백 호출
        if self.notification_callback:
            try:
                self.notification_callback(error_context)
            except Exception as e:
                logger.error(f"알림 콜백 호출 중 오류 발생: {str(e)}")
        
        # 예외 다시 발생
        if reraise:
            raise error_context.exception
    
    def _log_error(self, error_context: ErrorContext) -> None:
        """
        오류 로깅
        
        Args:
            error_context: 오류 컨텍스트
        """
        # 심각도에 따른 로그 레벨 결정
        severity = error_context.get_severity()
        log_level = severity.to_log_level()
        
        # 로그 메시지 구성
        log_message = f"Error: {error_context.exception}"
        
        if error_context.collector_name:
            log_message = f"[{error_context.collector_name}] {log_message}"
            
        if error_context.operation:
            log_message = f"{log_message} (Operation: {error_context.operation})"
        
        # 로그 출력
        logger.log(log_level, log_message)
        
        # 디버그 레벨 이상이면 스택 트레이스 로깅
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Traceback:\n{error_context.traceback}")
            
        # 추가 컨텍스트 로깅
        if error_context.extra_context and logger.isEnabledFor(logging.DEBUG):
            context_str = "\n".join(f"  {k}: {v}" for k, v in error_context.extra_context.items())
            logger.debug(f"Error Context:\n{context_str}")
    
    def _save_error_to_file(self, error_context: ErrorContext) -> None:
        """
        오류 정보를 파일로 저장
        
        Args:
            error_context: 오류 컨텍스트
        """
        if not self.log_dir:
            return
            
        try:
            # 파일명 생성
            timestamp = error_context.timestamp.strftime('%Y%m%d_%H%M%S')
            exception_type = type(error_context.exception).__name__
            collector_prefix = f"{error_context.collector_name}_" if error_context.collector_name else ""
            
            filename = f"{collector_prefix}{exception_type}_{timestamp}.json"
            filepath = os.path.join(self.log_dir, filename)
            
            # 오류 정보를 JSON으로 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                error_data = error_context.to_dict()
                error_data['traceback'] = error_context.traceback
                json.dump(error_data, f, indent=2, ensure_ascii=False)
                
            logger.debug(f"오류 정보가 저장됨: {filepath}")
            
        except Exception as e:
            logger.error(f"오류 정보 파일 저장 실패: {str(e)}")
    
    def create_error_context(self, 
                            exception: Exception,
                            collector_name: Optional[str] = None,
                            operation: Optional[str] = None) -> ErrorContext:
        """
        오류 컨텍스트 생성
        
        Args:
            exception: 발생한 예외
            collector_name: 수집기 이름
            operation: 수행 중이던 작업
            
        Returns:
            오류 컨텍스트 객체
        """
        return ErrorContext(exception, collector_name, operation)

# 기본 오류 처리기
default_error_handler = ErrorHandler()

def set_error_handler(handler: ErrorHandler) -> None:
    """
    기본 오류 처리기 설정
    
    Args:
        handler: 새 오류 처리기
    """
    global default_error_handler
    default_error_handler = handler

def get_error_handler() -> ErrorHandler:
    """
    기본 오류 처리기 가져오기
    
    Returns:
        오류 처리기
    """
    return default_error_handler

def handle_errors(collector_name: Optional[str] = None, 
                 operation: Optional[str] = None,
                 reraise: bool = False,
                 error_types: Optional[List[Type[Exception]]] = None):
    """
    오류 처리 데코레이터
    
    Args:
        collector_name: 수집기 이름
        operation: 수행 중인 작업
        reraise: 처리 후 예외를 다시 발생시킬지 여부
        error_types: 처리할 예외 유형 목록 (None이면 모든 예외)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 특정 예외 유형만 처리하는 경우
                if error_types and not any(isinstance(e, error_type) for error_type in error_types):
                    raise
                
                # 오류 처리
                _collector = collector_name
                _operation = operation or func.__name__
                
                # 첫 번째 인자가 self인 경우 수집기 이름 추정
                if not _collector and args and hasattr(args[0], '__class__'):
                    _collector = args[0].__class__.__name__
                
                # 오류 컨텍스트 생성 및 처리
                error_context = default_error_handler.create_error_context(
                    e, _collector, _operation
                )
                default_error_handler.handle_error(error_context, reraise)
                
                # 기본 반환 값
                return None
                
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 특정 예외 유형만 처리하는 경우
                if error_types and not any(isinstance(e, error_type) for error_type in error_types):
                    raise
                
                # 오류 처리
                _collector = collector_name
                _operation = operation or func.__name__
                
                # 첫 번째 인자가 self인 경우 수집기 이름 추정
                if not _collector and args and hasattr(args[0], '__class__'):
                    _collector = args[0].__class__.__name__
                
                # 오류 컨텍스트 생성 및 처리
                error_context = default_error_handler.create_error_context(
                    e, _collector, _operation
                )
                default_error_handler.handle_error(error_context, reraise)
                
                # 기본 반환 값
                return None
        
        # 동기 또는 비동기 함수에 따라 적절한 래퍼 반환
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator

def retry(max_attempts: int = 3, 
          delay: float = 1.0, 
          backoff_factor: float = 2.0,
          error_types: Optional[List[Type[Exception]]] = None,
          collector_name: Optional[str] = None):
    """
    재시도 데코레이터
    
    Args:
        max_attempts: 최대 시도 횟수
        delay: 재시도 간 대기 시간(초)
        backoff_factor: 재시도 간 대기 시간 증가 비율
        error_types: 재시도할 예외 유형 목록 (None이면 모든 예외)
        collector_name: 수집기 이름
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _collector = collector_name
            if not _collector and args and hasattr(args[0], '__class__'):
                _collector = args[0].__class__.__name__
                
            _operation = func.__name__
            
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 특정 예외 유형만 재시도하는 경우
                    if error_types and not any(isinstance(e, error_type) for error_type in error_types):
                        raise
                    
                    last_exception = e
                    
                    # 마지막 시도가 아니면 재시도
                    if attempt < max_attempts:
                        wait_time = delay * (backoff_factor ** (attempt - 1))
                        logger.warning(f"[{_collector}] {_operation} 실패 (시도 {attempt}/{max_attempts}): {str(e)}, {wait_time:.2f}초 후 재시도")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"[{_collector}] {_operation} 실패: 최대 시도 횟수 초과 ({max_attempts}회)")
                        
                        # 오류 처리
                        error_context = default_error_handler.create_error_context(
                            last_exception, _collector, _operation
                        )
                        error_context.add_context('attempts', max_attempts)
                        default_error_handler.handle_error(error_context, False)
                        
                        raise last_exception
            
            # 여기까지 오면 모든 시도가 실패한 것
            return None
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            _collector = collector_name
            if not _collector and args and hasattr(args[0], '__class__'):
                _collector = args[0].__class__.__name__
                
            _operation = func.__name__
            
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # 특정 예외 유형만 재시도하는 경우
                    if error_types and not any(isinstance(e, error_type) for error_type in error_types):
                        raise
                    
                    last_exception = e
                    
                    # 마지막 시도가 아니면 재시도
                    if attempt < max_attempts:
                        wait_time = delay * (backoff_factor ** (attempt - 1))
                        logger.warning(f"[{_collector}] {_operation} 실패 (시도 {attempt}/{max_attempts}): {str(e)}, {wait_time:.2f}초 후 재시도")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"[{_collector}] {_operation} 실패: 최대 시도 횟수 초과 ({max_attempts}회)")
                        
                        # 오류 처리
                        error_context = default_error_handler.create_error_context(
                            last_exception, _collector, _operation
                        )
                        error_context.add_context('attempts', max_attempts)
                        default_error_handler.handle_error(error_context, False)
                        
                        raise last_exception
            
            # 여기까지 오면 모든 시도가 실패한 것
            return None
        
        # 동기 또는 비동기 함수에 따라 적절한 래퍼 반환
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator

class StructuredLogger:
    """
    구조화된 로깅 클래스
    
    JSON 형식의 구조화된 로그를 생성합니다.
    """
    
    def __init__(self, 
                 name: str,
                 log_dir: Optional[str] = None,
                 console: bool = True,
                 level: int = logging.INFO):
        """
        구조화된 로거 초기화
        
        Args:
            name: 로거 이름
            log_dir: 로그 파일 디렉토리
            console: 콘솔 출력 여부
            level: 로그 레벨
        """
        self.name = name
        self.log_dir = log_dir
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 기존 핸들러 제거
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 콘솔 핸들러 추가
        if console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(self._create_formatter())
            self.logger.addHandler(console_handler)
        
        # 파일 핸들러 추가
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{name}.log")
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(self._create_formatter())
            self.logger.addHandler(file_handler)
    
    def _create_formatter(self) -> logging.Formatter:
        """로그 포맷터 생성"""
        return logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    def _format_log(self, 
                   message: str, 
                   collector: Optional[str] = None,
                   operation: Optional[str] = None,
                   **kwargs) -> str:
        """
        로그 메시지 포맷팅
        
        Args:
            message: 로그 메시지
            collector: 수집기 이름
            operation: 작업 이름
            **kwargs: 추가 컨텍스트
            
        Returns:
            포맷팅된 로그 메시지
        """
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'message': message
        }
        
        if collector:
            log_data['collector'] = collector
            
        if operation:
            log_data['operation'] = operation
            
        if kwargs:
            log_data.update(kwargs)
            
        return json.dumps(log_data, ensure_ascii=False)
    
    def debug(self, 
             message: str, 
             collector: Optional[str] = None,
             operation: Optional[str] = None,
             **kwargs) -> None:
        """디버그 레벨 로깅"""
        self.logger.debug(self._format_log(message, collector, operation, **kwargs))
    
    def info(self, 
            message: str, 
            collector: Optional[str] = None,
            operation: Optional[str] = None,
            **kwargs) -> None:
        """정보 레벨 로깅"""
        self.logger.info(self._format_log(message, collector, operation, **kwargs))
    
    def warning(self, 
               message: str, 
               collector: Optional[str] = None,
               operation: Optional[str] = None,
               **kwargs) -> None:
        """경고 레벨 로깅"""
        self.logger.warning(self._format_log(message, collector, operation, **kwargs))
    
    def error(self, 
             message: str, 
             collector: Optional[str] = None,
             operation: Optional[str] = None,
             exception: Optional[Exception] = None,
             **kwargs) -> None:
        """오류 레벨 로깅"""
        if exception:
            kwargs['exception_type'] = type(exception).__name__
            kwargs['exception_message'] = str(exception)
            
            if self.logger.isEnabledFor(logging.DEBUG):
                kwargs['traceback'] = traceback.format_exc()
                
        self.logger.error(self._format_log(message, collector, operation, **kwargs))
    
    def critical(self, 
                message: str, 
                collector: Optional[str] = None,
                operation: Optional[str] = None,
                exception: Optional[Exception] = None,
                **kwargs) -> None:
        """심각 레벨 로깅"""
        if exception:
            kwargs['exception_type'] = type(exception).__name__
            kwargs['exception_message'] = str(exception)
            
            # 심각 오류는 항상 스택 트레이스 포함
            kwargs['traceback'] = traceback.format_exc()
                
        self.logger.critical(self._format_log(message, collector, operation, **kwargs))