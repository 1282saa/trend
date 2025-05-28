# Google Trends 수집기 사용 가이드

## 📊 개요

이 프로젝트에는 Google Trends API를 활용한 실시간 트렌드 데이터 수집 기능이 완전히 구현되어 있습니다. pytrends 라이브러리를 사용하여 다양한 트렌드 데이터를 수집할 수 있습니다.

## 🚀 주요 기능

### 1. 실시간 인기 검색어 수집

- 국가별 실시간 트렌드 키워드 수집
- 순위 정보 포함
- 캐싱을 통한 효율적인 데이터 관리

### 2. 키워드 관심도 분석

- 특정 키워드들의 시간별 관심도 변화
- 지역별 관심도 분포
- 연관 주제 및 쿼리 분석

### 3. 검색어 제안

- 키워드 기반 검색어 자동완성
- 관련 검색어 추천

### 4. 국가별 관심도 분석

- 특정 키워드의 국가별 인기도
- 글로벌 트렌드 분석

## 🛠️ 설치 및 설정

### 필수 라이브러리

```bash
pip install pytrends==4.9.0
```

### 환경 변수 (선택사항)

```bash
# .env 파일에 추가
LOCALE=ko          # 언어 설정 (기본: ko)
TIMEZONE=540       # 타임존 (기본: 540, GMT+9)
```

## 📝 CLI 사용법

### 기본 명령어

#### 1. 실시간 트렌드 수집

```bash
# 한국 실시간 트렌드 상위 20개
python3 main.py --google-trends

# 최대 10개만 수집
python3 main.py --google-trends --google-trends-max 10

# 미국 트렌드 수집
python3 main.py --google-trends --google-trends-country united_states
```

#### 2. 키워드 관심도 분석

```bash
# 단일 키워드 분석
python3 main.py --google-trends --google-trends-keyword "AI"

# 여러 키워드 비교 분석 (최대 5개)
python3 main.py --google-trends --google-trends-keyword "AI,인공지능,ChatGPT"

# 시간 범위 지정
python3 main.py --google-trends --google-trends-keyword "AI" --google-trends-timeframe "now 7-d"
```

#### 3. 출력 형식 지정

```bash
# JSON 형식으로 출력
python3 main.py --google-trends --output-format json

# CSV 형식으로 저장
python3 main.py --google-trends --output-format csv --output-path trends.csv

# Excel 형식으로 저장
python3 main.py --google-trends --output-format excel --output-path trends.xlsx
```

### 고급 사용법

#### 1. 다른 소스와 함께 수집

```bash
# 유튜브 + 구글 트렌드 함께 수집
python3 main.py --youtube --google-trends

# 모든 소스 수집
python3 main.py --all
```

#### 2. 데몬 모드로 주기적 수집

```bash
# 30분마다 구글 트렌드 수집
python3 main.py --google-trends --daemon --interval 1800
```

#### 3. 상세 로그와 함께 실행

```bash
python3 main.py --google-trends --verbose
```

## 🔧 CLI 옵션 상세

### Google Trends 관련 옵션

| 옵션                        | 설명                      | 기본값      | 예시                                    |
| --------------------------- | ------------------------- | ----------- | --------------------------------------- |
| `--google-trends`           | 구글 트렌드 수집 활성화   | False       | `--google-trends`                       |
| `--google-trends-country`   | 국가/지역 코드            | south_korea | `--google-trends-country united_states` |
| `--google-trends-max`       | 최대 결과 수              | 20          | `--google-trends-max 10`                |
| `--google-trends-keyword`   | 분석할 키워드 (쉼표 구분) | None        | `--google-trends-keyword "AI,ChatGPT"`  |
| `--google-trends-timeframe` | 시간 범위                 | now 1-d     | `--google-trends-timeframe "now 7-d"`   |

### 지원하는 국가 코드

- `south_korea` (한국)
- `united_states` (미국)
- `japan` (일본)
- `china` (중국)
- `united_kingdom` (영국)
- `germany` (독일)
- `france` (프랑스)
- 기타 pytrends에서 지원하는 모든 국가

### 시간 범위 형식

