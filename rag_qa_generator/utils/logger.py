import logging
import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme

# Rich 테마 설정
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "critical": "bold white on red",
    "success": "bold green",
})

console = Console(theme=custom_theme)

class CustomFormatter(logging.Formatter):
    """로그 포맷터 커스터마이징"""
    
    def format(self, record):
        # 로그 레벨에 따른 색상 설정
        if record.levelno == logging.INFO:
            record.levelname = f"[info]{record.levelname}[/info]"
        elif record.levelno == logging.WARNING:
            record.levelname = f"[warning]{record.levelname}[/warning]"
        elif record.levelno == logging.ERROR:
            record.levelname = f"[error]{record.levelname}[/error]"
        elif record.levelno == logging.CRITICAL:
            record.levelname = f"[critical]{record.levelname}[/critical]"
            
        return super().format(record)

def setup_logger(
    name: str = "rag_qa_generator",
    level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True
) -> logging.Logger:
    """로거 설정 및 반환
    
    Args:
        name: 로거 이름
        level: 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        log_file: 로그 파일 경로 (None이면 파일 로깅 안함)
        console_output: 콘솔 출력 여부
        
    Returns:
        설정된 로거 객체
    """
    # 로그 레벨 문자열을 숫자로 변환
    log_level = getattr(logging, level.upper())
    
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # 기존 핸들러 제거 (중복 로깅 방지)
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 로그 포맷 설정
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 콘솔 출력 설정
    if console_output:
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_time=False,
            show_path=False
        )
        rich_handler.setLevel(log_level)
        rich_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(rich_handler)
    
    # 파일 로깅 설정
    if log_file is not None:
        # 디렉토리가 없으면 생성
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter(log_format, datefmt=date_format)
        )
        logger.addHandler(file_handler)
    
    return logger

def get_logger(
    name: str = "rag_qa_generator",
    level: str = "INFO"
) -> logging.Logger:
    """기본 설정된 로거 반환
    
    Args:
        name: 로거 이름
        level: 로그 레벨
        
    Returns:
        설정된 로거 객체
    """
    return setup_logger(name=name, level=level)

def get_time_logger(
    name: str = "rag_qa_generator", 
    level: str = "INFO"
) -> logging.Logger:
    """시간 기반 로그 파일을 사용하는 로거 반환
    
    Args:
        name: 로거 이름
        level: 로그 레벨
        
    Returns:
        설정된 로거 객체
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(f"logs/{name}_{timestamp}.log")
    return setup_logger(name=name, level=level, log_file=log_file)

# 성공 메시지를 위한 유틸리티 함수
def log_success(logger: logging.Logger, message: str) -> None:
    """성공 메시지 로깅 (INFO 레벨로 로깅하지만 녹색으로 표시)"""
    if isinstance(logger.handlers[0], RichHandler):
        console.print(f"[success]{message}[/success]")
    else:
        logger.info(message)

# 진행 상황 표시 유틸리티
def log_progress(
    logger: logging.Logger, 
    current: int, 
    total: int, 
    message: str = "진행 중"
) -> None:
    """진행 상황 표시 로깅"""
    percentage = (current / total) * 100
    progress_msg = f"{message}: {current}/{total} ({percentage:.1f}%)"
    logger.info(progress_msg)