FROM apache/spark:3.5.1

USER root

# Install Python packages needed for Spark jobs
RUN pip install --no-cache-dir \
    redis==5.0.8 \
    pymongo==4.8.0 \
    async-timeout==5.0.1

USER ${spark_uid}

