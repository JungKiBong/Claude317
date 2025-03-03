#!/bin/bash
# setup_env.sh - 가상환경 생성 및 패키지 설치 스크립트

# 스크립트가 있는 디렉토리로 이동
cd "$(dirname "$0")"

# OS 확인
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    echo "Windows 환경 감지됨"
    PYTHON="python"
    VENV_DIR="venv"
    VENV_ACTIVATE=".\\venv\\Scripts\\activate"
    
    # Windows에서는 직접 명령어 실행
    echo "가상환경 생성 중..."
    $PYTHON -m venv $VENV_DIR
    
    echo "가상환경 활성화 중..."
    source $VENV_ACTIVATE 2>/dev/null || . $VENV_ACTIVATE || echo "가상환경 활성화 실패. 스크립트를 수동으로 실행하세요: $VENV_ACTIVATE"
    
else
    echo "Unix/Linux/macOS 환경 감지됨"
    PYTHON="python3"
    VENV_DIR="venv"
    VENV_ACTIVATE="./venv/bin/activate"
    
    echo "가상환경 생성 중..."
    $PYTHON -m venv $VENV_DIR
    
    echo "가상환경 활성화 중..."
    source $VENV_ACTIVATE || echo "가상환경 활성화 실패. 스크립트를 수동으로 실행하세요: $VENV_ACTIVATE"
fi

# pip 업그레이드
echo "pip 업그레이드 중..."
pip install --upgrade pip

# 필수 패키지 설치
echo "필수 패키지 설치 중..."
pip install -r requirements.txt

# 개발용 패키지 설치 (선택 사항)
if [ "$1" = "--dev" ]; then
    echo "개발용 패키지 설치 중..."
    pip install pytest black isort flake8
fi

# 패키지 개발 모드로 설치
echo "프로젝트 패키지 설치 중..."
pip install -e .

echo "설치 완료!"
echo "가상환경을 활성화하려면 다음 명령어를 실행하세요:"
echo "  - Windows: .\\venv\\Scripts\\activate"
echo "  - Unix/Linux/macOS: source ./venv/bin/activate"