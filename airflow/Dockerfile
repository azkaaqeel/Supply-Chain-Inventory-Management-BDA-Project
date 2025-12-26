FROM apache/airflow:2.10.2-python3.8

USER root

# Install system dependencies (including Java for Spark in Phase 2)
RUN apt-get update && apt-get install -y \
    build-essential \
    openjdk-17-jdk \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Spark client for spark-submit (Phase 2)
ENV SPARK_HOME=/opt/spark
ENV PATH=$SPARK_HOME/bin:$PATH
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64

RUN curl -L https://archive.apache.org/dist/spark/spark-3.5.1/spark-3.5.1-bin-hadoop3.tgz \
    | tar -xz -C /opt/ \
    && mv /opt/spark-3.5.1-bin-hadoop3 /opt/spark \
    && chown -R airflow:root /opt/spark

USER airflow

# Install Python packages for MongoDB connectivity
# Note: Only pymongo needed for Phase 1 (direct Python-MongoDB connection)
RUN pip install --no-cache-dir pymongo==4.8.0

# Install Redis client for Phase 2 (with async_timeout dependency)
RUN pip install --no-cache-dir redis==5.0.8 async-timeout==5.0.1

# Set working directory
WORKDIR /opt/airflow

