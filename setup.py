from setuptools import setup, find_packages

setup(
    name="nepse-cli",
    version="1.1.0",
    description="Modern CLI tool for Meroshare IPO automation and NEPSE market data with interactive TUI",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="MenaceXnadin",
    url="https://github.com/menaceXnadin/nepse-cli",
    packages=find_packages(),
    py_modules=["main", "nepse_cli"],
    install_requires=[
        "playwright>=1.40.0",
        "prompt_toolkit>=3.0.48",
        "rich>=13.0.0",
        "colorama>=0.4.6",
        "requests>=2.25.0",
        "beautifulsoup4>=4.9.0",
        "cloudscraper>=1.2.0",
    ],
    entry_points={
        "console_scripts": [
            "nepse=nepse_cli:main",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
