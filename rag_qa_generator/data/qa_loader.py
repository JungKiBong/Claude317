import json
import os
import csv
import random
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import pandas as pd

class QALoader:
    """Q&A 데이터 로드 및 처리를 위한 클래스"""
    
    def __init__(self, qa_path: Optional[Union[str, Path]] = None):
        """
        Args:
            qa_path: Q&A 데이터 파일 경로 (JSON, CSV 등)
        """
        self.qa_path = Path(qa_path) if qa_path else None
        self.qa_data = []
        self.by_difficulty = {
            "easy": [],
            "medium": [],
            "hard": []
        }
    
    def load_qa_data(self) -> List[Dict[str, Any]]:
        """Q&A 데이터 파일 로드 및 파싱
        
        Returns:
            Q&A 데이터 리스트
            
        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            ValueError: 파일 형식이 지원되지 않거나 잘못된 경우
        """
        if not self.qa_path:
            return []
        
        # 파일 존재 여부 확인
        if not self.qa_path.exists():
            raise FileNotFoundError(f"Q&A 데이터 파일이 존재하지 않습니다: {self.qa_path}")
        
        # 파일 확장자에 따라 적절한 로더 사용
        file_ext = self.qa_path.suffix.lower()
        
        try:
            if file_ext == '.json':
                self._load_from_json()
            elif file_ext == '.csv':
                self._load_from_csv()
            elif file_ext in ['.xlsx', '.xls']:
                self._load_from_excel()
            else:
                raise ValueError(f"지원되지 않는 파일 형식입니다: {file_ext}")
        except Exception as e:
            raise ValueError(f"Q&A 데이터 파일 로드 실패: {str(e)}")
        
        # 난이도별 데이터 분류
        self._categorize_by_difficulty()
        
        return self.qa_data
    
    def _load_from_json(self) -> None:
        """JSON 파일에서 Q&A 데이터 로드"""
        with open(self.qa_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # JSON 형식이 배열인지 확인
        if isinstance(data, list):
            self.qa_data = data
        elif isinstance(data, dict) and 'qa_data' in data:
            # {'qa_data': [...]} 형식인 경우
            self.qa_data = data['qa_data']
        else:
            raise ValueError("JSON 파일이 유효한 Q&A 데이터 형식이 아닙니다.")
        
        # 필수 필드 확인
        self._validate_qa_data()
    
    def _load_from_csv(self) -> None:
        """CSV 파일에서 Q&A 데이터 로드"""
        # CSV 파일 읽기
        df = pd.read_csv(self.qa_path, encoding='utf-8')
        
        # 필수 필드 확인
        required_columns = ['question', 'answer']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"CSV 파일에 필수 컬럼이 누락되었습니다: {', '.join(missing_columns)}")
        
        # 데이터프레임을 딕셔너리 리스트로 변환
        self.qa_data = df.to_dict(orient='records')
        
        # SQL 필드가 없는 경우 빈 문자열로 설정
        for item in self.qa_data:
            if 'sql' not in item or pd.isna(item['sql']):
                item['sql'] = ''
            
            if 'difficulty' not in item or pd.isna(item['difficulty']):
                item['difficulty'] = 'medium'  # 기본 난이도
    
    def _load_from_excel(self) -> None:
        """Excel 파일에서 Q&A 데이터 로드"""
        # Excel 파일 읽기
        df = pd.read_excel(self.qa_path)
        
        # 필수 필드 확인
        required_columns = ['question', 'answer']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Excel 파일에 필수 컬럼이 누락되었습니다: {', '.join(missing_columns)}")
        
        # 데이터프레임을 딕셔너리 리스트로 변환
        self.qa_data = df.to_dict(orient='records')
        
        # SQL 필드가 없는 경우 빈 문자열로 설정
        for item in self.qa_data:
            if 'sql' not in item or pd.isna(item['sql']):
                item['sql'] = ''
            
            if 'difficulty' not in item or pd.isna(item['difficulty']):
                item['difficulty'] = 'medium'  # 기본 난이도
    
    def _validate_qa_data(self) -> None:
        """Q&A 데이터 형식 검증
        
        Raises:
            ValueError: 데이터 형식이 잘못된 경우
        """
        for i, item in enumerate(self.qa_data):
            # 필수 필드 확인
            if 'question' not in item:
                raise ValueError(f"항목 #{i+1}에 'question' 필드가 누락되었습니다.")
            if 'answer' not in item:
                raise ValueError(f"항목 #{i+1}에 'answer' 필드가 누락되었습니다.")
            
            # SQL 필드가 없는 경우 빈 문자열로 설정
            if 'sql' not in item:
                item['sql'] = ''
            
            # 난이도 필드가 없는 경우 기본값 설정
            if 'difficulty' not in item:
                item['difficulty'] = 'medium'  # 기본 난이도
    
    def _categorize_by_difficulty(self) -> None:
        """Q&A 데이터를 난이도별로 분류"""
        # 난이도별 분류 초기화
        self.by_difficulty = {
            "easy": [],
            "medium": [],
            "hard": []
        }
        
        # 각 항목을 난이도별로 분류
        for item in self.qa_data:
            difficulty = item.get('difficulty', 'medium').lower()
            
            # 지원되지 않는 난이도는 중간으로 설정
            if difficulty not in self.by_difficulty:
                difficulty = 'medium'
            
            self.by_difficulty[difficulty].append(item)
    
    def get_examples_by_difficulty(
        self, 
        difficulty: str, 
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """지정된 난이도의 예제 데이터 가져오기
        
        Args:
            difficulty: 난이도 ('easy', 'medium', 'hard')
            count: 가져올 예제 수
            
        Returns:
            예제 데이터 리스트
        """
        if not self.qa_data:
            self.load_qa_data()
        
        difficulty = difficulty.lower()
        if difficulty not in self.by_difficulty:
            raise ValueError(f"지원되지 않는 난이도입니다: {difficulty}")
        
        # 해당 난이도의 데이터가 충분히 있는지 확인
        available = self.by_difficulty[difficulty]
        if not available:
            # 다른 난이도에서 대체
            for alt_difficulty in ['medium', 'easy', 'hard']:
                if self.by_difficulty[alt_difficulty]:
                    available = self.by_difficulty[alt_difficulty]
                    break
        
        # 요청된 수만큼 무작위로 선택 (중복 없이)
        sample_count = min(count, len(available))
        if sample_count == 0:
            return []
        
        return random.sample(available, sample_count)
    
    def save_qa_data(
        self, 
        data: List[Dict[str, Any]], 
        output_path: Union[str, Path],
        format: str = 'json'
    ) -> None:
        """Q&A 데이터를 파일로 저장
        
        Args:
            data: 저장할 Q&A 데이터
            output_path: 출력 파일 경로
            format: 출력 형식 ('json', 'csv', 'excel')
            
        Raises:
            ValueError: 지원되지 않는 출력 형식인 경우
        """
        output_path = Path(output_path)
        
        # 디렉토리가 존재하지 않으면 생성
        output_dir = output_path.parent
        if not output_dir.exists():
            output_dir.mkdir(parents=True)
        
        # 형식에 따라 저장
        format = format.lower()
        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        elif format == 'csv':
            # 데이터프레임으로 변환 후 CSV로 저장
            df = pd.DataFrame(data)
            df.to_csv(output_path, index=False, encoding='utf-8')
            
        elif format == 'excel':
            # 데이터프레임으로 변환 후 Excel로 저장
            df = pd.DataFrame(data)
            df.to_excel(output_path, index=False)
            
        else:
            raise ValueError(f"지원되지 않는 출력 형식입니다: {format}")