# CS492-Pizza-Ordering-System

CS492 Capstone - Pizza Restaurant Online Ordering System

## Pizza Restaurant Online Ordering System
**Course:** CS492 Computer Science Capstone  
**Instructor:** Prof. Fadi Almasri  
**Sprint 1 Start Date:** 08/31/2026  

---

## Project Overview
A responsive web application designed for a local pizzeria, supporting customer menu browsing, order customization, automated bill calculation, customer order placement, and store manager/staff live order updates.

---

## Active Team Members & Roles
- **Michael Fabacher** — Product Owner *(Sprint 1 Task Owner: T1-05)*
- **Kellen Jones** — Scrum Master & Development Team *(Sprint 1 Task Owner: T1-03; Sprint 2 Task Owner: T2-06)*
- **Ayden Lotter** — Development Team *(Sprint 1 Task Owner: T1-01 & T1-06)*
- **Nicholas Lattimore** — Development Team *(Sprint 1 Task Owner: T1-02 & T1-04)*

---

## Tech Stack & Tools
- **Language:** Python 3.x
- **Framework:** Flask (with Flask-SQLAlchemy)
- **Database:** SQLite3
- **Hosting:** Render.com
- **Version Control:** Git & GitHub
- **Frontend:** HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons, Vanilla JS

---

## Sprint 1 Task Tracking & Deliverables

*Based on the formal Sprint 1 Tracking Sheet (Start Date: 08/31/2026, Total Estimate: 62 units/hours).*

| Task ID | Story ID | Description | Assigned Owner | Estimate | Implementation Deliverables | Status |
| :---: | :---: | :--- | :--- | :---: | :--- | :---: |
| **T1-01** | **PB-01** | Create restaurant home page content and layout | **Ayden Lotter** | 8 hrs | Landing page with welcome banner, story, photos, hours with open/closed badge, map embed, and contact info (`app/routes/main.py`, `app/templates/index.html`). | ✅ Done |
| **T1-02** | **PB-02** | Build menu categories, item display, descriptions, and prices | **Nicholas Lattimore** | 12 hrs | Menu pages with categories (pizzas, sides, drinks, desserts), item descriptions, prices, size/crust options, and sold out badges (`app/routes/menu.py`, `app/templates/menu.html`). | ✅ Done |
| **T1-03** | **PB-03** | Create cart functions for add, remove, and quantity changes | **Kellen Jones** | 14 hrs | Cart setup using session cookies, pizza customization popup (sizes, crusts, toppings), +/- quantity buttons, delete items, clear cart button, and handling empty cart (`app/routes/cart.py`, `app/templates/cart.html`, `app/static/js/cart.js`). | ✅ Done |
| **T1-04** | **PB-04** | Create bill calculation and order review screen | **Nicholas Lattimore** | 10 hrs | Checkout screen showing order summary, line totals, 8.25% sales tax, pickup vs delivery fee toggle, and preventing empty orders (`app/routes/cart.py`, `app/templates/checkout.html`). | ✅ Done |
| **T1-05** | **PB-05** | Create order submission and confirmation flow | **Michael Fabacher** | 10 hrs | Customer checkout form (name, email, phone, address), generated order number (`#ORD-YYYYMMDD-XXXX`), saving to SQLite database, order confirmation receipt, and kitchen orders dashboard (`app/routes/order.py`, `app/routes/staff.py`, `app/templates/confirmation.html`, `app/templates/staff/orders.html`). | ✅ Done |
| **T1-06** | **PB-10** | Review Sprint 1 pages for responsive layout | **Ayden Lotter** | 8 hrs | Tested layout on mobile, tablet, and desktop screens, checking mobile navigation menu, buttons, and spacing (`app/static/css/style.css`, `app/templates/base.html`). | ✅ Done |
| **Total** | | | | **62 hrs** | | **100% Complete** |

---

## Local Development Setup

### 1. Clone the repository
```bash
git clone https://github.com/kjones0587/CS492-Pizza-Ordering-System.git
cd CS492-Pizza-Ordering-System
```

### 2. Create and activate virtual environment
```bash
# Windows:
py -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the application
```bash
python run.py
```
Open your browser and navigate to `http://localhost:5000`. The database automatically initializes and seeds default menu categories and items on first run.

### 5. Run the Automated Tests
```bash
pytest
```
*Executes all 6 test suites verifying tasks T1-01 through T1-06.*

---

## Deployment to Render.com

This repository contains everything required for zero-configuration 1-click deployment on Render:

1. Push this repository to GitHub:
   ```bash
   git add .
   git commit -m "Sprint 1 delivery: tasks T1-01 through T1-06"
   git push origin main
   ```
2. Log into [Render.com](https://render.com) and click **New +** -> **Web Service**.
3. Select your GitHub repository `kjones0587/CS492-Pizza-Ordering-System`.
4. Configure the service:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn run:app`
5. Click **Deploy Web Service**. Render will automatically build the service, initialize the SQLite database, and launch your live public URL!
