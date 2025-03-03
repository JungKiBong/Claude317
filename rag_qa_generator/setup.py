from setuptools import setup, find_packages

setup(
    name="rag_qa_generator",
    version="0.1.0",
    description="LLM 기반 RAG Q&A 및 SQL 자동 생성기",
    author="RAG Q&A Generator Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "pandas>=1.3.0",
        "sqlparse>=0.4.2",
        "rich>=10.0.0",
        "tiktoken>=0.3.0",
        "streamlit>=1.18.0",
        "openai>=1.0.0",
        "anthropic>=0.3.0",
        "transformers>=4.20.0", 
        "huggingface_hub>=0.13.0",
        "openpyxl>=3.0.9",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "black>=21.5b2",
            "isort>=5.9.1",
            "flake8>=3.9.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "rag-qa-generator=run:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)