#!/usr/bin/env python
import os
import sys
import argparse
from pathlib import Path

def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(description="RAG Q&A 및 SQL 생성기")
    parser.add_argument("--gui", action="store_true", help="GUI 모드로 실행")
    
    # 나머지 인자는 CLI 모드로 전달
    parser.add_argument("args", nargs="*", help="CLI 모드에 전달할 추가 인자")
    
    return parser.parse_args()

def run_cli_mode(args):
    """CLI 모드 실행
    
    Args:
        args: CLI에 전달할 인자 리스트
    """
    # main.py 모듈 가져오기
    try:
        import main
        sys.argv = ["main.py"] + args
        main.main()
    except ImportError:
        print("오류: main.py 모듈을 찾을 수 없습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"CLI 모드 실행 중 오류 발생: {str(e)}")
        sys.exit(1)

def run_gui_mode():
    """GUI 모드 실행 (Streamlit)"""
    try:
        # Streamlit 사용 가능 여부 확인
        import streamlit
        
        # 현재 디렉토리 경로 가져오기
        current_dir = Path(__file__).parent.absolute()
        
        # Streamlit 앱 파일 경로
        streamlit_app_path = current_dir / "streamlit_app.py"
        
        if not streamlit_app_path.exists():
            print(f"오류: Streamlit 앱 파일을 찾을 수 없습니다: {streamlit_app_path}")
            sys.exit(1)
        
        # Streamlit 실행 명령
        os.system(f"streamlit run {streamlit_app_path}")
        
    except ImportError:
        print("오류: Streamlit이 설치되어 있지 않습니다. 'pip install streamlit'로 설치하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"GUI 모드 실행 중 오류 발생: {str(e)}")
        sys.exit(1)

def main():
    """메인 함수"""
    args = parse_args()
    
    if args.gui:
        # GUI 모드 실행
        run_gui_mode()
    else:
        # CLI 모드 실행
        run_cli_mode(args.args)

if __name__ == "__main__":
    main()