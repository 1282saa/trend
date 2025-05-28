# 실시간 트렌드 수집기

다양한 소스(유튜브, 뉴스, 포털 사이트, 구글 트렌드)에서 인기 트렌드 데이터를 수집하는 파이썬 도구입니다.

## 개요

이 프로젝트는 다음과 같은 데이터를 수집할 수 있습니다:

1. **유튜브 인기 동영상**: YouTube API를 통한 인기 동영상 목록
2. **뉴스 인기 기사**: 네이버, 다음, 구글 뉴스의 인기 기사
3. **포털 인기 검색어**: 네이버, 다음, 줌, 네이트의 실시간 인기 검색어
4. **구글 트렌드**: 구글 트렌드의 실시간 인기 검색어 및 키워드 분석

## 웹 인터페이스

이 프로젝트는 시각적인 웹 인터페이스(TrendPulse)를 통해 실시간 트렌드 데이터를 편리하게 확인할 수 있습니다.

### 웹 애플리케이션 실행하기

간단한 스크립트를 사용하여 웹 인터페이스를 시작할 수 있습니다:

```bash
./run_webapp.sh
```

또는 직접 다음 명령어를 실행할 수도 있습니다:

```bash
# 필요한 패키지 설치
pip install -r requirements.txt

# 웹 서버 실행
python app.py
```

