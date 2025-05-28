"""
TrendPulse 웹 애플리케이션 서버

실시간 트렌드 데이터를 수집하고 웹 인터페이스를 통해 제공하는 Flask 웹 서버
"""
import os
import json
import logging
import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS

from collectors.trend_collector import TrendCollector
from utils.config import get_config, initialize_config
from utils.error_handler import ErrorHandler, StructuredLogger, handle_errors

# 설정 초기화
config = initialize_config()

# 로깅 설정
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
logger = StructuredLogger('trendpulse_server', log_dir=log_dir, level=logging.INFO)

# 오류 처리기 설정
error_handler = ErrorHandler(log_dir=os.path.join(log_dir, 'errors'))

# Flask 앱 및 SocketIO 초기화
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 트렌드 수집기 초기화
trend_collector = TrendCollector()

# 데이터 캐시
data_cache = {
    'last_update': None,
    'hot_keywords': [],
    'topics': []
}

# 업데이트 간격 (초)
UPDATE_INTERVAL = config.get('update_interval', 300)  # 기본 5분

@app.route('/')
def index():
    """메인 페이지 렌더링"""
    return render_template('index.html')

@app.route('/api/keywords/hot')
@handle_errors(operation="get_hot_keywords")
def get_hot_keywords():
    """인기 키워드 API"""
    if not data_cache['hot_keywords'] or is_cache_expired():
        # 캐시가 비어있거나 만료되었을 경우 새로 수집
        update_cache()
    
    max_results = request.args.get('max', default=20, type=int)
    platform = request.args.get('platform', default=None, type=str)
    
    if platform:
        filtered_keywords = [
            kw for kw in data_cache['hot_keywords'] 
            if platform in kw.get('sources', [])
        ]
    else:
        filtered_keywords = data_cache['hot_keywords']
    
    return jsonify({
        'success': True,
        'timestamp': data_cache['last_update'],
        'data': filtered_keywords[:max_results]
    })

@app.route('/api/topics')
@handle_errors(operation="get_topics")
def get_topics():
    """AI 인사이트 토픽 API"""
    if not data_cache['topics'] or is_cache_expired():
        # 캐시가 비어있거나 만료되었을 경우 새로 수집
        update_cache()
    
    max_results = request.args.get('max', default=5, type=int)
    
    return jsonify({
        'success': True,
        'timestamp': data_cache['last_update'],
        'data': data_cache['topics'][:max_results]
    })

