# AI-Based Campus Lost & Found System

A beginner-friendly full-stack web application built with Flask, SQLite, HTML, CSS, and JavaScript.

## Features

- Add lost items
- Add found items
- View lost and found items separately
- Search items by name, description, or location
- Match lost and found items using simple keyword-based AI logic
- Mark items as recovered

## API Endpoints

- `POST /add_lost`
- `POST /add_found`
- `GET /items`
- `GET /match`
- `POST /mark_recovered/<item_id>`

## Run the project

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Start the app:

   ```bash
   python app.py
   ```

3. Open `http://127.0.0.1:5000`
