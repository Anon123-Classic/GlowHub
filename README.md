#  GlowHub — Salon Management System

**GlowHub** is a web-based salon management system built with **Python and Django** to help salons manage daily operations, appointments, services, staff, customers, and business activities from a centralized platform.

The project focuses on reducing manual processes and providing a structured workflow for managing salon operations.

##  Features

*  **Appointment & Booking Management**

  * Create and manage customer bookings
  * Booking validation
  * Appointment scheduling

* **Staff Management**

  * Assign staff to bookings
  * Manage staff availability
  * Support staff scheduling

*  **Service Management**

  * Manage salon services
  * Organize available services
  * Associate services with bookings

*  **Walk-in Management**

  * Record walk-in customers
  * Track walk-in services
  * Support walk-in reporting

*  **Business Reporting**

  * Booking information
  * Walk-in activity
  * Operational reporting

* 🗄️ **Database Management**

  * Structured relational data
  * SQLite database for development

## 🛠️ Technology Stack

| Technology       | Purpose                   |
| ---------------- | ------------------------- |
| **Python**       | Core programming language |
| **Django**       | Backend web framework     |
| **HTML5**        | Frontend structure        |
| **CSS3**         | Styling                   |
| **JavaScript**   | Client-side interactions  |
| **SQLite**       | Development database      |
| **Git & GitHub** | Version control           |

##  Project Structure

```text
GlowHub/
│
├── env_salon/          # Python virtual environment
├── media/              # Uploaded media and service assets
├── proj_salon/         # Django project configuration
├── salon/              # Main salon application
├── staticfiles/        # Static assets
├── db.sqlite3          # Development database
├── manage.py            # Django management utility
├── requirements.txt     # Project dependencies
└── .env                 # Environment configuration
```

##  Getting Started

### Prerequisites

Make sure you have installed:

* Python 3.x
* pip
* Git

### 1. Clone the repository

```bash
git clone https://github.com/Anon123-Classic/GlowHub.git
```

### 2. Navigate to the project

```bash
cd GlowHub
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

### 4. Activate the virtual environment

**Windows**

```bash
venv\Scripts\activate
```

**Linux/macOS**

```bash
source venv/bin/activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Apply database migrations

```bash
python manage.py migrate
```

### 7. Start the development server

```bash
python manage.py runserver
```

Open the application in your browser:

```text
http://127.0.0.1:8000/
```

##  Project Goals

GlowHub was developed to explore how software can be used to digitize and streamline small-business operations.

The project demonstrates practical experience in:

* Backend development
* Database-driven applications
* Business workflow automation
* User and staff management
* Appointment scheduling
* CRUD operations
* Reporting
* Web application architecture

##  Future Improvements

Potential improvements include:

*  Mobile-friendly interface improvements
*  Role-based access control
* Online payment integration
* Advanced business analytics
* Automated appointment notifications
* Cloud deployment
* REST API integration
* AI-powered appointment and customer insights
* Interactive business dashboard