서버가 시작되면 웹 브라우저에서 [http://localhost:5000](http://localhost:5000)으로 접속하여 웹 인터페이스를 확인할 수 있습니다.

### 웹 인터페이스 주요 기능

1. **실시간 트렌드 대시보드**: 모든 소스의 통합 트렌드 데이터를 직관적인 카드 형태로 제공
2. **플랫폼별 필터링**: 특정 플랫폼(YouTube, 네이버, 구글 등)별로 트렌드 필터링
3. **실시간 업데이트**: Socket.IO를 통한 데이터 실시간 업데이트
4. **트렌드 상세 정보**: 각 트렌드 키워드에 대한 상세 정보 및 관련 링크 제공
5. **AI 인사이트**: 트렌드 데이터를 기반으로 한 주요 토픽 및 인사이트 제공
6. **다크/라이트 테마**: 사용자 선호에 따른 테마 변경 기능
7. **트렌드 저장**: 관심 있는 트렌드를 저장하고 나중에 확인하는 기능

### API 엔드포인트

웹 서버는 다음과 같은 API 엔드포인트를 제공합니다:

- `GET /api/keywords/hot`: 인기 키워드 목록 반환
- `GET /api/topics`: AI 인사이트 토픽 목록 반환
- `GET /api/keywords/details/<keyword>`: 특정 키워드에 대한 상세 정보 반환
- `GET /api/keywords/history/<keyword>`: 키워드의 시간별 인기도 이력 반환

## 설치 방법

### 요구사항

- Python 3.7 이상
- pip (패키지 관리자)

### 설치 단계

1. 저장소 클론:

```bash
git clone <repository_url>
cd <repository_directory>
```

2. 필요한 패키지 설치:

```bash
pip install -r requirements.txt
```

3. 환경 변수 설정:

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 필요한 API 키를 설정하세요.

## API 키 발급 방법

### 1. YouTube API 키

1. [Google Cloud Console](https://console.cloud.google.com/)에 로그인
2. 프로젝트 생성
3. YouTube Data API v3 활성화
4. API 키 생성
5. `.env` 파일의 `YOUTUBE_API_KEY`에 발급받은 키 입력

### 2. 네이버 API 키 (선택 사항)

1. [네이버 개발자 센터](https://developers.naver.com/main/)에 로그인
2. 애플리케이션 등록
3. 네이버 검색 API 선택
4. `.env` 파일에 발급받은 `NAVER_CLIENT_ID`와 `NAVER_CLIENT_SECRET` 입력

## 기본 사용법

### 모든 소스에서 데이터 수집

```bash
python main.py --all
```

### 특정 소스에서만 데이터 수집

```bash
python main.py --youtube --news
```

### 유튜브 카테고리별 데이터 수집

```bash
python main.py --youtube --youtube-by-category --youtube-max 100
```

### 포털 통합 인기 검색어 수집

```bash
python main.py --portal --portal-combine --portal-min-sources 2
```

### 구글 트렌드 데이터 수집

```bash
python main.py --google-trends
```

### 구글 트렌드 키워드 분석

```bash
python main.py --google-trends --google-trends-keyword "인공지능,챗GPT" --google-trends-timeframe "today 3-m"
```

### 파일로 결과 저장

```bash
python main.py --all --output results/trends --format json --pretty
```

### 데몬 모드로 주기적 수집

```bash
python main.py --all --daemon --interval 600 --runs 10
```

## 명령줄 옵션

### 수집 소스 선택

- `--youtube`: 유튜브 인기 동영상 수집
- `--news`: 뉴스 인기 기사 수집
- `--portal`: 포털 인기 검색어 수집
- `--google-trends`: 구글 트렌드 데이터 수집
- `--all`: 모든 소스에서 데이터 수집 (기본값)

### 유튜브 옵션

- `--youtube-region`: 유튜브 지역 코드 (기본값: KR)
- `--youtube-max`: 유튜브 최대 결과 수 (기본값: 50)
- `--youtube-by-category`: 유튜브 카테고리별 수집

### 뉴스 옵션

- `--news-sources`: 수집할 뉴스 소스 (콤마로 구분, 기본값: naver,daum,google)
- `--news-category`: 뉴스 카테고리 (기본값: 전체)
- `--news-max`: 소스별 최대 뉴스 수 (기본값: 30)

### 포털 옵션

- `--portal-sources`: 수집할 포털 소스 (콤마로 구분, 기본값: naver,daum,zum,nate)
- `--portal-max`: 소스별 최대 검색어 수 (기본값: 20)
- `--portal-combine`: 여러 포털의 인기 검색어 통합 순위화
- `--portal-min-sources`: 키워드 통합 시 최소 등장 소스 수 (기본값: 2)

### 구글 트렌드 옵션

- `--google-trends-country`: 구글 트렌드 국가 코드 (기본값: south_korea)
- `--google-trends-max`: 구글 트렌드 최대 결과 수 (기본값: 20)
- `--google-trends-keyword`: 구글 트렌드에서 분석할 키워드 (콤마로 구분, 최대 5개)
- `--google-trends-timeframe`: 구글 트렌드 시간 범위 (기본값: now 1-d)

### 출력 옵션

- `--output`: 결과 저장 파일 경로 (없으면 화면에 출력)
- `--format`: 출력 형식 (json, csv, excel 중 하나, 기본값: json)
- `--pretty`: JSON 출력을 보기 좋게 포맷팅

### 실행 모드

- `--daemon`: 데몬 모드로 실행 (주기적 수집)
- `--interval`: 데몬 모드에서 수집 간격(초) (기본값: 300)
- `--runs`: 데몬 모드에서 실행 횟수 (0=무한)

### 기타 옵션

- `--verbose`: 상세 로깅 활성화

## 프로젝트 구조

```
project/
├── collectors/
│   ├── __init__.py
│   ├── youtube_collector.py     # 유튜브 인기 동영상 수집
│   ├── news_collector.py        # 뉴스 인기 기사 수집
│   ├── portal_collector.py      # 포털 인기 검색어 수집
│   ├── google_trends_collector.py # 구글 트렌드 데이터 수집
│   └── trend_collector.py       # 통합 수집기
├── utils/
│   ├── __init__.py
│   ├── cache.py                 # 캐싱 유틸리티
│   ├── http_client.py           # HTTP 클라이언트
│   └── browser.py               # 브라우저 자동화 유틸리티
├── static/
│   ├── css/                     # CSS 스타일시트
│   └── js/                      # JavaScript 파일
├── templates/                   # HTML 템플릿
├── app.py                       # 웹 애플리케이션 서버
├── main.py                      # 명령줄 인터페이스
├── run_webapp.sh                # 웹 앱 실행 스크립트
├── requirements.txt             # 패키지 의존성
├── .env.example                 # 환경 변수 템플릿
└── README.md                    # 프로젝트 설명
```

## 구글 트렌드 기능 사용법

### 실시간 인기 검색어 가져오기

```bash
python main.py --google-trends
```

### 여러 국가의 트렌드 비교하기

```bash
# 미국 트렌드
python main.py --google-trends --google-trends-country "united_states"

# 일본 트렌드
python main.py --google-trends --google-trends-country "japan"
```

### 특정 키워드 분석하기

```bash
# 최근 하루 동안의 AI와 챗GPT 검색 관심도 비교
python main.py --google-trends --google-trends-keyword "AI,챗GPT" --google-trends-timeframe "now 1-d"

# 최근 3개월간의 키워드 관심도 트렌드
python main.py --google-trends --google-trends-keyword "BTS,NewJeans,aespa" --google-trends-timeframe "today 3-m"
```

### 모든 소스에서 통합 데이터 수집하기

```bash
python main.py --all --pretty
```

## 라이선스

MIT License
