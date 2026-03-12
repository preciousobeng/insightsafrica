# InsightsAfrica — QA Test Script
**Platform:** https://insightsafrica.org
**Version:** 0.3.0
**Tester:** _______________
**Date:** _______________

---

## How to use this script
- Work through each section top to bottom
- Mark each test: ✅ Pass | ❌ Fail | ⚠️ Partial / Unexpected behaviour
- For any ❌ or ⚠️, note: what you did, what you expected, what actually happened
- Test on both **desktop** and **mobile** where marked
- Use both **dark mode** and **light mode** (toggle in top nav)

---

## 1. Landing Page

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 1.1 | Open https://insightsafrica.org | Page loads, dark background, nav visible | | |
| 1.2 | Toggle theme (sun/moon icon in nav) | Switches between dark and light mode | | |
| 1.3 | Click Platform in nav | Scrolls to product cards section | | |
| 1.4 | Click Data in nav | Scrolls to data sources strip | | |
| 1.5 | Click About in nav | Scrolls to About section | | |
| 1.6 | Click Contact in nav | Scrolls to contact form | | |
| 1.7 | Click "Explore the Platform" button | Goes to Ghana hub (hub.html) | | |
| 1.8 | Click "Enter Platform" in top nav | Goes to Ghana hub | | |
| 1.9 | Click "Sign In" in top nav | Goes to login page | | |
| 1.10 | Resize browser to mobile width (< 768px) | Hamburger menu appears, nav links hidden | | |
| 1.11 | Open hamburger menu on mobile | Dropdown shows Platform, Data, About, Contact, Sign In | | |
| 1.12 | Scroll to bottom | Footer visible with links and copyright | | |

---

## 2. Contact Form

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 2.1 | Scroll to Contact section | Form visible with Name, Email, Enquiry Type, Message fields | | |
| 2.2 | Submit form with all fields empty | Browser validation prevents submission | | |
| 2.3 | Enter invalid email (e.g. "notanemail") | Validation error shown | | |
| 2.4 | Fill all fields correctly and submit | Green success message: "Message sent — we'll be in touch shortly." | | |
| 2.5 | Submit the form twice quickly | Second submission handled gracefully (no duplicate send) | | |

---

## 3. Sign Up Flow

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 3.1 | Go to login page, click "Create account" | Sign up form shows: Full Name, Email, Password, Confirm Password | | |
| 3.2 | Submit with mismatched passwords | Error shown: passwords do not match | | |
| 3.3 | Submit with valid details | Thank-you message shown, confirmation email sent | | |
| 3.4 | Check inbox for confirmation email | Email arrives from noreply@insightsafrica.org, branded correctly | | |
| 3.5 | Click confirmation link in email | Redirected to hub.html, logged in | | |
| 3.6 | Try to sign up again with same email | Appropriate error shown | | |

---

## 4. Sign In Flow

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 4.1 | Sign in with correct credentials | Redirected to Ghana hub | | |
| 4.2 | Sign in with wrong password | Error message shown | | |
| 4.3 | Use "Forgot password" link | Password reset email received | | |
| 4.4 | Click reset link in email | Redirected to set new password | | |

---

## 5. Ghana Hub (hub.html)

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 5.1 | Open Ghana hub | Four product cards visible: FloodWatch, MineWatch, CropWatch, HeatWatch | | |
| 5.2 | Click country switcher to Nigeria | Goes to Nigeria hub | | |
| 5.3 | Click FloodWatch card | Opens Ghana FloodWatch | | |
| 5.4 | Click MineWatch card | Opens Ghana MineWatch | | |
| 5.5 | Click CropWatch card | Opens Ghana CropWatch | | |
| 5.6 | Click HeatWatch card | Opens Ghana HeatWatch | | |

---

## 6. Ghana FloodWatch (/flood/)

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 6.1 | Page loads | Map of Ghana visible, rainfall layer loaded | | |
| 6.2 | Click through month selector | Map updates to show different months (2024–2025) | | |
| 6.3 | Click on a region/district | Tooltip or info shown | | |
| 6.4 | Check legend | Rainfall scale visible and readable | | |
| 6.5 | Mobile view | Map and controls usable on small screen | | |

---

## 7. Ghana MineWatch (/mine/)

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 7.1 | Page loads | Map with galamsey site markers visible | | |
| 7.2 | Click a site marker | Site info shown (name, change data) | | |
| 7.3 | Toggle between NDVI / NDWI / Change layers | Map updates correctly | | |
| 7.4 | Before/after imagery visible | Change detection images load | | |

---

## 8. Ghana CropWatch (/crop/)

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 8.1 | Page loads | NDVI map of Ghana farming regions visible | | |
| 8.2 | Step through time periods | Map updates showing vegetation change | | |
| 8.3 | Stress scoring visible | Regions show crop stress indicators | | |

---

## 9. Ghana HeatWatch (/heat/)

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 9.1 | Page loads | Heat map visible, cities listed (Accra, Kumasi, Tamale) | | |
| 9.2 | Select a city | Map centres and shows that city's heat data | | |
| 9.3 | Legend readable | Temperature scale visible | | |

---

## 10. Nigeria Hub (/nigeria/hub.html)

| # | Action | Expected | Result | Notes |
|---|--------|----------|--------|-------|
| 10.1 | Open Nigeria hub | Four product cards visible | | |
| 10.2 | Country switcher shows Ghana option | Clicking it returns to Ghana hub | | |
| 10.3 | FloodWatch loads | Nigeria rainfall map, 37 states visible | | |
| 10.4 | MineWatch loads | 10 mining sites visible (artisanal + oil/gas) | | |
| 10.5 | CropWatch loads | Nigeria NDVI composites load | | |
| 10.6 | HeatWatch loads | Lagos, Kano, Abuja heat maps load | | |

---

## 11. Cross-cutting Checks

| # | Check | Expected | Result | Notes |
|---|-------|----------|--------|-------|
| 11.1 | All external links open correctly | No broken links | | |
| 11.2 | Page load speed (rough) | Each page loads within 5 seconds on a normal connection | | |
| 11.3 | No console errors (F12 → Console) | No red errors on any page | | |
| 11.4 | All images/maps load | No broken image icons | | |
| 11.5 | Theme preference persists on refresh | Dark/light mode remembered after reload | | |

---

## Bug Report Template

For each issue found, copy and fill in:

```
Bug #:
Page/Section:
Severity: Critical / Major / Minor / Cosmetic
Steps to reproduce:
  1.
  2.
  3.
Expected result:
Actual result:
Browser & device:
Screenshot: [attach if possible]
```

---

*Thanks for testing — feedback goes to info@insightsafrica.org*
