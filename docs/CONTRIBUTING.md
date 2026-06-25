# HBD Dashboard Automation - Contributor Setup Guide

Welcome to the **Honey Bee Digital (HBD) Dashboard Automation** repository! This document outlines the project goal and provides step-by-step instructions to set up your local development environment.

---

## 1. Project Overview & Summary
The HBD Dashboard Automation platform is a decoupled analytics and automation suite comprising:
* **B2B Directory Ingestion (ETL)**: An automated pipeline that pulls directories (Google Maps, IndiaMART, JustDial, etc.) from Google Drive, cleans/deduplicates them, validates geographical coordinates against a master location database (`Location_Master_India`), and merges them into the Master Registry.
* **E-Commerce Price Scrapers**: Playwright-based stealth catalog scrapers for platforms like Zepto, JioMart, Blinkit, and Amazon.
* **Category Mapping System**: A dynamic UI portal to map raw e-commerce category trees back to HBD's master category taxonomy.

---

## 2. Contributor Onboarding & Setup Instructions

Follow these steps to set up a local development instance of the HBD Dashboard Automation application:

### Step 1: Clone the Repository
Fork the repository on GitHub to your account, clone it locally, and move to the project folder:
```bash
# Clone the repository
git clone <repository-url>

# Move to the project directory
cd <fork-folder-name>
```

### Step 2: Ensure You Are on the Latest Main Branch
Always ensure you start your work from the latest upstream changes:
```bash
# Make sure you're on the latest main
git checkout main
git pull origin main
```

### Step 3: Set Up the Local Python Virtual Environment
Create and activate an isolated Python 3.12 virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate the environment:
# On Windows (Command Prompt / PowerShell)
venv\Scripts\activate

# On macOS/Linux
# source venv/bin/activate
```

### Step 4: Install Backend Dependencies & Configure Environment
Install all required libraries, set up your local environment file, and provide the Google Cloud Service account credentials:
```bash
# Change to the backend directory
cd backend

# Install requirements
pip install -r requirements.txt
```

> [!IMPORTANT]
> **1. Create the Environment Configuration File**
> Create a file named `.env` in the `backend/` directory and populate it with the shared development values:
> ```env
> SECRET_KEY=your_secret_key
> DB_USER=your_db_user
> DB_PASSWORD=your_db_password
> DB_HOST=your_db_host
> DB_NAME=your_db_name
> JWT_SECRET_KEY=your_jwt_secret
> CELERY_BROKER_URL=redis://localhost:6379/0
> ```

> [!IMPORTANT]
> **2. Add the Google Service Account Credentials**
> Place the shared Google Cloud Service Account credentials file inside the `backend/model/` directory:
> * **Path**: `backend/model/honey-bee-digital-d96daf6e6faf.json`
> This key is required to authorize read-only access to the Google Drive ETL directory spreadsheets.

### Step 5: Install Frontend Node Modules
Navigate to the frontend workspace and install the required npm packages:
```bash
# Change to the frontend directory
cd ../frontend

# Install dependencies
npm install
```

---

## 3. Running the Project Locally

To run the application, open **two separate terminal windows** with your virtual environment activated:

### Terminal 1: Launch Backend Server
```bash
cd backend
python app.py --runserver
```
The backend API server will run on [http://localhost:5000](http://localhost:5000).

### Terminal 2: Launch Frontend Client
```bash
cd frontend
npm run dev
```
The Vite development server will boot and display the local URL (usually [http://localhost:5173](http://localhost:5173)).