- `now 1-H` (지난 1시간)
- `now 4-H` (지난 4시간)
- `now 1-d` (지난 1일)
- `now 7-d` (지난 7일)
- `today 1-m` (지난 1개월)
- `today 3-m` (지난 3개월)
- `today 12-m` (지난 12개월)
- `today 5-y` (지난 5년)

## 📊 출력 데이터 형식

### 실시간 트렌드 데이터

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "sources": {
    "google_trends": [
      {
        "rank": 1,
        "keyword": "AI 뉴스",
        "query": "AI 뉴스",
        "country": "south_korea",
        "platform": "google_trends",
        "collected_at": "2024-01-15T10:30:00"
      }
    ]
  }
}
```

### 키워드 관심도 분석 데이터

```json
{
  "google_trends_keyword_analysis": {
    "keywords": ["AI", "인공지능"],
    "timeframe": "now 7-d",
    "geo": "KR",
    "interest_over_time": {
      "AI": [85, 92, 78, 95, 88],
      "인공지능": [72, 68, 81, 76, 79]
    },
    "interest_by_region": {
      "Seoul": { "AI": 100, "인공지능": 85 },
      "Busan": { "AI": 75, "인공지능": 92 }
    },
    "related_topics": {
      "AI": {
        "top": [
          { "topic_title": "ChatGPT", "value": 100 },
          { "topic_title": "Machine Learning", "value": 85 }
        ]
      }
    },
    "related_queries": {
      "AI": {
        "top": [
          { "query": "AI 뉴스", "value": 100 },
          { "query": "AI 주식", "value": 75 }
        ]
      }
    }
  }
}
```

## 🔍 실제 사용 예제

### 예제 1: 기본 트렌드 수집

```bash
python3 main.py --google-trends --google-trends-max 10 --output-format json --pretty
```

### 예제 2: 키워드 분석

```bash
python3 main.py --google-trends \
  --google-trends-keyword "AI,ChatGPT,GPT-4" \
  --google-trends-timeframe "now 7-d" \
  --output-format excel \
  --output-path ai_trends.xlsx
```

### 예제 3: 통합 데이터 수집

```bash
python3 main.py --all \
  --google-trends-max 15 \
  --youtube-max 20 \
  --news-max 10 \
  --output-format csv \
  --output-path comprehensive_trends.csv
```

### 예제 4: 데몬 모드

```bash
python3 main.py --google-trends \
  --daemon \
  --interval 3600 \
  --output-path hourly_trends.json \
  --verbose
```

## 🚨 주의사항

### 1. API 제한

- Google Trends는 무료 서비스이지만 요청 빈도 제한이 있습니다
- 너무 빈번한 요청 시 일시적으로 차단될 수 있습니다
- 캐싱 기능을 활용하여 중복 요청을 방지합니다

### 2. 데이터 정확성

- 실시간 트렌드는 지역과 시간에 따라 변동됩니다
- 상대적 인기도로 표시되므로 절대적 수치가 아닙니다

### 3. 키워드 제한

- 한 번에 최대 5개의 키워드만 비교 분석 가능합니다
- 키워드는 영어와 한국어 모두 지원됩니다

## 🔧 문제 해결

### 1. pytrends 설치 오류

```bash
pip install --upgrade pytrends
```

### 2. 네트워크 오류

- 프록시 환경에서는 추가 설정이 필요할 수 있습니다
- VPN 사용 시 지역 설정을 확인하세요

### 3. 데이터 수집 실패

- 로그를 확인하여 구체적인 오류 메시지를 확인하세요
- `--verbose` 옵션으로 상세 로그를 활성화하세요

## 📈 성능 최적화

### 1. 캐싱 활용

- 실시간 트렌드: 30분 캐싱
- 키워드 관심도: 1시간 캐싱
- 검색어 제안: 24시간 캐싱

### 2. 배치 처리

- 여러 키워드를 한 번에 분석하여 API 호출 최소화
- 데몬 모드로 정기적 수집 자동화

### 3. 메모리 관리

- 대용량 데이터 수집 시 스트리밍 방식 사용
- 불필요한 데이터는 즉시 정리

## 🤝 기여하기

버그 리포트나 기능 개선 제안은 언제든 환영합니다!

---

**마지막 업데이트**: 2024년 1월 15일
