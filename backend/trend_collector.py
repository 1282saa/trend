import os
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Any
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import feedparser

load_dotenv()

class ImprovedTrendCollector:
    """개선된 트렌드 수집기 - 실제 데이터 수집에 최적화"""
    
    def __init__(self):
        self.session = None
        # API 키 로드
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        self.news_api_key = os.getenv('NEWS_API_KEY')
        self.naver_client_id = os.getenv('NAVER_CLIENT_ID')
        self.naver_client_secret = os.getenv('NAVER_CLIENT_SECRET')
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def collect_all(self) -> Dict[str, Any]:
        """모든 소스에서 트렌드 수집"""
        tasks = [
            self.collect_youtube_api(),
            self.collect_naver_api(),
            self.collect_news_api(),
            self.collect_google_rss(),
            self.collect_daum_search(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 성공한 결과만 필터링
        all_trends = []
        for i, result in enumerate(results):
            if isinstance(result, list):
                all_trends.extend(result)
            else:
                print(f"수집 실패 [{i}]: {result}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total": len(all_trends),
            "trends": all_trends
        }
    
    async def collect_youtube_api(self) -> List[Dict[str, Any]]:
        """YouTube API로 실제 인기 동영상 수집"""
        if not self.youtube_api_key or self.youtube_api_key == 'your_youtube_api_key_here':
            print("YouTube API 키 미설정")
            return []
        
        try:
            from .collectors.youtube_collector import YouTubeCollector
            collector = YouTubeCollector()
            videos = collector.fetch_trending_videos(max_results=50)  # 50개로 증가
            
            trends = []
            for video in videos:
                trends.append({
                    "keyword": video['keyword'],
                    "source": "youtube",
                    "score": video.get('view_count', 0) // 10000,  # 만 단위로 점수화
                    "url": video.get('url', ''),
                    "metadata": {
                        "channel": video.get('channel', ''),
                        "views": video.get('view_count', 0),
                        "description": video.get('description', '')[:200],
                        "published_at": video.get('published_at', ''),
                        "thumbnail": video.get('thumbnail', '')
                    },
                    "timestamp": datetime.now().isoformat()
                })
            
            print(f"YouTube: {len(trends)}개 수집")
            return trends
            
        except Exception as e:
            print(f"YouTube API 오류: {e}")
            return []
    
    async def collect_naver_api(self) -> List[Dict[str, Any]]:
        """네이버 API로 실시간 뉴스/검색어 수집"""
        if not self.naver_client_id:
            print("Naver API 키 미설정")
            return []
        
        try:
            trends = []
            
            # 1. 실시간 급상승 뉴스
            url = "https://openapi.naver.com/v1/search/news.json"
            headers = {
                "X-Naver-Client-Id": self.naver_client_id,
                "X-Naver-Client-Secret": self.naver_client_secret,
            }
            
            # 여러 키워드로 검색하여 트렌드 파악
            hot_keywords = ["속보", "단독", "긴급", "화제", "논란", "인기"]
            
            for keyword in hot_keywords:
                params = {
                    "query": keyword,
                    "display": 5,
                    "sort": "date"
                }
                
                async with self.session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for item in data.get('items', []):
                            # HTML 태그 제거
                            import re
                            title = re.sub('<.*?>', '', item['title'])
                            
                            # 핵심 키워드 추출 (간단한 방식)
                            words = title.split()[:5]  # 앞 5단어
                            main_keyword = ' '.join(words)
                            
                            trends.append({
                                "keyword": main_keyword,
                                "source": "naver",
                                "score": 50 + (hot_keywords.index(keyword) * 10),
                                "url": item.get('link', ''),
                                "timestamp": datetime.now().isoformat()
                            })
            
            # 중복 제거
            seen = set()
            unique_trends = []
            for trend in trends:
                if trend['keyword'] not in seen:
                    seen.add(trend['keyword'])
                    unique_trends.append(trend)
            
            print(f"Naver: {len(unique_trends)}개 수집")
            return unique_trends[:50]  # 50개로 증가
            
        except Exception as e:
            print(f"Naver API 오류: {e}")
            return []
    
    async def collect_news_api(self) -> List[Dict[str, Any]]:
        """연합뉴스 RSS 피드에서 뉴스 수집"""
        try:
            # 연합뉴스 RSS 피드 URL
            rss_url = 'https://www.yna.co.kr/rss/news.xml'
            
            async with self.session.get(rss_url) as response:
                if response.status == 200:
                    import xml.etree.ElementTree as ET
                    
                    text = await response.text()
                    root = ET.fromstring(text)
                    
                    trends = []
                    items = root.findall('.//item')[:50]  # 최신 뉴스 50개
                    
                    for idx, item in enumerate(items):
                        title_elem = item.find('title')
                        desc_elem = item.find('description')
                        link_elem = item.find('link')
                        
                        if title_elem is not None and title_elem.text:
                            title = title_elem.text
                            
                            # 제목에서 주요 키워드 추출
                            # 연합뉴스 제목 형식: "주요내용" 또는 "주요내용(부가정보)"
                            keyword = title.split('(')[0].strip()
                            if len(keyword) > 30:
                                keyword = keyword[:30] + '...'
                            
                            trends.append({
                                "keyword": keyword,
                                "source": "news",
                                "score": 80 - (idx * 2),  # 최신 뉴스일수록 높은 점수
                                "url": link_elem.text if link_elem is not None else '',
                                "description": desc_elem.text[:200] if desc_elem is not None and desc_elem.text else '',
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    print(f"연합뉴스에서 {len(trends)}개 뉴스 수집")
                    return trends
                else:
                    print(f"연합뉴스 RSS 접근 오류: {response.status}")
                    return []
                    
        except Exception as e:
            print(f"연합뉴스 RSS 수집 오류: {e}")
            return []
    
    async def collect_google_rss(self) -> List[Dict[str, Any]]:
        """Google Trends RSS 피드 수집"""
        try:
            url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    trends = []
                    for idx, entry in enumerate(feed.entries[:10]):
                        trends.append({
                            "keyword": entry.title,
                            "source": "google",
                            "score": 100 - (idx * 5),  # 순위에 따른 점수
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    print(f"Google RSS: {len(trends)}개 수집")
                    return trends
                    
        except Exception as e:
            print(f"Google RSS 오류: {e}")
            return []
    
    async def collect_daum_search(self) -> List[Dict[str, Any]]:
        """다음 실시간 검색어 (대체 방법)"""
        try:
            # 다음 뉴스 인기 기사로 대체
            url = "https://news.daum.net/ranking/popular"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    trends = []
                    # 인기 뉴스 제목 추출
                    news_items = soup.select('a.link_txt')[:10]
                    
                    for idx, item in enumerate(news_items):
                        title = item.text.strip()
                        if title:
                            # 제목에서 핵심 키워드 추출
                            words = title.split()[:5]
                            keyword = ' '.join(words)
                            
                            trends.append({
                                "keyword": keyword,
                                "source": "daum",
                                "score": 80 - (idx * 5),
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    print(f"Daum: {len(trends)}개 수집")
                    return trends
                    
        except Exception as e:
            print(f"Daum 수집 오류: {e}")
            return []

def analyze_trends(all_trends: List[Dict[str, Any]]) -> Dict[str, Any]:
    """수집된 트렌드 분석 및 정리"""
    # 키워드별 점수 집계
    keyword_scores = {}
    
    for trend in all_trends:
        keyword = trend['keyword'].lower()
        if keyword in keyword_scores:
            keyword_scores[keyword]['score'] += trend.get('score', 50)
            keyword_scores[keyword]['sources'].add(trend['source'])
            keyword_scores[keyword]['count'] += 1
        else:
            keyword_scores[keyword] = {
                'keyword': trend['keyword'],  # 원본 유지
                'score': trend.get('score', 50),
                'sources': {trend['source']},
                'count': 1,
                'urls': []
            }
        
        # URL 수집
        if trend.get('url'):
            keyword_scores[keyword]['urls'].append(trend['url'])
    
    # 점수 기준 정렬
    sorted_keywords = sorted(
        keyword_scores.values(),
        key=lambda x: x['score'] * len(x['sources']),  # 점수 x 플랫폼 수
        reverse=True
    )
    
    # 상위 100개만 선택
    top_keywords = sorted_keywords[:100]
    
    # API 형식으로 변환
    formatted_trends = []
    for idx, item in enumerate(top_keywords):
        formatted_trends.append({
            'keyword': item['keyword'],
            'score': item['score'],
            'sources': list(item['sources']),
            'rank': idx + 1,
            'timestamp': datetime.now().isoformat()
        })
    
    return {
        'hot_keywords': formatted_trends,
        'total_collected': len(all_trends),
        'unique_keywords': len(keyword_scores),
        'last_update': datetime.now().isoformat()
    }

async def test_collection():
    """테스트 실행"""
    print("=" * 50)
    print("개선된 트렌드 수집 테스트")
    print("=" * 50)
    
    async with ImprovedTrendCollector() as collector:
        # 전체 수집
        result = await collector.collect_all()
        
        print(f"\n총 {result['total']}개 트렌드 수집")
        
        # 분석
        analysis = analyze_trends(result['trends'])
        
        print(f"\n🔥 HOT 키워드 TOP 10:")
        for trend in analysis['hot_keywords'][:10]:
            sources = ', '.join(trend['sources'])
            print(f"{trend['rank']}. {trend['keyword']} (점수: {trend['score']}, 출처: {sources})")
        
        # 결과 저장
        os.makedirs('results', exist_ok=True)
        with open('results/test_trends.json', 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 결과 저장: results/test_trends.json")

if __name__ == "__main__":
    asyncio.run(test_collection())