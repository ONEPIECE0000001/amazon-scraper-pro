from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="amazon-data-collector",
    version="1.0.0",
    author="Amazon Data Collection System",
    author_email="contact@example.com",
    description="A professional Amazon e-commerce product data collection system with intelligent anti-crawling and distributed architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/amazon-data-collector",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Topic :: Internet :: WWW/HTTP",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "amazon-collector=main:main",
        ],
    },
    keywords="scrapy, playwright, web-scraping, amazon, data-collection, anti-crawling",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/amazon-data-collector/issues",
        "Source": "https://github.com/yourusername/amazon-data-collector",
        "Documentation": "https://github.com/yourusername/amazon-data-collector/blob/main/README.md",
    },
)