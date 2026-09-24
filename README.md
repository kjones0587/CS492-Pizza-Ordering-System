# CS492-Pizza-Ordering-System

CS492 Capstone - Pizza Restaurant Online Ordering System

## Pizza Restaurant Online Ordering System
**Course:** CS492 Computer Science Capstone  
**Instructor:** Prof. Fadi Almasri  
**Sprint 1 Dates:** 08/31/2026 – 09/13/2026 *(100% Completed & Graded)*  
**Sprint 2 Dates:** 09/14/2026 – 09/27/2026 *(100% Completed & Deployed)*  

---

## Project Overview
A responsive web application designed for a local pizzeria, supporting customer menu browsing, pizza customization, real-time cart recalculation, promo code discounts, online card payments, customer order placement, and store manager authentication and order status management.

---

## Active Team Members & Roles
- **Kellen Jones** — Scrum Master & Lead Developer *(Sprint 1: T1-03 Cart & Quantities, T1-04 Billing Integration; Sprint 2: PB-06 Online Payment Gateway & Luhn Validation, T2-06 Testing & Coordination)*
- **Michael Fabacher** — Product Owner & Developer *(Sprint 1: T1-05 Order Submission, Confirmation Receipt & Kitchen Dashboard; Sprint 2: PB-07 Store Manager Authentication, Login Portal & Route Protection)*
- **Nicholas Lattimore** — Developer *(Sprint 1: T1-02 Menu Categories, Pricing & Display; Sprint 2: PB-09 Promo Code Engine & Checkout Coupon UI, PB-08 Menu Item Management)*
- **Ayden Lotter** — Developer *(Sprint 1: T1-01 Responsive Layout & Hero Header, T1-06 Responsive Testing; Sprint 2: PB-10 Mobile Touch UX & Accessibility, PB-11 CSRF Security Hardening)*

---

## Tech Stack & Tools
- **Language:** Python 3.x
- **Framework:** Flask (with Flask-SQLAlchemy)
- **Database:** SQLite3
- **Hosting:** Render.com
- **Version Control:** Git & GitHub
- **Frontend:** HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons, Vanilla JS

---

## Sprint 1 Task Tracking & Deliverables (Completed)

*Based on the formal Sprint 1 Tracking Sheet (Start Date: 08/31/2026, Total Estimate: 62 units/hours).*

| Task ID | Story ID | Description | Assigned Owner | Estimate | Implementation Deliverables | Status |
| :---: | :---: | :--- | :--- | :---: | :--- | :---: |
| **T1-01** | **PB-01** | Create restaurant home page content and layout | **Ayden Lotter** | 8 hrs | Landing page with welcome banner, story, photos, hours with open/closed badge, map embed, and contact info (`app/routes/main.py`, `app/templates/index.html`). | ✅ Done |
| **T1-02** | **PB-02** | Build menu categories, item display, descriptions, and prices | **Nicholas Lattimore** | 12 hrs | Menu pages with categories (pizzas, sides, drinks, desserts), item descriptions, prices, size/crust options, and sold out badges (`app/routes/menu.py`, `app/templates/menu.html`). | ✅ Done |
| **T1-03** | **PB-03** | Create cart functions for add, remove, and quantity changes | **Kellen Jones** | 14 hrs | Cart setup using session cookies, pizza customization popup (sizes, crusts, toppings), +/- quantity buttons, delete items, clear cart button, and handling empty cart (`app/routes/cart.py`, `app/templates/cart.html`, `app/static/js/cart.js`). | ✅ Done |
| **T1-04** | **PB-04** | Create bill calculation and order review screen | **Nicholas Lattimore** | 10 hrs | Checkout screen showing order summary, line totals, 8.25% sales tax, pickup vs delivery fee toggle, and preventing empty orders (`app/routes/cart.py`, `app/templates/checkout.html`). | ✅ Done |
| **T1-05** | **PB-05** | Create order submission and confirmation flow | **Michael Fabacher** | 10 hrs | Customer checkout form, generated order number (`#ORD-YYYYMMDD-XXXX`), saving to SQLite, confirmation receipt with print stylesheet, and kitchen orders dashboard (`app/routes/order.py`, `app/routes/staff.py`, `app/templates/confirmation.html`, `app/templates/staff/orders.html`). | ✅ Done |
| **T1-06** | **PB-10** | Review Sprint 1 pages for responsive layout | **Ayden Lotter** | 8 hrs | Tested layout on mobile, tablet, and desktop screens, checking mobile navigation menu, buttons, and spacing (`app/static/css/style.css`, `app/templates/base.html`). | ✅ Done |
| **Total** | | | | **62 hrs** | | **100% Complete** |

