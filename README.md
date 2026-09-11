# Lucky 99 v3

Frontend + Flask backend + SQLite database.

Features:
- Separate player login page
- Player website has NO admin link/button
- Admin is available only at the separate `/admin/login` URL
- 0–99 keypad
- Every submission saved separately with player name
- 36-hour automatic deletion
- Admin 0–99 input/count table + Refresh
- Admin winning number
- Admin `RESET ALL INPUTS` with confirmation; deletes all active inputs and makes all counts zero
- Public result page

Run:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Player: http://127.0.0.1:5000/
Admin: http://127.0.0.1:5000/admin/login
Result: http://127.0.0.1:5000/result

Default admin:
admin / admin123

For a real deployment, use environment variables for credentials and SECRET_KEY and put admin behind additional network/auth controls. Hiding the URL alone is not security.

## Result behavior

The player has a **Check Result** button/page. Once the admin publishes a winning number, that result remains visible to users until the admin publishes a new winning number. Resetting user inputs does **not** remove the published result.
