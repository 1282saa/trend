"""
YouTube API v3를 사용한 인기 동영상 수집 모듈
"""
import os
import json
import logging
import time
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.cache import cached, memory_cache, file_cache

# 로그 설정
logger = logging.getLogger('youtube_collector')

class YouTubeCollector:
    """YouTube API를 통한 데이터 수집기"""
    
    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 1800):
        """
        YouTube 수집기 초기화
        
        Args:
            api_key: YouTube API 키 (None이면 환경 변수에서 가져옴)
            cache_ttl: 캐시 유효 시간(초), 기본 30분
        """
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("YouTube API 키가 필요합니다. 환경 변수 YOUTUBE_API_KEY를 설정하거나 api_key 매개변수를 전달하세요.")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.cache_ttl = cache_ttl
    
    @cached(ttl=1800)  # 30분 캐싱
    def fetch_trending_videos(
        self, 
        region_code: str = 'KR',
        category_id: Optional[str] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        특정 지역의 인기 동영상 목록을 가져옵니다.
        
        Args:
            region_code: 국가 코드 (예: 'KR', 'US')
            category_id: 비디오 카테고리 ID (None이면 모든 카테고리)
            max_results: 가져올 최대 결과 수 (최대 50)
            
        Returns:
            인기 동영상 정보 목록
            
        Raises:
            HttpError: API 요청 실패 시
        """
        if max_results > 50:
            logger.warning(f"max_results가 API 한도(50)를 초과하여 50으로 제한됩니다.")
            max_results = 50
            
        try:
            # 인기 동영상 목록 요청
            videos_response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                chart='mostPopular',
                regionCode=region_code,
                videoCategoryId=category_id,
                maxResults=max_results
            ).execute()
            
            # 결과 처리
            videos = []
            for item in videos_response.get('items', []):
                video_data = {
                    'id': item['id'],
                    'title': item['snippet'].get('title', ''),
                    'channel_id': item['snippet'].get('channelId', ''),
                    'channel_title': item['snippet'].get('channelTitle', ''),
                    'published_at': item['snippet'].get('publishedAt', ''),
                    'thumbnail': item['snippet'].get('thumbnails', {}).get('high', {}).get('url', ''),
                    'view_count': int(item['statistics'].get('viewCount', 0)),
                    'like_count': int(item['statistics'].get('likeCount', 0)),
                    'comment_count': int(item['statistics'].get('commentCount', 0)),
                    'duration': item.get('contentDetails', {}).get('duration', ''),
                    'category_id': item['snippet'].get('categoryId', ''),
                    'url': f"https://www.youtube.com/watch?v={item['id']}",
                    'embed_url': f"https://www.youtube.com/embed/{item['id']}",
                    'collected_at': datetime.now().isoformat()
                }
                videos.append(video_data)
                
            return videos
                
        except HttpError as e:
            logger.error(f"YouTube API 오류: {str(e)}")
            return []
    
    def fetch_trending_videos_by_category(
        self, 
        region_code: str = 'KR', 
        max_per_category: int = 10, 
        max_categories: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        카테고리별 인기 동영상을 수집합니다.
        
        Args:
            region_code: 국가 코드 (예: 'KR', 'US')
            max_per_category: 카테고리당 최대 비디오 수
            max_categories: 가져올 최대 카테고리 수 (None이면 모든 카테고리)
            
        Returns:
            카테고리명을 키로 하고 비디오 목록을 값으로 하는 딕셔너리
        """
        try:
            # 비디오 카테고리 목록 가져오기
            categories_response = self.youtube.videoCategories().list(
                part='snippet',
                regionCode=region_code
            ).execute()
            
            # 카테고리 필터링 (유효한 카테고리만)
            categories = []
            for item in categories_response.get('items', []):
                # 할당량 정보가 있거나 유효한 카테고리만 포함
                if 'snippet' in item and item.get('snippet', {}).get('assignable', False):
                    categories.append({
                        'id': item['id'],
                        'title': item['snippet']['title']
                    })
            
            # 카테고리 제한 (필요한 경우)
            if max_categories and len(categories) > max_categories:
                categories = categories[:max_categories]
                
            # 각 카테고리별 인기 동영상 가져오기
            result = {}
            for category in categories:
                videos = self.fetch_trending_videos(
                    region_code=region_code,
                    category_id=category['id'],
                    max_results=max_per_category
                )
                
                if videos:
                    result[category['title']] = videos
                    
                # API 할당량 고려 (연속 요청 시 간격 두기)
                time.sleep(0.5)
                
            return result
            
        except HttpError as e:
            logger.error(f"YouTube API 오류 (카테고리): {str(e)}")
            return {}
    
    @cached(ttl=3600)  # 1시간 캐싱
    def fetch_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """
        여러 동영상의 세부 정보를 가져옵니다.
        
        Args:
            video_ids: 비디오 ID 목록
            
        Returns:
            동영상 세부 정보 목록
        """
        if not video_ids:
            return []
            
        results = []
        # API 요청당 최대 50개 ID 처리 가능
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            
            try:
                response = self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch)
                ).execute()
                
                for item in response.get('items', []):
                    video_data = {
                        'id': item['id'],
                        'title': item['snippet'].get('title', ''),
                        'description': item['snippet'].get('description', ''),
                        'channel_id': item['snippet'].get('channelId', ''),
                        'channel_title': item['snippet'].get('channelTitle', ''),
                        'published_at': item['snippet'].get('publishedAt', ''),
                        'thumbnail': item['snippet'].get('thumbnails', {}).get('high', {}).get('url', ''),
                        'view_count': int(item['statistics'].get('viewCount', 0)),
                        'like_count': int(item['statistics'].get('likeCount', 0)),
                        'comment_count': int(item['statistics'].get('commentCount', 0)),
                        'duration': item.get('contentDetails', {}).get('duration', ''),
                        'tags': item['snippet'].get('tags', []),
                        'url': f"https://www.youtube.com/watch?v={item['id']}",
                        'collected_at': datetime.now().isoformat()
                    }
                    results.append(video_data)
                    
                # API 할당량 고려
                if i + 50 < len(video_ids):
                    time.sleep(0.5)
                    
            except HttpError as e:
                logger.error(f"YouTube API 오류 (동영상 세부정보): {str(e)}")
                
        return results
    
    def fetch_channel_details(self, channel_ids: List[str]) -> List[Dict[str, Any]]:
        """
        여러 채널의 세부 정보를 가져옵니다.
        
        Args:
            channel_ids: 채널 ID 목록
            
        Returns:
            채널 세부 정보 목록
        """
        if not channel_ids:
            return []
            
        results = []
        # API 요청당 최대 50개 ID 처리 가능
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i+50]
            
            try:
                response = self.youtube.channels().list(
                    part='snippet,statistics',
                    id=','.join(batch)
                ).execute()
                
                for item in response.get('items', []):
                    channel_data = {
                        'id': item['id'],
                        'title': item['snippet'].get('title', ''),
                        'description': item['snippet'].get('description', ''),
                        'published_at': item['snippet'].get('publishedAt', ''),
                        'thumbnail': item['snippet'].get('thumbnails', {}).get('high', {}).get('url', ''),
                        'subscriber_count': item['statistics'].get('subscriberCount', 'hidden'),
                        'video_count': int(item['statistics'].get('videoCount', 0)),
                        'view_count': int(item['statistics'].get('viewCount', 0)),
                        'url': f"https://www.youtube.com/channel/{item['id']}",
                        'collected_at': datetime.now().isoformat()
                    }
                    results.append(channel_data)
                    
                # API 할당량 고려
                if i + 50 < len(channel_ids):
                    time.sleep(0.5)
                    
            except HttpError as e:
                logger.error(f"YouTube API 오류 (채널 세부정보): {str(e)}")
                
        return results
    
    def fetch_video_comments(
        self, 
        video_id: str, 
        max_results: int = 100,
        sort: str = 'relevance'
    ) -> List[Dict[str, Any]]:
        """
        비디오의 댓글을 가져옵니다.
        
        Args:
            video_id: 비디오 ID
            max_results: 가져올 최대 댓글 수
            sort: 정렬 방식 ('relevance' 또는 'time')
            
        Returns:
            댓글 정보 목록
        """
        if not video_id:
            return []
            
        comments = []
        next_page_token = None
        
        try:
            while len(comments) < max_results:
                # 댓글 스레드 요청
                request = self.youtube.commentThreads().list(
                    part='snippet',
                    videoId=video_id,
                    maxResults=min(100, max_results - len(comments)),  # API 한도 100
                    order=sort,
                    pageToken=next_page_token
                )
                response = request.execute()
                
                # 응답 처리
                for item in response.get('items', []):
                    comment = item['snippet']['topLevelComment']['snippet']
                    comment_data = {
                        'id': item['id'],
                        'author': comment.get('authorDisplayName', ''),
                        'author_channel_url': comment.get('authorChannelUrl', ''),
                        'text': comment.get('textDisplay', ''),
                        'like_count': int(comment.get('likeCount', 0)),
                        'published_at': comment.get('publishedAt', ''),
                        'updated_at': comment.get('updatedAt', ''),
                        'reply_count': int(item['snippet'].get('totalReplyCount', 0))
                    }
                    comments.append(comment_data)
                
                # 다음 페이지 토큰 처리
                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(comments) >= max_results:
                    break
                    
                # API 할당량 고려
                time.sleep(0.5)
                
            return comments
            
        except HttpError as e:
            if "commentsDisabled" in str(e):
                logger.info(f"비디오의 댓글이 비활성화되어 있습니다: {video_id}")
                return []
            else:
                logger.error(f"YouTube API 오류 (댓글): {str(e)}")
                return []
                
    def search_videos(
        self,
        query: str,
        max_results: int = 50,
        published_after: Optional[Union[str, datetime]] = None,
        region_code: str = 'KR',
        order: str = 'relevance',
        category_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        키워드로 비디오를 검색합니다.
        
        Args:
            query: 검색어
            max_results: 최대 결과 수
            published_after: 이후에 게시된 비디오만 포함 (ISO 8601 형식 문자열 또는 datetime)
            region_code: 국가 코드
            order: 정렬 방식 ('relevance', 'date', 'viewCount', 'rating')
            category_id: 비디오 카테고리 ID
            
        Returns:
            검색 결과 비디오 목록
        """
        if not query:
            return []
            
        # published_after 처리
        if published_after:
            if isinstance(published_after, datetime):
                published_after = published_after.strftime('%Y-%m-%dT%H:%M:%SZ')
            elif not isinstance(published_after, str):
                published_after = None
                
        videos = []
        next_page_token = None
        
        try:
            while len(videos) < max_results:
                # 검색 요청
                request_params = {
                    'part': 'snippet',
                    'q': query,
                    'type': 'video',
                    'maxResults': min(50, max_results - len(videos)),  # API 한도 50
                    'regionCode': region_code,
                    'order': order,
                }
                
                if published_after:
                    request_params['publishedAfter'] = published_after
                
                if category_id:
                    request_params['videoCategoryId'] = category_id
                    
                if next_page_token:
                    request_params['pageToken'] = next_page_token
                
                request = self.youtube.search().list(**request_params)
                response = request.execute()
                
                # 비디오 ID 추출
                video_ids = [item['id']['videoId'] for item in response.get('items', [])]
                
                # 비디오 세부 정보 가져오기
                if video_ids:
                    video_details = self.fetch_video_details(video_ids)
                    videos.extend(video_details)
                
                # 다음 페이지 토큰 처리
                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(videos) >= max_results:
                    break
                    
                # API 할당량 고려
                time.sleep(0.5)
                
            return videos[:max_results]
            
        except HttpError as e:
            logger.error(f"YouTube API 오류 (검색): {str(e)}")
            return [] 