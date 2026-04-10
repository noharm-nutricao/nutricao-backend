FROM python:3.11-slim

WORKDIR /app

# copiar requirements
COPY requirements.txt .

# instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# copiar código
COPY . .

# porta da API
EXPOSE 5000

# rodar flask
CMD ["python", "mobile.py"]