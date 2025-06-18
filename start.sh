#!/bin/bash

# Step 1: Install Python backend dependencies
echo "Installing backend dependencies..."
pip install -r requirements.txt

# Step 2: Start the Flask backend (flask_backend.py should have `app = Flask(__name__)`)
echo "Starting Flask backend..."
gunicorn flask_backend:app --bind 0.0.0.0:8000 &

# Step 3: Install frontend dependencies
echo "Installing frontend dependencies..."
npm install

# Step 4: Build and run the frontend
echo "Building and starting frontend..."
npm run build
npm start
