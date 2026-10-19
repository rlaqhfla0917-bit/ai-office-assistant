FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY officeops/ officeops/
RUN mkdir -p /app/data && useradd --system --create-home appuser && chown -R appuser:appuser /app/data
USER appuser
EXPOSE 8501
CMD ["uvicorn","officeops.web:app","--host","0.0.0.0","--port","8501"]
