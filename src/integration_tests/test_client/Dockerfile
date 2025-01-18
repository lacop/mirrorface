FROM python:3.12-slim

RUN pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install transformers==4.48.0

COPY client.py .
