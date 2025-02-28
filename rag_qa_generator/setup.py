#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM RAG Q&A 및 SQL 자동 생성기 - 설치 스크립트
"""

from setuptools import setup, find_packages
import os

# README 파일 읽기
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# 버전 정보
VERSION = "1.0.0"

# 기본 의존성 패키지
BASE_REQUIREMENTS = [
    "tqdm>=4.66.0",
    "sqlparse>=0.4.3",
    "requests>=2.28.2",
    "backoff>=2.2.1",
    "python-dotenv>=1.0.0",
    "rich>=13.4.2",
    "typer>=0.9.0",
]

# 모델별 의존성 패키지
OLLAMA_REQUIREMENTS = [
    "langchain>=0.1.0",
    "langchain-community>=0.0.10",
]

HUGGINGFACE_REQUIREMENTS = [
    "torch>=2.0.0",
    "transformers>=4.36.0",
    "accelerate>=0.21.0",
]

OPENAI_REQUIREMENTS = [
    "openai>=1.0.0",
    "tiktoken>=0.5.0",
]

CLAUDE_REQUIREMENTS = [
    "anthropic>=0.5.0",
]

UI_REQUIREMENTS = [
    "streamlit>=1.22.0",
    "pandas>=1.5.3",
    "openpyxl>=3.1.2",
    "pydeck>=0.8.0",
    "plotly>=5.14.0",
]

DEV_REQUIREMENTS = [
    "pytest>=7.3.1",
    "black>=23.3.0",
    "flake8>=6.0.0",
    "isort>=5.12.0",
    "mypy>=1.3.0",
]

setup(
    name="rag_qa_generator",
    version=VERSION,
    author="RAG Q&A Generator Team",
    author_email="example@example.com",
    description="대규모 언어 모델을 활용한 RAG Q&A 및 SQL 자동 생성기",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/rag_qa_generator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=BASE_REQUIREMENTS,
    extras_require={
        "ollama": OLLAMA_REQUIREMENTS,
        "huggingface": HUGGINGFACE_REQUIREMENTS,
        "openai": OPENAI_REQUIREMENTS,
        "claude": CLAUDE_REQUIREMENTS,
        "ui": UI_REQUIREMENTS,
        "dev": DEV_REQUIREMENTS,
        "all": OLLAMA_REQUIREMENTS + HUGGINGFACE_REQUIREMENTS + 
               OPENAI_REQUIREMENTS + CLAUDE_REQUIREMENTS + UI_REQUIREMENTS,
    },
    entry_points={
        "console_scripts": [
            "rag-qa-generator=rag_qa_generator.run:main",
        ],
    },
    include_package_data=True,
)