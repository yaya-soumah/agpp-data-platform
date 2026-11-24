FROM apache/airflow:3.4.0-python3.12

RUN pip install --no-cache-dir apache-airflow-providers-docker \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.4.0/constraints-3.12.txt"
