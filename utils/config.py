"""
환경 설정 관리 모듈

다양한 환경 변수와 설정을 중앙에서 관리하는 모듈입니다.
개발, 테스트, 프로덕션 환경에 따라 설정을 다르게 로드할 수 있습니다.
"""
import os
import json
import logging
from typing import Dict, Any, Optional, Union, List
from enum import Enum, auto
from pathlib import Path
import yaml

# 로그 설정
logger = logging.getLogger('config')

class Environment(Enum):
    """실행 환경"""
    DEVELOPMENT = auto()
    TESTING = auto()
    PRODUCTION = auto()

class Config:
    """
    환경 설정 관리 클래스
    
    환경 변수와 설정 파일로부터 설정을 로드하고 관리합니다.
    """
    
    _instance = None  # 싱글톤 인스턴스
    
    def __new__(cls, *args, **kwargs):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, 
                 env: Union[Environment, str] = None, 
                 config_file: Optional[str] = None,
                 use_dotenv: bool = True):
        """
        설정 관리자 초기화
        
        Args:
            env: 실행 환경 (None이면 환경 변수에서 가져옴)
            config_file: 설정 파일 경로 (None이면 기본 위치에서 검색)
            use_dotenv: .env 파일 로드 여부
        """
        # 이미 초기화되었는지 확인
        if hasattr(self, 'initialized') and self.initialized:
            return
            
        # 환경 설정
        if env is None:
            env_str = os.getenv('APP_ENV', 'development').lower()
            if env_str == 'production':
                self.env = Environment.PRODUCTION
            elif env_str == 'testing':
                self.env = Environment.TESTING
            else:
                self.env = Environment.DEVELOPMENT
        elif isinstance(env, Environment):
            self.env = env
        else:
            env_str = str(env).lower()
            if env_str == 'production':
                self.env = Environment.PRODUCTION
            elif env_str == 'testing':
                self.env = Environment.TESTING
            else:
                self.env = Environment.DEVELOPMENT
        
        # .env 파일 로드
        if use_dotenv:
            self._load_dotenv()
        
        # 기본 설정 초기화
        self.settings = {}
        
        # 설정 파일 로드
        if config_file:
            self._load_config_file(config_file)
        else:
            # 기본 위치에서 설정 파일 찾기
            for file_path in ['config.yaml', 'config.yml', 'config.json']:
                if os.path.exists(file_path):
                    self._load_config_file(file_path)
                    break
        
        # 환경 변수에서 설정 로드
        self._load_from_env()
        
        # 로깅 설정 초기화
        self._init_logging()
        
        # 초기화 완료 표시
        self.initialized = True
        
        logger.info(f"설정 로드 완료 (환경: {self.env.name})")
    
    def _load_dotenv(self) -> None:
        """
        .env 파일 로드
        
        여러 위치의 .env 파일을 검색하여 로드합니다.
        """
        try:
            from dotenv import load_dotenv
            
            # 환경별 .env 파일 로드
            env_files = ['.env']
            if self.env == Environment.DEVELOPMENT:
                env_files.insert(0, '.env.development')
            elif self.env == Environment.TESTING:
                env_files.insert(0, '.env.testing')
            elif self.env == Environment.PRODUCTION:
                env_files.insert(0, '.env.production')
            
            # 모든 .env 파일 로드 시도
            for env_file in env_files:
                if os.path.exists(env_file):
                    load_dotenv(env_file)
                    logger.debug(f".env 파일 로드됨: {env_file}")
                    
        except ImportError:
            logger.warning("python-dotenv 패키지가 설치되지 않았습니다. .env 파일을 로드할 수 없습니다.")
    
    def _load_config_file(self, file_path: str) -> None:
        """
        설정 파일 로드
        
        Args:
            file_path: 설정 파일 경로
        """
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_ext in ['.yaml', '.yml']:
                    try:
                        import yaml
                        config_data = yaml.safe_load(f)
                    except ImportError:
                        logger.warning("PyYAML 패키지가 설치되지 않았습니다. YAML 설정 파일을 로드할 수 없습니다.")
                        return
                elif file_ext == '.json':
                    config_data = json.load(f)
                else:
                    logger.warning(f"지원하지 않는 설정 파일 형식: {file_ext}")
                    return
            
            # 환경별 설정 로드
            if isinstance(config_data, dict):
                # 공통 설정 로드
                if 'common' in config_data:
                    self.settings.update(config_data['common'])
                
                # 환경별 설정 로드
                env_key = self.env.name.lower()
                if env_key in config_data:
                    self.settings.update(config_data[env_key])
            
            logger.debug(f"설정 파일 로드됨: {file_path}")
            
        except Exception as e:
            logger.error(f"설정 파일 로드 오류: {str(e)}")
    
    def _load_from_env(self) -> None:
        """환경 변수에서 설정 로드"""
        # 환경 변수 접두어
        prefix = 'APP_'
        
        # 모든 환경 변수 순회
        for key, value in os.environ.items():
            # 접두어로 시작하는 환경 변수만 처리
            if key.startswith(prefix):
                # 접두어 제거 및 소문자로 변환
                setting_key = key[len(prefix):].lower()
                
                # 중첩 키 처리 (예: APP_DATABASE_URL -> database.url)
                if '_' in setting_key:
                    parts = setting_key.split('_')
                    
                    # 현재 설정 위치
                    current = self.settings
                    
                    # 마지막 부분을 제외한 모든 부분은 중첩 사전 생성
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        elif not isinstance(current[part], dict):
                            current[part] = {}
                        current = current[part]
                    
                    # 마지막 부분이 값 할당
                    current[parts[-1]] = self._parse_env_value(value)
                else:
                    self.settings[setting_key] = self._parse_env_value(value)
    
    def _parse_env_value(self, value: str) -> Any:
        """
        환경 변수 값 파싱
        
        Args:
            value: 환경 변수 값
            
        Returns:
            파싱된 값 (문자열, 숫자, 불리언, 목록, 사전)
        """
        # 불리언 값 처리
        if value.lower() in ['true', 'yes', '1']:
            return True
        elif value.lower() in ['false', 'no', '0']:
            return False
            
        # 숫자 처리
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
            
        # 목록 처리 (쉼표로 구분)
        if ',' in value and not value.startswith('{'):
            return [item.strip() for item in value.split(',')]
            
        # JSON 처리
        if (value.startswith('{') and value.endswith('}')) or \
           (value.startswith('[') and value.endswith(']')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # 기본: 문자열 반환
        return value
    
    def _init_logging(self) -> None:
        """로깅 설정 초기화"""
        log_config = self.get('logging', {})
        
        if not log_config:
            return
            
        try:
            # 로그 레벨 설정
            log_level = getattr(logging, log_config.get('level', 'INFO').upper())
            
            # 로그 형식 설정
            log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # 로그 파일 설정
            log_file = log_config.get('file')
            
            # 로그 핸들러
            handlers = []
            
            # 콘솔 핸들러
            if log_config.get('console', True):
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(logging.Formatter(log_format))
                handlers.append(console_handler)
            
            # 파일 핸들러
            if log_file:
                # 로그 디렉토리 생성
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                    
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setFormatter(logging.Formatter(log_format))
                handlers.append(file_handler)
            
            # 로그 설정 적용
            logging.basicConfig(
                level=log_level,
                format=log_format,
                handlers=handlers
            )
            
            logger.debug("로깅 설정 초기화 완료")
            
        except Exception as e:
            logger.warning(f"로깅 설정 초기화 오류: {str(e)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        설정 값 가져오기
        
        Args:
            key: 설정 키 (점으로 구분된 중첩 키 지원)
            default: 키가 없을 경우 반환할 기본값
            
        Returns:
            설정 값 또는 기본값
        """
        # 점으로 구분된 중첩 키 처리
        if '.' in key:
            parts = key.split('.')
            
            # 현재 설정 위치
            current = self.settings
            
            # 키 경로 따라가기
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
                    
            return current
        else:
            # 단일 키
            return self.settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        설정 값 설정
        
        Args:
            key: 설정 키 (점으로 구분된 중첩 키 지원)
            value: 설정 값
        """
        # 점으로 구분된 중첩 키 처리
        if '.' in key:
            parts = key.split('.')
            
            # 현재 설정 위치
            current = self.settings
            
            # 중간 경로 생성
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
                
            # 마지막 부분에 값 설정
            current[parts[-1]] = value
        else:
            # 단일 키
            self.settings[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """
        모든 설정 가져오기
        
        Returns:
            모든 설정의 복사본
        """
        return self.settings.copy()
    
    def is_production(self) -> bool:
        """프로덕션 환경인지 확인"""
        return self.env == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """개발 환경인지 확인"""
        return self.env == Environment.DEVELOPMENT
    
    def is_testing(self) -> bool:
        """테스트 환경인지 확인"""
        return self.env == Environment.TESTING
    
    def load_secrets(self, secrets_file: str) -> None:
        """
        비밀 설정 파일 로드
        
        Args:
            secrets_file: 비밀 설정 파일 경로
        """
        if not os.path.exists(secrets_file):
            logger.warning(f"비밀 설정 파일을 찾을 수 없습니다: {secrets_file}")
            return
            
        try:
            file_ext = os.path.splitext(secrets_file)[1].lower()
            
            with open(secrets_file, 'r', encoding='utf-8') as f:
                if file_ext in ['.yaml', '.yml']:
                    try:
                        import yaml
                        secrets_data = yaml.safe_load(f)
                    except ImportError:
                        logger.warning("PyYAML 패키지가 설치되지 않았습니다. YAML 설정 파일을 로드할 수 없습니다.")
                        return
                elif file_ext == '.json':
                    secrets_data = json.load(f)
                else:
                    logger.warning(f"지원하지 않는 비밀 설정 파일 형식: {file_ext}")
                    return
            
            # 설정에 비밀 정보 병합
            if isinstance(secrets_data, dict):
                for key, value in secrets_data.items():
                    self.set(key, value)
            
            logger.info(f"비밀 설정 파일 로드 완료: {secrets_file}")
            
        except Exception as e:
            logger.error(f"비밀 설정 파일 로드 오류: {str(e)}")
    
    def __str__(self) -> str:
        """문자열 표현"""
        safe_settings = {}
        
        # 민감한 정보 마스킹
        def mask_sensitive(data, parent_key=''):
            if isinstance(data, dict):
                result = {}
                for key, value in data.items():
                    full_key = f"{parent_key}.{key}" if parent_key else key
                    
                    # 민감한 키 마스킹
                    if any(sensitive in full_key.lower() for sensitive in 
                            ['password', 'secret', 'token', 'key', 'auth']):
                        result[key] = '******'
                    elif isinstance(value, (dict, list)):
                        result[key] = mask_sensitive(value, full_key)
                    else:
                        result[key] = value
                return result
            elif isinstance(data, list):
                return [mask_sensitive(item, parent_key) for item in data]
            else:
                return data
        
        safe_settings = mask_sensitive(self.settings)
        
        return f"Config(env={self.env.name}, settings={json.dumps(safe_settings, indent=2)})"


# 기본 설정 인스턴스
config = Config()

def get_config() -> Config:
    """
    설정 인스턴스 가져오기
    
    Returns:
        설정 인스턴스
    """
    return config

def initialize_config(env: Union[Environment, str] = None, 
                      config_file: Optional[str] = None,
                      use_dotenv: bool = True) -> Config:
    """
    설정 초기화
    
    Args:
        env: 실행 환경
        config_file: 설정 파일 경로
        use_dotenv: .env 파일 로드 여부
        
    Returns:
        설정 인스턴스
    """
    global config
    config = Config(env=env, config_file=config_file, use_dotenv=use_dotenv)
    return config