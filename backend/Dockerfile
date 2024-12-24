# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements.txt into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code
COPY . .

# Expose port 8080 to the host (default for your backend in docker-compose.yml)
EXPOSE 8080

# Set environment variables for Flask and MySQL connection
ENV FLASK_APP=Main.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8080

# Run the Flask application
CMD ["flask", "run"]
