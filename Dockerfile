FROM python:3.11-slim

LABEL description="Amazon product data collection system — Scrapy + Playwright + stealth"

# Install system deps required by Playwright / Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (caching layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium for Playwright
RUN python -m playwright install chromium

# Copy application code
COPY . .

# Default command: run the spider with a keyword
ENTRYPOINT ["python", "main.py"]
CMD ["--keyword", "laptop", "--pages", "2"]
