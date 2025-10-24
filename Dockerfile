FROM python:3.12

WORKDIR /code
#RUN
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY . .

EXPOSE 8080
CMD ["fastapi", "run", "main.py", "--port", "8080"]
