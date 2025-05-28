#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
실시간 트렌드 수집 메인 스크립트
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import signal

import pandas as pd
from dotenv import load_dotenv

from collectors.trend_collector import TrendCollector

# 환경 변수 로드
load_dotenv()

# 로그 설정
logging.basicConfig(
    level=logging.INFO if os.getenv('LOG_LEVEL') is None else getattr(logging, os.getenv('LOG_LEVEL')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trend_collector.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('main')

# 키보드 인터럽트 시 우아하게 종료하기 위한 변수
stop_requested = False

def signal_handler(sig, frame):
    """키보드 인터럽트 핸들러"""
    global stop_requested
    logger.info("종료 요청을 받았습니다. 진행 중인 작업 완료 후 종료합니다...")
    stop_requested = True

# 시그널 핸들러 등록
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def parse_arguments():
    """명령줄 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(description="실시간 트렌드 수집 도구")
    
    # 수집 소스 선택 옵션
    source_group = parser.add_argument_group('수집 소스')
    source_group.add_argument("--youtube", action="store_true", help="유튜브 인기 동영상 수집")
    source_group.add_argument("--news", action="store_true", help="뉴스 인기 기사 수집")
    source_group.add_argument("--portal", action="store_true", help="포털 인기 검색어 수집")
    source_group.add_argument("--google-trends", action="store_true", help="구글 트렌드 수집")
    source_group.add_argument("--all", action="store_true", help="모든 소스에서 데이터 수집 (기본값)")
    
    # 유튜브 옵션
    youtube_group = parser.add_argument_group('유튜브 옵션')
    youtube_group.add_argument("--youtube-region", type=str, default="KR", help="유튜브 지역 코드 (기본값: KR)")
    youtube_group.add_argument("--youtube-max", type=int, default=50, help="유튜브 최대 결과 수 (기본값: 50)")
    youtube_group.add_argument("--youtube-by-category", action="store_true", help="유튜브 카테고리별 수집")
    
    # 뉴스 옵션
    news_group = parser.add_argument_group('뉴스 옵션')
    news_group.add_argument("--news-sources", type=str, default="naver,daum,google",
                          help="수집할 뉴스 소스 (콤마로 구분, 기본값: naver,daum,google)")
    news_group.add_argument("--news-category", type=str, default=None,
                          help="뉴스 카테고리 (기본값: 전체)")
    news_group.add_argument("--news-max", type=int, default=30,
                          help="소스별 최대 뉴스 수 (기본값: 30)")
    
    # 포털 옵션
    portal_group = parser.add_argument_group('포털 옵션')
    portal_group.add_argument("--portal-sources", type=str, default="naver,daum,zum,nate",
                            help="수집할 포털 소스 (콤마로 구분, 기본값: naver,daum,zum,nate)")
    portal_group.add_argument("--portal-max", type=int, default=20,
                            help="소스별 최대 검색어 수 (기본값: 20)")
    portal_group.add_argument("--portal-combine", action="store_true",
                            help="여러 포털의 인기 검색어 통합 순위화")
    portal_group.add_argument("--portal-min-sources", type=int, default=2,
                            help="키워드 통합 시 최소 등장 소스 수 (기본값: 2)")
    
    # 구글 트렌드 옵션
    google_trends_group = parser.add_argument_group('구글 트렌드 옵션')
    google_trends_group.add_argument("--google-trends-country", type=str, default="south_korea",
                                  help="구글 트렌드 국가 코드 (기본값: south_korea)")
    google_trends_group.add_argument("--google-trends-max", type=int, default=20,
                                  help="구글 트렌드 최대 결과 수 (기본값: 20)")
    google_trends_group.add_argument("--google-trends-keyword", type=str, default=None,
                                  help="구글 트렌드에서 분석할 키워드 (콤마로 구분, 최대 5개)")
    google_trends_group.add_argument("--google-trends-timeframe", type=str, default="now 1-d",
                                  help="구글 트렌드 시간 범위 (기본값: now 1-d)")
    
    # 출력 옵션
    output_group = parser.add_argument_group('출력 옵션')
    output_group.add_argument("--output", type=str, default=None,
                            help="결과 저장 파일 경로 (없으면 화면에 출력)")
    output_group.add_argument("--format", type=str, choices=["json", "csv", "excel"], default="json",
                            help="출력 형식 (기본값: json)")
    output_group.add_argument("--pretty", action="store_true", help="JSON 출력을 보기 좋게 포맷팅")
    
    # 실행 모드 옵션
    mode_group = parser.add_argument_group('실행 모드')
    mode_group.add_argument("--daemon", action="store_true", help="데몬 모드로 실행 (주기적 수집)")
    mode_group.add_argument("--interval", type=int, default=300,
                          help="데몬 모드에서 수집 간격(초) (기본값: 300)")
    mode_group.add_argument("--runs", type=int, default=0,
                          help="데몬 모드에서 실행 횟수 (0=무한)")
    
    # 기타 옵션
    parser.add_argument("--verbose", action="store_true", help="상세 로깅 활성화")
    
    return parser.parse_args()

def save_results(results: Dict[str, Any], output_path: Optional[str], output_format: str, pretty: bool = False):
    """
    결과를 파일로 저장하거나 화면에 출력합니다.
    
    Args:
        results: 저장할 결과 데이터
        output_path: 출력 파일 경로 (None이면 화면에 출력)
        output_format: 출력 형식 (json, csv, excel)
        pretty: 보기 좋게 포맷팅할지 여부
    """
    # 출력 파일이 지정되지 않은 경우 화면에 출력
    if output_path is None:
        if output_format == 'json':
            if pretty:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(results, ensure_ascii=False))
        else:
            print(results)
        return
    
    # 디렉토리 생성
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # 형식에 따라 저장
    if output_format == 'json':
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2 if pretty else None)
    
    elif output_format == 'csv':
        # JSON을 DataFrame으로 변환
        try:
            df = flatten_json_to_dataframe(results)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
        except Exception as e:
            logger.error(f"CSV 변환 오류: {str(e)}")
            # 실패 시 JSON으로 저장
            with open(f"{output_path}.json", 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
    
    elif output_format == 'excel':
        # JSON을 DataFrame으로 변환
        try:
            df = flatten_json_to_dataframe(results)
            df.to_excel(output_path, index=False)
        except Exception as e:
            logger.error(f"Excel 변환 오류: {str(e)}")
            # 실패 시 JSON으로 저장
            with open(f"{output_path}.json", 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"결과가 {output_path}에 저장되었습니다.")

def flatten_json_to_dataframe(data: Dict[str, Any]) -> pd.DataFrame:
    """
    중첩된 JSON을 DataFrame으로 변환합니다.
    
    Args:
        data: 변환할 JSON 데이터
        
    Returns:
        변환된 DataFrame
    """
    flattened_data = []
    
    # 유튜브 데이터 처리
    if 'sources' in data and 'youtube' in data['sources']:
        for item in data['sources']['youtube']:
            flat_item = {
                'type': 'youtube',
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'channel': item.get('channel_title', ''),
                'views': item.get('view_count', 0),
                'likes': item.get('like_count', 0),
                'published_at': item.get('published_at', ''),
                'thumbnail': item.get('thumbnail', '')
            }
            flattened_data.append(flat_item)
    
    # 뉴스 데이터 처리
    if 'sources' in data and 'news' in data['sources']:
        for source, items in data['sources']['news'].items():
            for item in items:
                flat_item = {
                    'type': f'news_{source}',
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'source': item.get('source', ''),
                    'description': item.get('description', ''),
                    'published_at': item.get('published_time', ''),
                    'thumbnail': item.get('thumbnail', ''),
                    'category': item.get('category', '')
                }
                flattened_data.append(flat_item)
    
    # 포털 인기 검색어 처리
    if 'sources' in data and 'portal' in data['sources']:
        for source, items in data['sources']['portal'].items():
            for item in items:
                flat_item = {
                    'type': f'portal_{source}',
                    'keyword': item.get('keyword', ''),
                    'rank': item.get('rank', 0),
                    'delta': item.get('delta', 0)
                }
                flattened_data.append(flat_item)
                
    # 구글 트렌드 데이터 처리
    if 'sources' in data and 'google_trends' in data['sources']:
        for item in data['sources']['google_trends']:
            flat_item = {
                'type': 'google_trends',
                'keyword': item.get('keyword', ''),
                'rank': item.get('rank', 0),
                'country': item.get('country', '')
            }
            flattened_data.append(flat_item)
    
    return pd.DataFrame(flattened_data)

async def run_collection(args):
    """
    지정된 소스에서 데이터를 수집합니다.
    
    Args:
        args: 명령줄 인수
        
    Returns:
        수집된 결과
    """
    # 통합 수집기 생성
    collector = TrendCollector()
    
    # 수집 소스 확인
    include_youtube = args.youtube or args.all
    include_news = args.news or args.all
    include_portal = args.portal or args.all
    include_google_trends = args.google_trends or args.all
    
    # 수집기 상태 확인
    collectors_status = collector.check_collectors()
    
    # 선택한 소스 중 하나라도 사용할 수 없는 경우 경고
    if include_youtube and not collectors_status['youtube']:
        logger.warning("유튜브 수집기가 초기화되지 않아 유튜브 데이터는 수집되지 않습니다.")
    if include_news and not collectors_status['news']:
        logger.warning("뉴스 수집기가 초기화되지 않아 뉴스 데이터는 수집되지 않습니다.")
    if include_portal and not collectors_status['portal']:
        logger.warning("포털 수집기가 초기화되지 않아 포털 데이터는 수집되지 않습니다.")
    if include_google_trends and not collectors_status['google_trends']:
        logger.warning("구글 트렌드 수집기가 초기화되지 않아 구글 트렌드 데이터는 수집되지 않습니다.")
    
    # 모든 소스가 비활성화된 경우
    if not (include_youtube and collectors_status['youtube']) and \
       not (include_news and collectors_status['news']) and \
       not (include_portal and collectors_status['portal']) and \
       not (include_google_trends and collectors_status['google_trends']):
        logger.error("모든 데이터 소스가 비활성화되었습니다. 수집할 수 있는 소스가 없습니다.")
        return None
    
    # 결과를 담을 딕셔너리
    results = {
        'timestamp': datetime.now().isoformat(),
        'sources': {}
    }
    
    # 유튜브 데이터 수집
    if include_youtube and collectors_status['youtube']:
        logger.info("유튜브 인기 동영상 수집 중...")
        
        if args.youtube_by_category:
            youtube_results = collector.collect_youtube_trends(
                region_code=args.youtube_region,
                by_category=True,
                max_per_category=args.youtube_max // 5,  # 카테고리당 약 1/5 정도 가져오기
                max_categories=5
            )
            
            # 카테고리별 결과를 통합 리스트로 변환
            flat_results = []
            for category, videos in youtube_results.items():
                for video in videos:
                    video['category_name'] = category
                    flat_results.append(video)
            
            results['sources']['youtube'] = flat_results
        else:
            results['sources']['youtube'] = collector.collect_youtube_trends(
                region_code=args.youtube_region,
                max_results=args.youtube_max
            )
        
        logger.info(f"{len(results['sources'].get('youtube', []))} 개의 유튜브 동영상 수집 완료")
    
    # 뉴스 데이터 수집
    if include_news and collectors_status['news']:
        logger.info("뉴스 인기 기사 수집 중...")
        
        news_sources = [s.strip() for s in args.news_sources.split(',') if s.strip()]
        results['sources']['news'] = await collector.collect_news_trends(
            sources=news_sources,
            category=args.news_category,
            max_per_source=args.news_max
        )
        
        # 소스별 수집 결과 로그
        for source, items in results['sources'].get('news', {}).items():
            logger.info(f"{source} 뉴스: {len(items)} 개 수집 완료")
    
    # 포털 인기 검색어 수집
    if include_portal and collectors_status['portal']:
        logger.info("포털 인기 검색어 수집 중...")
        
        portal_sources = [s.strip() for s in args.portal_sources.split(',') if s.strip()]
        portal_results = await collector.collect_portal_trends(
            sources=portal_sources,
            max_per_source=args.portal_max
        )
        
        # 소스별 수집 결과 로그
        for source, items in portal_results.items():
            logger.info(f"{source} 인기 검색어: {len(items)} 개 수집 완료")
        
        # 통합 순위화 옵션
        if args.portal_combine and len(portal_results) > 1:
            combined_trends = collector.get_combined_trending_keywords(
                portal_results, 
                min_sources=args.portal_min_sources,
                max_results=100
            )
            
            # 원본 및 통합 결과 모두 저장
            results['sources']['portal'] = {
                'by_source': portal_results,
                'combined': combined_trends
            }
            logger.info(f"포털 통합 검색어: {len(combined_trends)} 개 생성 완료")
        else:
            results['sources']['portal'] = portal_results
            
    # 구글 트렌드 데이터 수집
    if include_google_trends and collectors_status['google_trends']:
        logger.info("구글 트렌드 수집 중...")
        
        # 실시간 인기 검색어 수집
        google_trends_results = collector.collect_google_trends(
            country=args.google_trends_country,
            max_results=args.google_trends_max
        )
        results['sources']['google_trends'] = google_trends_results
        
        # 키워드 분석 옵션이 있는 경우
        if args.google_trends_keyword:
            keywords = [k.strip() for k in args.google_trends_keyword.split(',') if k.strip()]
            if keywords:
                logger.info(f"구글 트렌드 키워드 분석: {', '.join(keywords)}")
                keyword_results = collector.collect_keyword_interest(
                    keywords=keywords,
                    timeframe=args.google_trends_timeframe,
                    geo='KR'
                )
                results['sources']['google_trends_keyword_analysis'] = keyword_results
        
        logger.info(f"{len(results['sources'].get('google_trends', []))} 개의 구글 트렌드 키워드 수집 완료")
    
    return results

async def run_daemon(args):
    """
    데몬 모드로 주기적으로 데이터를 수집합니다.
    
    Args:
        args: 명령줄 인수
    """
    runs_completed = 0
    
    while not stop_requested:
        try:
            # 현재 시간 기록
            start_time = datetime.now()
            logger.info(f"데이터 수집 시작 (실행 #{runs_completed + 1})")
            
            # 데이터 수집
            results = await run_collection(args)
            
            if results:
                # 타임스탬프를 파일명에 포함
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # 출력 파일 경로 생성
                if args.output:
                    base_name, ext = os.path.splitext(args.output)
                    if not ext:
                        ext = f".{args.format}"
                    output_path = f"{base_name}_{timestamp}{ext}"
                else:
                    output_dir = os.getenv('OUTPUT_DIR', 'results')
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, f"trends_{timestamp}.{args.format}")
                
                # 결과 저장
                save_results(results, output_path, args.format, args.pretty)
            
            # 실행 횟수 증가
            runs_completed += 1
            
            # 최대 실행 횟수 체크
            if args.runs > 0 and runs_completed >= args.runs:
                logger.info(f"지정된 실행 횟수({args.runs})에 도달하여 종료합니다.")
                break
            
            # 실행 간격 대기
            elapsed = (datetime.now() - start_time).total_seconds()
            wait_time = max(0, args.interval - elapsed)
            
            if wait_time > 0 and not stop_requested:
                logger.info(f"다음 실행까지 {wait_time:.1f}초 대기 중...")
                # 작은 단위로 나누어 대기 (종료 신호에 더 빠르게 반응하기 위함)
                for _ in range(int(wait_time)):
                    await asyncio.sleep(1)
                    if stop_requested:
                        break
            
        except Exception as e:
            logger.error(f"데몬 실행 중 오류 발생: {str(e)}")
            # 오류 발생 시에도 잠시 대기 후 재시도
            await asyncio.sleep(min(30, args.interval))
    
    logger.info("데몬 모드 종료")

async def main():
    """메인 함수"""
    # 명령줄 인수 파싱
    args = parse_arguments()
    
    # 로그 레벨 설정
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("디버그 모드 활성화됨")
    
    # 인자가 없으면 기본적으로 모든 소스 수집
    if not (args.youtube or args.news or args.portal or args.google_trends):
        args.all = True
    
    # 데몬 모드 실행
    if args.daemon:
        logger.info(f"데몬 모드 시작 (간격: {args.interval}초)")
        await run_daemon(args)
    # 일회성 실행
    else:
        logger.info("데이터 수집 시작")
        results = await run_collection(args)
        
        if results:
            # 출력 파일 경로 결정
            output_path = args.output
            if output_path:
                # 확장자가 없는 경우 추가
                if '.' not in os.path.basename(output_path):
                    output_path = f"{output_path}.{args.format}"
            
            # 결과 저장 또는 출력
            save_results(results, output_path, args.format, args.pretty)
        
        logger.info("데이터 수집 완료")

if __name__ == "__main__":
    # Windows에서 asyncio 이벤트 루프 정책 설정 (필요한 경우)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 비동기 메인 함수 실행
    asyncio.run(main()) 