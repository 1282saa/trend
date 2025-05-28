#!/bin/bash

# TrendPulse 웹 애플리케이션 실행 스크립트

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 로고 출력
echo -e "${PURPLE}"
echo "==============================================="
echo "  _____                    _ _____      _     "
echo " |_   _| __ ___ _ __   __| |  __ \    | |    "
echo "   | || '__/ _ \ '_ \ / _\` | |__) |_ _| |___ "
echo "   | || | |  __/ | | | (_| |  ___/ _\` | / __|"
echo "   |_||_|  \___|_| |_|\__,_|_|   \__,_|_\___|"
echo ""
echo "==============================================="
echo -e "${NC}"

echo -e "${CYAN}웹 애플리케이션 시작 준비 중...${NC}"

# 가상환경 확인 및 활성화
if [ -d "venv" ]; then
    echo -e "${BLUE}가상환경 활성화...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}가상환경이 없습니다. 새 가상환경을 생성합니다...${NC}"
    python3 -m venv venv
    source venv/bin/activate
fi

# 필요한 패키지 설치
echo -e "${BLUE}필요한 패키지 설치 중...${NC}"
pip install -r requirements.txt

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}.env 파일이 없습니다. 예제를 복사합니다...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}.env.example를 .env로 복사했습니다. 필요한 경우 .env 파일을 수정하세요.${NC}"
    else
        echo -e "${RED}.env.example 파일도 없습니다. 환경 변수 설정이 필요할 수 있습니다.${NC}"
    fi
fi

# 웹 애플리케이션 실행
echo -e "${GREEN}TrendPulse 웹 애플리케이션을 시작합니다...${NC}"
echo -e "${YELLOW}웹 브라우저에서 http://localhost:5000 으로 접속하세요.${NC}"
python3 app.py

# 스크립트 종료 시 메시지
echo -e "${PURPLE}TrendPulse 웹 애플리케이션이 종료되었습니다.${NC}" 