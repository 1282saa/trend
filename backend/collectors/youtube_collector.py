import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class YouTubeCollector:
    """YouTube 트렌드 수집기"""
    
    def __init__(self):
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        if self.api_key and self.api_key != 'your_youtube_api_key_here':
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        else:
            self.youtube = None
            print("⚠️  YouTube API 키가 설정되지 않았습니다.")
            print("GCP에서 발급받은 YouTube Data API v3 키를 .env 파일에 추가하세요:")
            print("YOUTUBE_API_KEY=your_actual_api_key")
    
    def fetch_trending_videos(self, region='KR', max_results=20) -> List[Dict[str, Any]]:
        """YouTube 인기 급상승 동영상 수집"""
        if not self.youtube:
            return []
        
        try:
            request = self.youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=region,
                maxResults=max_results,
                hl='ko'  # 한국어 결과 우선
            )
            
            response = request.execute()
            
            trends = []
            for item in response.get('items', []):
                snippet = item['snippet']
                statistics = item.get('statistics', {})
                
                trends.append({
                    'keyword': snippet['title'],
                    'source': 'youtube',
                    'channel': snippet['channelTitle'],
                    'description': snippet.get('description', '')[:200],
                    'video_id': item['id'],
                    'url': f"https://www.youtube.com/watch?v={item['id']}",
                    'view_count': int(statistics.get('viewCount', 0)),
                    'like_count': int(statistics.get('likeCount', 0)),
                    'published_at': snippet['publishedAt'],
                    'timestamp': datetime.now().isoformat(),
                    'type': 'trending_video'
                })
            
            return trends
            
        except HttpError as e:
            print(f"YouTube API 오류: {e}")
            if e.resp.status == 403:
                print("API 할당량 초과 또는 API 키 권한 문제일 수 있습니다.")
                print("GCP 콘솔에서 YouTube Data API v3가 활성화되어 있는지 확인하세요.")
            return []
        except Exception as e:
            print(f"YouTube 트렌드 수집 오류: {e}")
            return []
    
    def search_by_keyword(self, keyword: str, max_results=10) -> List[Dict[str, Any]]:
        """특정 키워드로 YouTube 검색"""
        if not self.youtube:
            return []
        
        try:
            request = self.youtube.search().list(
                part='snippet',
                q=keyword,
                type='video',
                order='viewCount',  # 조회수 순 정렬
                regionCode='KR',
                maxResults=max_results,
                hl='ko'
            )
            
            response = request.execute()
            
            results = []
            for item in response.get('items', []):
                snippet = item['snippet']
                results.append({
                    'title': snippet['title'],
                    'channel': snippet['channelTitle'],
                    'description': snippet.get('description', '')[:200],
                    'video_id': item['id']['videoId'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    'published_at': snippet['publishedAt'],
                    'timestamp': datetime.now().isoformat()
                })
            
            return results
            
        except Exception as e:
            print(f"YouTube 검색 오류: {e}")
            return []


# 독립 실행 테스트
if __name__ == "__main__":
    collector = YouTubeCollector()
    
    if collector.youtube:
        print("YouTube 트렌드 수집 중...")
        trends = collector.fetch_trending_videos(max_results=10)
        
        if trends:
            print(f"\n✅ YouTube 인기 동영상 TOP 10:")
            for idx, video in enumerate(trends, 1):
                print(f"{idx}. {video['keyword']}")
                print(f"   채널: {video['channel']}")
                print(f"   조회수: {video['view_count']:,}")
                print(f"   URL: {video['url']}")
                print()
        else:
            print("트렌드를 가져올 수 없습니다.")
    else:
        print("\nYouTube API 키 설정 방법:")
        print("1. GCP 콘솔에서 YouTube Data API v3 활성화")
        print("2. API 키 생성")
        print("3. .env 파일에 추가: YOUTUBE_API_KEY=your_key")