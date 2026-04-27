FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

    
# Install pipenv first
RUN pip install --no-cache-dir pipenv gunicorn

# Copy dependency files
COPY Pipfile Pipfile.lock ./

# Install dependencies (using --system to install to the global python environment)
RUN pipenv install --deploy --system

# Copy the rest of your project
COPY . .

# Expose the port
EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "Intelligent_QAD_system.wsgi:application"]