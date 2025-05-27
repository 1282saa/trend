import os
import json
import asyncio
from typing import List, Dict, Any, Optional
import re
from openai import OpenAI
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# OpenAI API 키 환경 변수에서 가져오기
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 기본 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

def cluster_topics_with_chatgpt(
    keywords: List[str], 
    api_key: Optional[str] = None, 
    n_clusters: int = 5
) -> List[Dict[str, Any]]:
    """
    ChatGPT를 사용하여 키워드를 주제별로 군집화합니다.
    
    Args:
        keywords: 군집화할 키워드 리스트
        api_key: OpenAI API 키 (없으면 환경 변수에서 가져옴)
        n_clusters: 생성할 클러스터(토픽) 수
        
    Returns:
        [{'topic': '금리동향', 'keywords': [...]}, ...] 형식의 리스트
    """
    if not keywords:
        return []
        
    # API 키 설정
    api_key = api_key or OPENAI_API_KEY
    if not api_key:
        raise ValueError("OpenAI API 키가 필요합니다. 환경 변수 OPENAI_API_KEY를 설정하거나 api_key 매개변수를 전달하세요.")
    
    # OpenAI 클라이언트 설정
    client = OpenAI(api_key=api_key)
    
    # 프롬프트 구성
    prompt = f"""
다음 키워드 리스트를 금융/경제 관점에서 주요 {n_clusters}개 토픽으로 묶고,
각 토픽에 해당하는 키워드를 함께 제시해주세요.
결과는 반드시 다음 JSON 형식으로 반환해주세요:

```json
[
  {{
    "topic": "토픽명",
    "keywords": ["키워드1", "키워드2", ...]
  }},
  ...
]
```

키워드 리스트:
{keywords}
"""
    
    try:
        # ChatGPT API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        # 응답 내용 가져오기
        content = response.choices[0].message.content
        
        # JSON 추출 (```json와 같은 마크다운 코드 블록이 있을 경우 처리)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            content = json_match.group(1)
        
        # JSON 파싱
        try:
            clusters = json.loads(content)
            # JSON 형식이 예상과 다를 경우 처리
            if isinstance(clusters, dict) and "clusters" in clusters:
                clusters = clusters["clusters"]
            elif isinstance(clusters, dict):
                # 다른 형태의 JSON이 반환된 경우 리스트로 변환
                clusters = [{"topic": k, "keywords": v} for k, v in clusters.items()]
            
            return clusters
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"원본 응답: {content}")
            return []
            
    except Exception as e:
        print(f"ChatGPT API 호출 오류: {e}")
        return []

def generate_hook_copies(
    topic: str, 
    api_key: Optional[str] = None, 
    n: int = 3
) -> List[str]:
    """
    ChatGPT를 사용하여 토픽에 대한 훅 카피를 생성합니다.
    
    Args:
        topic: 훅 카피를 생성할 토픽명
        api_key: OpenAI API 키 (없으면 환경 변수에서 가져옴)
        n: 생성할 훅 카피 수
        
    Returns:
        생성된 훅 카피 리스트
    """
    if not topic:
        return []
        
    # API 키 설정
    api_key = api_key or OPENAI_API_KEY
    if not api_key:
        raise ValueError("OpenAI API 키가 필요합니다. 환경 변수 OPENAI_API_KEY를 설정하거나 api_key 매개변수를 전달하세요.")
    
    # OpenAI 클라이언트 설정
    client = OpenAI(api_key=api_key)
    
    # 프롬프트 구성
    prompt = f"""
'00초 요약' 시리즈 훅 카피 {n}개를 짧게 만들어주세요.
결과는 반드시 다음 JSON 형식으로 반환해주세요:

```json
{{
  "hooks": ["8초만에 알아보는 금리동향", "10초 완성! 요즘 금리 트렌드", ...]
}}
```

주제: {topic}
"""

    try:
        # ChatGPT API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            response_format={"type": "json_object"}
        )
        
        # 응답 내용 가져오기
        content = response.choices[0].message.content
        
        # JSON 추출 (```json와 같은 마크다운 코드 블록이 있을 경우 처리)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            content = json_match.group(1)
        
        # JSON 파싱
        try:
            result = json.loads(content)
            return result.get("hooks", [])
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            # 파싱 실패 시 간단한 텍스트 분할 시도
            lines = content.strip().split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            return cleaned_lines[:n] if cleaned_lines else []
            
    except Exception as e:
        print(f"ChatGPT API 호출 오류: {e}")
        return []

async def generate_insights_async(
    clusters: List[Dict[str, Any]], 
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    여러 토픽에 대한 훅 카피를 비동기적으로 생성합니다.
    
    Args:
        clusters: [{'topic': '금리동향', 'keywords': [...]}, ...] 형식의 클러스터 리스트
        api_key: OpenAI API 키 (없으면 환경 변수에서 가져옴)
        
    Returns:
        훅 카피가 추가된 클러스터 리스트
    """
    if not clusters:
        return []
        
    async def process_cluster(cluster):
        topic = cluster.get('topic', '')
        hooks = generate_hook_copies(topic, api_key)
        return {**cluster, 'hook_copies': hooks}
    
    # 비동기 작업 생성
    tasks = [process_cluster(cluster) for cluster in clusters]
    
    # 비동기 작업 실행 및 결과 수집
    results = await asyncio.gather(*tasks)
    
    return results

def generate_topic_summary(
    topic: str, 
    keywords: List[str], 
    api_key: Optional[str] = None,
    max_words: int = 150
) -> str:
    """
    토픽과 관련 키워드를 바탕으로 요약문을 생성합니다.
    
    Args:
        topic: 토픽명
        keywords: 관련 키워드 리스트
        api_key: OpenAI API 키 (없으면 환경 변수에서 가져옴)
        max_words: 최대 단어 수
        
    Returns:
        생성된 요약문
    """
    if not topic or not keywords:
        return ""
        
    # API 키 설정
    api_key = api_key or OPENAI_API_KEY
    if not api_key:
        raise ValueError("OpenAI API 키가 필요합니다. 환경 변수 OPENAI_API_KEY를 설정하거나 api_key 매개변수를 전달하세요.")
    
    # OpenAI 클라이언트 설정
    client = OpenAI(api_key=api_key)
    
    # 프롬프트 구성
    prompt = f"""
다음 토픽과 관련 키워드를 바탕으로 최근 트렌드에 대한 간결한 요약문을 {max_words}단어 이내로 작성해주세요.
결과는 JSON 형식 없이 일반 텍스트로만 반환해주세요.

토픽: {topic}
관련 키워드: {', '.join(keywords)}
"""

    try:
        # ChatGPT API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        # 응답 내용 가져오기
        summary = response.choices[0].message.content.strip()
        return summary
            
    except Exception as e:
        print(f"ChatGPT API 호출 오류: {e}")
        return "" 