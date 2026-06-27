"""
Update-Skript für Bierball-Ranked direkt auf Google Sheets.

Voraussetzung:
- credentials.json (Service-Account-Key) liegt im selben Ordner
- Das Google Sheet wurde mit der Service-Account-Mail (aus credentials.json,
  Feld "client_email") als Editor geteilt
- pip install gspread google-auth pandas

Nutzung:
- Trage Matches normal in Google Sheets ein
- Führe dieses Skript aus: python update_ranking.py
- Das Players-Sheet und der H2H-Tab werden automatisch neu berechnet und überschrieben
"""

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from elo_engine import process_match, START_RATING, K_FACTOR, ALPHA, compute_h2h, h2h_to_dataframe

# ---- Anpassen ----
SHEET_ID = "160fta0W3onci59lJSOqD4Sx6w7jiG3AzWaYIHIF2fMw"
PLAYERS_TAB = "Players"
MATCHES_TAB = "Matches"
CREDENTIALS_FILE = "credentials.json"
# ------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def parse_team(cell: str) -> list[str]:
    return [name.strip() for name in str(cell).split(",")]


def main():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)

    sheet = gc.open_by_key(SHEET_ID)
    players_ws = sheet.worksheet(PLAYERS_TAB)
    matches_ws = sheet.worksheet(MATCHES_TAB)

    players_df = pd.DataFrame(players_ws.get_all_records())
    matches_df = pd.DataFrame(matches_ws.get_all_records())

    # Startwerte: alle Spieler bei START_RATING, 0 Spiele, 0 Siege
    ratings = {name: START_RATING for name in players_df["name"]}
    spiele = {name: 0 for name in players_df["name"]}
    siege = {name: 0 for name in players_df["name"]}

    for _, row in matches_df.iterrows():
        team1 = parse_team(row["team1_spieler"])
        team2 = parse_team(row["team2_spieler"])
        winner = str(row["ergebnis"]).strip()

        for name in team1 + team2:
            if name not in ratings:
                ratings[name] = START_RATING
                spiele[name] = 0
                siege[name] = 0

        deltas = process_match(ratings, team1, team2, winner, k=K_FACTOR, alpha=ALPHA)

        for name, delta in deltas.items():
            ratings[name] += delta
            spiele[name] += 1
            if (winner == "team1" and name in team1) or (winner == "team2" and name in team2):
                siege[name] += 1

    result = pd.DataFrame({
        "name": list(ratings.keys()),
        "rating": [round(ratings[n], 1) for n in ratings],
        "spiele": [spiele[n] for n in ratings],
        "siege": [siege[n] for n in ratings],
    }).sort_values("rating", ascending=False).reset_index(drop=True)

    # Players-Sheet komplett neu schreiben
    players_ws.clear()
    players_ws.update([result.columns.values.tolist()] + result.values.tolist())

    print("Players-Sheet aktualisiert:")
    print(result.to_string(index=False))

    # ---- H2H-Statistik berechnen und in eigenen Tab schreiben ----
    h2h = compute_h2h(matches_df.to_dict("records"), parse_team)
    h2h_df = h2h_to_dataframe(h2h)

    try:
        h2h_ws = sheet.worksheet("H2H")
    except gspread.exceptions.WorksheetNotFound:
        h2h_ws = sheet.add_worksheet(title="H2H", rows=200, cols=10)

    h2h_ws.clear()
    h2h_ws.update([h2h_df.columns.values.tolist()] + h2h_df.values.tolist())

    print("\nH2H-Tab aktualisiert.")


if __name__ == "__main__":
    main()