@app.route('/api/keywords/details/<keyword>')
@handle_errors(operation="get_keyword_details")
def get_keyword_details(keyword):
    """특정 키워드에 대한 상세 정보 API"""
    # 실제 구현에서는 데이터베이스나 추가 API 호출로 상세 정보를 가져와야 함
    # 현재는 예시 데이터 반환
    try:
        # 키워드 찾기
        keyword_data = next(
            (kw for kw in data_cache['hot_keywords'] if kw['keyword'] == keyword),
            None
        )
        
        if not keyword_data:
            return jsonify({
                'success': False,
                'error': '키워드를 찾을 수 없습니다.'
            }), 404
        
        # 예시 상세 데이터
        details = {
            'keyword': keyword,
            'sources': keyword_data.get('sources', []),
            'score': keyword_data.get('score', 0),
            'total_score': keyword_data.get('score', 0) * 1.5,  # 예시 계산
            'urls': [
                f"https://search.naver.com/search.naver?query={keyword}",
                f"https://www.google.com/search?q={keyword}",
                f"https://www.youtube.com/results?search_query={keyword}"
            ],
            'metadata': {
                'category': '일반',
                'views': 12500,
                'description': f'{keyword}에 대한 상세 설명입니다.',
                'published_at': datetime.now().isoformat()
            }
        }
        
        return jsonify({
            'success': True,
            'data': details
        })
        
    except Exception as e:
        logger.error(f"키워드 상세 정보 조회 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/keywords/history/<keyword>')
@handle_errors(operation="get_keyword_history")
def get_keyword_history(keyword):
    """키워드의 시간별 인기도 이력 API"""
    # 실제 구현에서는 데이터베이스에서 이력 데이터를 가져와야 함
    # 현재는 예시 데이터 반환
    try:
        # 임의의 시간별 데이터 생성
        history = []
        now = datetime.now()
        
        for i in range(24):
            history.append({
                'timestamp': (now.replace(hour=i, minute=0, second=0, microsecond=0)).isoformat(),
                'score': 50 + (i * 5) % 50  # 임의의 인기도 점수
            })
        
        return jsonify({
            'success': True,
            'data': {
                'keyword': keyword,
                'history': history
            }
        })
        
    except Exception as e:
        logger.error(f"키워드 이력 조회 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def is_cache_expired():
    """캐시가 만료되었는지 확인"""
    if not data_cache['last_update']:
        return True
    
    last_update = datetime.fromisoformat(data_cache['last_update'])
    seconds_since_update = (datetime.now() - last_update).total_seconds()
    
    return seconds_since_update > UPDATE_INTERVAL

@handle_errors(operation="collect_trends")
async def collect_trends():
    """모든 소스에서 트렌드 수집"""
    logger.info("트렌드 데이터 수집 시작")
    
    try:
        # 모든 트렌드 수집
        results = await trend_collector.collect_all_trends()
        
        # 키워드 데이터 추출
        hot_keywords = []
        
        # 유튜브 트렌드 변환
        if 'youtube' in results['sources']:
            for idx, video in enumerate(results['sources']['youtube']):
                hot_keywords.append({
                    'rank': idx + 1,
                    'keyword': video.get('title', ''),
                    'query': video.get('title', ''),
                    'sources': ['youtube'],
                    'score': 100 - idx,  # 임의의 점수
                    'platform': 'youtube',
                    'collected_at': datetime.now().isoformat()
                })
        
        # 포털 인기 검색어 변환
        if 'portal' in results['sources']:
            for source, items in results['sources']['portal'].items():
                for item in items:
                    # 중복 키워드 확인
                    existing_kw = next(
                        (kw for kw in hot_keywords if kw['keyword'].lower() == item['keyword'].lower()),
                        None
                    )
                    
                    if existing_kw:
                        # 이미 있는 키워드면 소스 추가
                        if source not in existing_kw['sources']:
                            existing_kw['sources'].append(source)
                            existing_kw['score'] += (100 - item['rank'])  # 점수 합산
                    else:
                        # 새 키워드 추가
                        hot_keywords.append({
                            'rank': item.get('rank', 0),
                            'keyword': item.get('keyword', ''),
                            'query': item.get('keyword', ''),
                            'sources': [source],
                            'score': 100 - item.get('rank', 0),  # 임의의 점수
                            'platform': source,
                            'collected_at': datetime.now().isoformat()
                        })
        
        # 구글 트렌드 변환
        if 'google_trends' in results['sources']:
            for item in results['sources']['google_trends']:
                # 중복 키워드 확인
                existing_kw = next(
                    (kw for kw in hot_keywords if kw['keyword'].lower() == item['keyword'].lower()),
                    None
                )
                
                if existing_kw:
                    # 이미 있는 키워드면 소스 추가
                    if 'google' not in existing_kw['sources']:
                        existing_kw['sources'].append('google')
                        existing_kw['score'] += (100 - item['rank'])  # 점수 합산
                else:
                    # 새 키워드 추가
                    hot_keywords.append({
                        'rank': item.get('rank', 0),
                        'keyword': item.get('keyword', ''),
                        'query': item.get('query', ''),
                        'sources': ['google'],
                        'score': 100 - item.get('rank', 0),  # 임의의 점수
                        'platform': 'google_trends',
                        'collected_at': datetime.now().isoformat()
                    })
        
        # 뉴스 트렌드 변환
        if 'news' in results['sources']:
            for source, items in results['sources']['news'].items():
                for idx, item in enumerate(items):
                    # 제목에서 키워드 추출 (실제로는 더 복잡한 로직 필요)
                    title = item.get('title', '')
                    
                    hot_keywords.append({
                        'rank': idx + 1,
                        'keyword': title,
                        'query': title,
                        'sources': ['news', source],
                        'score': 100 - idx,  # 임의의 점수
                        'platform': f'news_{source}',
                        'collected_at': datetime.now().isoformat()
                    })
        
        # 점수 기준으로 정렬
        hot_keywords.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # 순위 재할당
        for i, kw in enumerate(hot_keywords):
            kw['rank'] = i + 1
        
        # AI 인사이트 토픽 생성 (실제로는 LLM 등을 활용하여 분석)
        topics = generate_topics(hot_keywords)
        
        # 캐시 업데이트
        data_cache['hot_keywords'] = hot_keywords
        data_cache['topics'] = topics
        data_cache['last_update'] = datetime.now().isoformat()
        
        # 소켓을 통해 클라이언트에 실시간 업데이트 전송
        socketio.emit('trends_update', {
            'hot_keywords': hot_keywords[:20],  # 상위 20개만
            'topics': topics
        })
        
        logger.info(f"트렌드 데이터 업데이트 완료: {len(hot_keywords)} 키워드, {len(topics)} 토픽")
        return hot_keywords, topics
        
    except Exception as e:
        logger.error(f"트렌드 수집 오류: {str(e)}")
        return [], []

def generate_topics(hot_keywords):
    """
    인기 키워드를 기반으로 토픽 생성
    실제 구현에서는 LLM 등을 활용하여 더 정교한 분석 필요
    """
    # 예시 토픽
    topics = [
        {
            'topic': '인공지능 발전 동향',
            'keywords': ['AI', '인공지능', '머신러닝', '딥러닝'],
            'hook_copies': [
                '최신 AI 기술이 산업 전반에 미치는 영향과 향후 전망',
                '인공지능 윤리와 규제에 대한 글로벌 동향 분석',
                '생성형 AI의 발전과 창의성의 새로운 정의'
            ]
        },
        {
            'topic': '글로벌 경제 동향',
            'keywords': ['경제', '주식', '금리', '인플레이션'],
            'hook_copies': [
                '글로벌 경기 침체 우려와 각국의 대응 정책',
                '금리 인상이 부동산 시장에 미치는 영향',
                '인플레이션 완화를 위한 중앙은행들의 전략'
            ]
        },
        {
            'topic': '디지털 트랜스포메이션',
            'keywords': ['디지털', '혁신', '클라우드', '데이터'],
            'hook_copies': [
                '기업의 디지털 전환 성공 사례와 교훈',
                '데이터 기반 의사결정의 중요성과 실행 방안',
                '클라우드 네이티브 환경으로의 전환 전략'
            ]
        },
        {
            'topic': '소셜 미디어 트렌드',
            'keywords': ['소셜미디어', '인플루언서', '콘텐츠', '마케팅'],
            'hook_copies': [
                '쇼트폼 콘텐츠의 부상과 브랜드 마케팅 전략',
                '인플루언서 마케팅의 효과적인 활용 방안',
                '소셜 미디어 알고리즘 변화에 대응하는 콘텐츠 전략'
            ]
        },
        {
            'topic': '지속가능한 미래',
            'keywords': ['ESG', '기후변화', '친환경', '탄소중립'],
            'hook_copies': [
                'ESG 경영이 기업 가치에 미치는 영향과 투자 전망',
                '기후 위기 대응을 위한 혁신 기술과 정책 동향',
                '순환경제로의 전환: 기업과 소비자의 역할'
            ]
        }
    ]
    
    return topics

def update_cache():
    """캐시 데이터 업데이트"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    hot_keywords, topics = loop.run_until_complete(collect_trends())
    loop.close()
    return hot_keywords, topics

@socketio.on('connect')
def handle_connect():
    """Socket.IO 연결 처리"""
    logger.info(f"클라이언트 연결됨: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Socket.IO 연결 해제 처리"""
    logger.info(f"클라이언트 연결 해제: {request.sid}")

def start_background_tasks():
    """백그라운드 작업 시작"""
    # 처음 한 번 데이터 수집
    update_cache()
    
    # 주기적 업데이트 작업 등록
    def periodic_update():
        while True:
            socketio.sleep(UPDATE_INTERVAL)
            update_cache()
    
    socketio.start_background_task(periodic_update)

if __name__ == '__main__':
    # 백그라운드 작업 시작
    start_background_tasks()
    
    # 웹 서버 실행
    port = int(os.getenv('PORT', 5000))
    debug = config.get('app.debug', False)
    
    logger.info(f"TrendPulse 웹 서버 시작 (포트: {port}, 디버그: {debug})")
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)