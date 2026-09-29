# LifeSync — Smart Calendar, Diary and Weather Assistant

LifeSync is a web-based personal productivity application built with Python and Django. It combines calendar management, a personal diary, live weather forecasting, and automated notifications into a single dashboard. The interface dynamically switches between day and night themes and reacts to real-time weather conditions.

## Features

- **Smart Calendar** — Interactive monthly calendar for events, birthdays, and reminders with per-day details and category filters.
- **Daily Diary & Notes** — Create journal entries with mood tracking and optionally save the day's weather.
- **Real-Time Weather** — Current weather conditions and a 5-day forecast using the OpenWeatherMap API.
- **Dynamic Day/Night Theme** — Automatically changes the application's appearance based on local time or user preference.
- **Weather-Based Animation** — Animated sky featuring the sun, moon, stars, clouds, rain, snow, and lightning based on live weather.
- **Notification System** — Automatic reminders for events, birthdays, and custom reminders due today or tomorrow.

## Tech Stack

- Python
- Django
- HTML
- CSS
- JavaScript
- Bootstrap 5
- SQLite (Default)
- MySQL (Optional)
- OpenWeatherMap API

## Project Structure

```text
lifesync/
├── backend/
│   ├── lifesync/          # Project settings and URLs
│   ├── accounts/          # User authentication and profiles
│   ├── core/              # Landing page and dashboard
│   ├── planner/           # Calendar, events, birthdays, reminders
│   ├── diary/             # Personal diary
│   ├── weather/           # Weather integration
│   ├── notifications/     # Notification system
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JavaScript, images
│   ├── manage.py
│   └── requirements.txt
└── frontend/
```

Each Django application contains:

- `models.py`
- `views.py`
- `urls.py`
- `forms.py`
- `admin.py`

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Akshayyy19/Lifesync.git
cd Lifesync
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### Activate the virtual environment

**Windows**

```bash
venv\Scripts\activate
```

**Linux/macOS**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Configure environment variables

Copy:

```text
backend/.env.example
```

to

```text
backend/.env
```

Then add your OpenWeatherMap API key.

### 5. Apply migrations

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

### 6. Create a superuser

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

Open your browser and visit:

```
http://127.0.0.1:8000/
```

## Using MySQL (Optional)

1. Install mysqlclient

```bash
pip install mysqlclient
```

2. Create a MySQL database.

3. Update your `.env` file with the MySQL database credentials.

4. Run:

```bash
python manage.py migrate
```

## Notifications

Generate notifications manually:

```bash
python manage.py generate_notifications
```

You can automate this command using Windows Task Scheduler or Cron Jobs.

## Admin Panel

Visit:

```
http://127.0.0.1:8000/admin/
```

Log in using the superuser account.

## Future Improvements

- Real-time updates using WebSockets
- Email and SMS notifications
- Recurring events
- Export diary entries to PDF
- Mobile application using Django REST Framework APIs

## License

This project was developed as a college mini project for educational purposes. Feel free to use and modify it for learning.
