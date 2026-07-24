<<<<<<< HEAD
# LifeSync — Smart Calendar, Diary and Weather Assistant

LifeSync is a web-based personal productivity app built with Python and Django.
It brings calendar management, a personal diary, live weather forecasting, and
automated notifications together in one dashboard — with an interface that
genuinely shifts between day and night and reacts to real weather conditions.

## Features

- **Smart calendar** — an interactive month grid for events, birthdays, and
  reminders, with per-day detail pages and category filters.
- **Daily diary & notes** — journal entries with a mood tag; each entry can
  optionally capture that day's weather automatically.
- **Real-time weather** — current conditions and a 5-day forecast for any# LifeSync — Smart Calendar, Diary and Weather Assistant

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
  city, powered by the OpenWeatherMap API.
- **Dynamic day/night theme** — the whole interface (not just one widget)
  shifts palette based on local time or a manual preference.
- **Weather-based animation** — a lightweight animated sky (sun, moon,
  stars, drifting clouds, rain, snow, lightning) reflecting live conditions.
- **Notification system** — automatic reminders for events, birthdays, and
  custom reminders due today or tomorrow, plus a management command that
  can be scheduled via cron/Task Scheduler.

## Tech stack

Python · Django · HTML/CSS/JavaScript · Bootstrap 5 · SQLite (default) or
MySQL · OpenWeatherMap API

## Project structure

```
lifesync/
├── lifesync/        # project settings, root URLs
├── accounts/        # auth, user profile (city + theme preference)
├── core/             # landing page + main dashboard
├── planner/          # calendar: events, birthdays, reminders
├── diary/             # diary entries
├── weather/           # OpenWeatherMap integration
├── notifications/      # auto-generated reminders
├── templates/           # all HTML, organised by app
└── static/               # style.css + theme/calendar/weather/notifications JS
```

Each app follows the same layout: `models.py`, `admin.py`, `forms.py`,
`views.py`, `urls.py`.

## Setup

**1. Extract the project and open a terminal in the `lifesync/` folder.**

**2. Create and activate a virtual environment.**

```bash
python -m venv venv
# macOS/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate
```

**3. Install dependencies.**

```bash
pip install -r requirements.txt
```

**4. Configure your environment.**

```bash
cp .env.example .env
```

Open `.env` and fill in `OPENWEATHERMAP_API_KEY` (get a free key at
[openweathermap.org/api](https://openweathermap.org/api) — the free
"Current Weather Data" plan is all you need; new keys can take up to a
couple of hours to activate). The app still runs without a key, it just
won't be able to show live weather until one is added.

**5. Set up the database.**

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

**6. Run the development server.**

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`, register an account, and set your city under
**Profile settings** for weather and dashboard data.

## Using MySQL instead of SQLite

1. `pip install mysqlclient`
2. Create a database: `CREATE DATABASE lifesync;`
3. In `.env`, uncomment and fill in the `DB_ENGINE=mysql` block.
4. Re-run `python manage.py migrate`.

## Automated notifications

Notifications are generated on the fly whenever a user visits their
dashboard or notifications page — no background worker required. For a
more "production-like" setup, you can also run:

```bash
python manage.py generate_notifications
```

and schedule that command with cron (Linux/macOS) or Task Scheduler
(Windows) to run daily.

## Admin panel

Visit `/admin/` and log in with the superuser you created to browse and
edit all data directly — handy for demos and debugging.

## Possible future enhancements

- Real-time updates via WebSockets instead of polling on page load
- Email/SMS delivery for reminders, not just in-app notifications
- Recurring (non-birthday) events, e.g. weekly meetings
- Exporting diary entries to PDF
- A public REST API (Django REST Framework) for a future mobile app

## License

Built as a college mini-project. Free to use and adapt for learning purposes.
=======
# Lifesync
An intelligent personal planning application developed using Python and Django that integrates calendar management, weather forecasting, daily diary, notes, event scheduling, notifications, and reminder features to improve productivity and daily organization.
>>>>>>> 4389fe0c3baa0917845532290efa1bf1dcfaa1f0