---

## Sprint 2 Task Tracking & Deliverables (Completed)

*Based on the formal Sprint 2 Tracking Sheet (Start Date: 09/14/2026, Total Estimate: 65 units/hours).*

| Task ID | Story ID | Description | Assigned Team Members | Estimate | Implementation Deliverables | Status |
| :---: | :---: | :--- | :--- | :---: | :--- | :---: |
| **T2-01** | **PB-06** | Design and validate online payment workflow | **Michael Fabacher & Kellen Jones** | 12 hrs | Mock payment gateway service with Modulo 10 Luhn checksum card validation, card brand detection (Visa, MC, Amex, Discover), future expiration checking, sandbox decline rules, interactive checkout payment form, screen-darkening decline spotlight, and confirmation receipt badges (`app/services/payment.py`, `app/templates/checkout.html`, `app/routes/order.py`). | ✅ Complete |
| **T2-02** | **PB-07** | Create secure manager login and access control | **Nicholas Lattimore & Michael Fabacher** | 10 hrs | Staff authentication backend (`/staff/login`, `/staff/logout`), password hashing, session management, `@staff_login_required` decorator, and manager login portal with navbar session indicator (`app/routes/staff.py`, `app/templates/staff/login.html`). | ✅ Complete |
| **T2-03** | **PB-08** | Build menu management for adding, editing, and disabling items | **Ayden Lotter & Nicholas Lattimore** | 14 hrs | Staff portal menu item management (`/staff/menu`) to update base prices, edit descriptions, toggle item availability (in stock / out of stock), and create new items with category image fallbacks. | ✅ Complete |
| **T2-04** | **PB-09** | Build discount and promotion management | **Michael Fabacher & Nicholas Lattimore** | 10 hrs | Coupon engine with percentage and fixed discounts, minimum subtotal thresholds (`/cart/apply-promo`), checkout promo code input form, AJAX bill recalculation, usage count tracking, and protected default code guardrails (`app/routes/cart.py`, `app/templates/checkout.html`, `app/templates/staff/promos.html`). | ✅ Complete |
| **T2-05** | **PB-11** | Review input validation, data protection, and payment data handling | **Nicholas Lattimore & Ayden Lotter** | 8 hrs | CSRF token protection on all POST forms, secure session cookies (`HTTPOnly`, `SameSite=Lax`), and AJAX request CSRF header injection. | ✅ Complete |
| **T2-06** | **PB-10 / PB-12** | Mobile touch UX polish, testing notes, and deployment prep | **Kellen Jones & Ayden Lotter** | 11 hrs | Minimum 46px touch targets for pizza customization, quantity stepper touch sizing, iOS zoom prevention (16px inputs), sticky mobile checkout bar, and automated regression test suite (**58 passing tests**) (`app/static/css/style.css`, `tests/`). | ✅ Complete |
| **Total** | | | | **65 hrs** | | **100% Complete** |

---

## Demo & Testing Credentials

For instructor and peer review of our Sprint 2 features:

* **Manager Login Portal:** Navigate to `/staff/login` (or click "Staff Login" in footer / navbar).
  * **Username:** `manager` (or click the **Auto-Fill** button on the login screen)
  * **Password:** `pizza123`
* **Test Promo Codes (PB-09):**
  * `WELCOME10` — 10% discount off entire cart subtotal.
  * `SAVE5` — $5.00 off orders with a subtotal of $25.00 or higher.
  * `ALMASRI` — VIP Faculty Pass ($0.00 complimentary lunch for Professor Almasri).
* **Test Payment Cards (PB-06):**
  * Any valid 16-digit Luhn-compliant card number (e.g. standard Visa test numbers starting with `4` or use the **Auto-Fill Demo Visa** button).
  * Use the **Test Decline Card** button (or card ending in `...0002`) to test simulated sandbox decline handling.

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
