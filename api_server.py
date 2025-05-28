from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
import json
import os
import asyncio
from threading import Thread
import time
from backend.trend_collector import ImprovedTrendCollector, analyze_trends
from backend.utils.llm_insights import cluster_topics_with_chatgpt, generate_hook_copies

app = Flask(__name__, 
            static_folder='static', 
            static_url_path='/static',
            template_folder='templates')
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 전역 데이터 저장소
trends_cache = {
    "hot_keywords": [],
    "topics": [],
    "last_update": None,
    "bookmarks": []
}

# 백그라운드 트렌드 수집 스레드
collector_thread = None
is_collecting = False

def background_collector():
    """백그라운드에서 주기적으로 트렌드를 수집"""
    global trends_cache, is_collecting
    
    async def collect_trends():
        while is_collecting:
            try:
                print(f"[{datetime.now()}] 트렌드 수집 시작...")
                
                # 개선된 수집기 사용
                async with ImprovedTrendCollector() as collector:
                    result = await collector.collect_all()
                    
                    # 분석
                    analysis = analyze_trends(result['trends'])
                    
                    # 핫 키워드 추출
                    hot_keywords = analysis['hot_keywords'][:30]
                    
                    # 키워드 정제
                    keywords_for_clustering = [kw["keyword"] for kw in hot_keywords[:20]]
                    keywords_clean = normalize(deduplicate(keywords_for_clustering))
                    keywords_final = combine_similar_keywords(keywords_clean)
                    
                    # 토픽 클러스터링 (API 키가 있는 경우)
                    if os.getenv("OPENAI_API_KEY") and len(keywords_final) >= 5:
                        clusters = cluster_topics_with_chatgpt(
                            keywords_final, 
                            n_clusters=min(5, len(keywords_final) // 2)
                        )
                        
                        # 각 토픽에 대한 훅 카피 생성
                        topics_with_hooks = []
                        for cluster in clusters:
                            topic = cluster.get("topic", "")
                            keywords = cluster.get("keywords", [])
                            hook_copies = generate_hook_copies(topic, n=3)
                            
                            topics_with_hooks.append({
                                "id": f"topic_{len(topics_with_hooks)+1}",
                                "topic": topic,
                                "keywords": keywords,
                                "hook_copies": hook_copies,
                                "created_at": datetime.now().isoformat()
                            })
                        
                        trends_cache["topics"] = topics_with_hooks
                    
                    # 캐시 업데이트
                    trends_cache["hot_keywords"] = hot_keywords
                    trends_cache["last_update"] = datetime.now().isoformat()
                    
                    # 트렌드 원본 데이터도 저장 (원본 링크 접근용)
                    app._latest_trends = result
                    
                    # WebSocket으로 실시간 업데이트 전송
                    socketio.emit('trends_update', {
                        "hot_keywords": hot_keywords[:10],
                        "topics": trends_cache["topics"][:5],
                        "timestamp": trends_cache["last_update"]
                    })
                    
                    print(f"[{datetime.now()}] 트렌드 수집 완료")
                    
            except Exception as e:
                print(f"트렌드 수집 오류: {e}")
            
            # 5분 대기
            await asyncio.sleep(300)
    
    # 비동기 루프 실행
    asyncio.run(collect_trends())

# 메인 페이지 라우트
@app.route('/')
def index():
    return render_template('index.html')

# API 엔드포인트들

@app.route('/api/keywords/hot')
def get_hot_keywords():
    """인기 키워드 목록 반환"""
    n = request.args.get('n', 30, type=int)
    keywords = trends_cache["hot_keywords"][:n]
    
    return jsonify({
        "success": True,
        "data": keywords,
        "last_update": trends_cache["last_update"],
        "total": len(keywords)
    })

@app.route('/api/topics')
def get_topics():
    """토픽 목록 반환"""
    topics = trends_cache["topics"]
    
    return jsonify({
        "success": True,
        "data": topics,
        "last_update": trends_cache["last_update"],
        "total": len(topics)
    })

@app.route('/api/topics/<topic_id>/hooks')
def get_topic_hooks(topic_id):
    """특정 토픽의 훅 카피 반환"""
    topic = next((t for t in trends_cache["topics"] if t["id"] == topic_id), None)
    
    if not topic:
        return jsonify({
            "success": False,
            "error": "Topic not found"
        }), 404
    
    return jsonify({
        "success": True,
        "data": {
            "topic": topic["topic"],
            "hook_copies": topic["hook_copies"]
        }
    })

@app.route('/api/bookmarks', methods=['GET', 'POST', 'DELETE'])
def handle_bookmarks():
    """북마크 CRUD 처리"""
    if request.method == 'GET':
        return jsonify({
            "success": True,
            "data": trends_cache["bookmarks"]
        })
    
    elif request.method == 'POST':
        data = request.json
        bookmark = {
            "id": f"bookmark_{len(trends_cache['bookmarks'])+1}",
            "topic": data.get("topic"),
            "copy": data.get("copy"),
            "created_at": datetime.now().isoformat()
        }
        trends_cache["bookmarks"].append(bookmark)
        
        return jsonify({
            "success": True,
            "data": bookmark
        })
    
    elif request.method == 'DELETE':
        bookmark_id = request.args.get('id')
        trends_cache["bookmarks"] = [
            b for b in trends_cache["bookmarks"] 
            if b["id"] != bookmark_id
        ]
        
        return jsonify({
            "success": True,
            "message": "Bookmark deleted"
        })

@app.route('/api/keywords/history/<keyword>')
def get_keyword_history(keyword):
    """키워드의 7일 추이 데이터 (모의)"""
    # 실제로는 DB에서 가져와야 하지만, 여기서는 모의 데이터 생성
    history = []
    for i in range(7, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        history.append({
            "date": date,
            "score": 50 + (7-i) * 10 + (hash(keyword+date) % 20)
        })
    
    return jsonify({
        "success": True,
        "data": {
            "keyword": keyword,
            "history": history
        }
    })

@app.route('/api/keywords/details/<keyword>')
def get_keyword_details(keyword):
    """키워드 상세 정보 및 원본 링크 조회"""
    try:
        # 현재 수집된 트렌드에서 해당 키워드 찾기
        if hasattr(app, '_latest_trends'):
            all_trends = app._latest_trends.get('trends', [])
            
            # 해당 키워드와 관련된 모든 트렌드 찾기
            related_trends = [
                trend for trend in all_trends 
                if trend.get('keyword', '').lower() == keyword.lower()
            ]
            
            if related_trends:
                # 모든 URL 수집
                urls = []
                sources = set()
                total_score = 0
                metadata = {}
                
                for trend in related_trends:
                    if trend.get('url'):
                        urls.append(trend['url'])
                    sources.add(trend.get('source', ''))
                    total_score += trend.get('score', 0)
                    
                    # 메타데이터 수집
                    if trend.get('metadata'):
                        metadata.update(trend['metadata'])
                
                return jsonify({
                    'success': True,
                    'data': {
                        'keyword': keyword,
                        'urls': urls,
                        'sources': list(sources),
                        'total_score': total_score,
                        'metadata': metadata,
                        'related_count': len(related_trends)
                    }
                })
        
        # 키워드를 찾을 수 없는 경우
        return jsonify({
            'success': False,
            'error': 'Keyword not found',
            'data': {
                'keyword': keyword,
                'urls': [],
                'sources': [],
                'total_score': 0,
                'metadata': {},
                'related_count': 0
            }
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/status')
def get_status():
    """시스템 상태 반환"""
    return jsonify({
        "success": True,
        "data": {
            "is_collecting": is_collecting,
            "last_update": trends_cache["last_update"],
            "total_keywords": len(trends_cache["hot_keywords"]),
            "total_topics": len(trends_cache["topics"]),
            "api_key_configured": bool(os.getenv("OPENAI_API_KEY"))
        }
    })

# WebSocket 이벤트
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'data': 'Connected to trend server'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('request_update')
def handle_request_update():
    """클라이언트의 즉시 업데이트 요청"""
    emit('trends_update', {
        "hot_keywords": trends_cache["hot_keywords"][:10],
        "topics": trends_cache["topics"][:5],
        "timestamp": trends_cache["last_update"]
    })

# 초기 데이터 로드
def load_initial_data():
    """서버 시작 시 초기 데이터 로드"""
    global trends_cache
    
    # 저장된 데이터가 있으면 로드
    if os.path.exists('results/api_cache.json'):
        with open('results/api_cache.json', 'r', encoding='utf-8') as f:
            trends_cache.update(json.load(f))
    
    # 데이터가 없거나 오래된 경우 즉시 수집
    if not trends_cache["last_update"] or \
       datetime.now() - datetime.fromisoformat(trends_cache["last_update"]) > timedelta(hours=1):
        print("초기 데이터 수집 중...")
        # 동기적으로 한 번 실행
        asyncio.run(collect_once())

async def collect_once():
    """한 번만 트렌드 수집"""
    async with ImprovedTrendCollector() as collector:
        result = await collector.collect_all()
        analysis = analyze_trends(result['trends'])
        
        # 핫 키워드 추출
        hot_keywords = analysis['hot_keywords'][:30]
        
        trends_cache["hot_keywords"] = hot_keywords
        trends_cache["last_update"] = datetime.now().isoformat()

# 서버 종료 시 데이터 저장
def save_cache():
    """캐시 데이터를 파일로 저장"""
    os.makedirs('results', exist_ok=True)
    with open('results/api_cache.json', 'w', encoding='utf-8') as f:
        json.dump(trends_cache, f, ensure_ascii=False, indent=2)

# 프론트엔드 라우트는 위에서 이미 정의됨

if __name__ == '__main__':
    # 초기 데이터 로드
    load_initial_data()
    
    # 백그라운드 수집 시작
    is_collecting = True
    collector_thread = Thread(target=background_collector, daemon=True)
    collector_thread.start()
    
    print("🚀 웹 서비스 시작!")
    print("🌐 웹사이트: http://localhost:5000")
    print("📡 API 서버: http://localhost:5000/api/*")
    print("🔌 WebSocket: ws://localhost:5000")
    print("🛑 종료: Ctrl+C")
    
    try:
        socketio.run(app, debug=False, port=5000, host='0.0.0.0', allow_unsafe_werkzeug=True)
    finally:
        is_collecting = False
        save_cache()