# 🔥 TrendPulse - 실시간 트렌드 분석 플랫폼

TrendPulse는 여러 플랫폼(YouTube, 네이버, 연합뉴스 등)에서 실시간 트렌드를 수집하고 AI로 분석하여 인사이트를 제공하는 웹 서비스입니다.

## ✨ 주요 기능

- **다중 플랫폼 트렌드 수집**: YouTube, 네이버, 연합뉴스, Google Trends, Daum 등
- **실시간 업데이트**: WebSocket을 통한 실시간 데이터 스트리밍
- **AI 인사이트**: ChatGPT를 활용한 트렌드 분석 및 카피 생성
- **원본 링크 연결**: 각 트렌드의 원본 콘텐츠로 직접 이동
- **반응형 디자인**: 모바일/데스크톱 모두 지원
- **다크모드 지원**: 사용자 선호에 따른 테마 전환

## 🛠 기술 스택

### Backend
- Python 3.8+
- Flask + Flask-SocketIO
- aiohttp (비동기 HTTP 요청)
- OpenAI API (ChatGPT)

### Frontend
- Vanilla JavaScript
- Chart.js (데이터 시각화)
- Socket.io Client
- CSS3 (Glassmorphism, Animations)

## 📦 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/trendpulse.git
cd trendpulse
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정
`.env.example` 파일을 `.env`로 복사하고 필요한 API 키를 입력합니다:

```bash
cp .env.example .env
```

필요한 API 키:
- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- `YOUTUBE_API_KEY`: YouTube Data API v3 키
- `NAVER_CLIENT_ID`: 네이버 검색 API 클라이언트 ID
- `NAVER_CLIENT_SECRET`: 네이버 검색 API 시크릿

## 🚀 실행 방법

```bash
python api_server.py
```

웹 브라우저에서 http://localhost:5000 접속

## 📁 프로젝트 구조

```
trendpulse/
├── api_server.py           # 메인 서버 파일
├── backend/
│   ├── trend_collector.py  # 통합 트렌드 수집기
│   ├── collectors/
│   │   ├── base_collectors.py     # 기본 수집기 클래스
│   │   └── youtube_collector.py   # YouTube 전용 수집기
│   └── utils/
│       └── llm_insights.py        # AI 인사이트 생성
├── static/
│   ├── css/
│   │   └── style.css      # 스타일시트
│   └── js/
│       └── app.js         # 프론트엔드 로직
├── templates/
│   └── index.html         # 메인 페이지
├── results/               # 수집 결과 저장 (gitignore)
├── requirements.txt       # Python 패키지 목록
├── .env.example          # 환경변수 예시
└── README.md             # 프로젝트 문서

```

## 🔌 API 엔드포인트

### 트렌드 API
- `GET /api/keywords/hot` - 인기 키워드 목록 (최대 100개)
- `GET /api/keywords/history/<keyword>` - 키워드 히스토리
- `GET /api/keywords/details/<keyword>` - 키워드 상세 정보 및 원본 링크
- `GET /api/topics` - AI 분석 토픽
- `GET /api/status` - 시스템 상태

### WebSocket 이벤트
- `connect` - 연결 확인
- `trends_update` - 실시간 트렌드 업데이트
- `request_update` - 즉시 업데이트 요청

## 🎨 주요 UI 기능

- **플랫폼 필터**: 특정 플랫폼의 트렌드만 필터링
- **실시간 티커**: 상단에 인기 키워드 흐름 표시
- **트렌드 카드**: 각 트렌드의 상세 정보와 차트
- **원본 보기**: 트렌드의 원본 페이지로 직접 이동
- **저장 기능**: 관심 트렌드 북마크
- **다크모드**: 눈의 피로를 줄이는 다크 테마

## 📊 데이터 수집 주기

- 자동 수집: 5분마다
- 수동 새로고침: 우측 상단 새로고침 버튼
- 실시간 업데이트: WebSocket 연결 시

## 🤝 기여 방법

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다.

## 👥 문의

프로젝트 관련 문의사항은 이슈를 통해 남겨주세요.

---
Made with ❤️ by 서울경제신문