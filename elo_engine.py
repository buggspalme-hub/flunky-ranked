"""
Elo-Engine für Bierball-Ranked.

Kernideen:
- team_rating(): Team-Stärke ist ein Mix aus Minimum (schwächster Spieler)
  und Durchschnitt -> Bottleneck-Effekt ("man wartet auf den Schlechtesten").
- expected_score(): klassische Elo-Erwartungswert-Formel.
- distribute_weights(): verteilt die Rating-Änderung nach dem Spiel NICHT
  gleich auf alle Teammitglieder, sondern stärker auf den schwächsten Spieler
  (der ja laut team_rating() auch am meisten zur erwarteten Niederlage/Sieg
  beigetragen hat).
"""

START_RATING = 1000
K_FACTOR = 32       # wie stark sich Rating pro Spiel bewegt
ALPHA = 0.7         # Gewicht des Minimums in der Team-Stärke (0=nur Durchschnitt, 1=nur Minimum)


def team_rating(ratings: list[float], alpha: float = ALPHA) -> float:
    """Team-Stärke = Mix aus schwächstem Spieler und Team-Durchschnitt."""
    ratings = list(ratings)
    avg = sum(ratings) / len(ratings)
    return alpha * min(ratings) + (1 - alpha) * avg


def expected_score(rating_a: float, rating_b: float) -> float:
    """Wahrscheinlichkeit, dass Team/Spieler A gegen B gewinnt."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def distribute_weights(ratings: list[float]) -> list[float]:
    """
    Gewichte (summieren zu 1) für die Verteilung der Rating-Änderung
    innerhalb eines Teams. Der schwächste Spieler (niedrigstes Rating)
    bekommt das höchste Gewicht.

    Bei einem 1er-Team (1v1) kommt automatisch [1.0] heraus.
    """
    ratings = list(ratings)
    max_r = max(ratings)
    # +50 als Sockel, damit auch der staerkste Spieler im Team nicht
    # komplett mit Gewicht 0 rausfaellt, falls er == max ist.
    raw = [(max_r - r) + 50 for r in ratings]
    total = sum(raw)
    return [w / total for w in raw]
def compute_h2h(matches: list[dict], parse_team) -> dict:
    """
    Baut die Head-to-Head-Statistik aus allen Matches.

    Bei Team-Matches zaehlt jeder Spieler aus Team1 als Gegner JEDES Spielers
    aus Team2 (und umgekehrt) -> ein 3v2-Match ergibt 6 H2H-Paarungen.
    """
    h2h: dict = {}
    for row in matches:
        team1 = parse_team(row["team1_spieler"])
        team2 = parse_team(row["team2_spieler"])
        winner = str(row["ergebnis"]).strip()

        for a in team1:
            for b in team2:
                h2h.setdefault(a, {}).setdefault(b, {"wins": 0, "losses": 0})
                h2h.setdefault(b, {}).setdefault(a, {"wins": 0, "losses": 0})
                if winner == "team1":
                    h2h[a][b]["wins"] += 1
                    h2h[b][a]["losses"] += 1
                else:
                    h2h[a][b]["losses"] += 1
                    h2h[b][a]["wins"] += 1
    return h2h


def h2h_to_dataframe(h2h: dict):
    """Wandelt das h2h-dict in eine sortierte, lesbare Tabelle (DataFrame) um."""
    import pandas as pd

    rows = []
    for player, opponents in h2h.items():
        for opp, stats in opponents.items():
            games = stats["wins"] + stats["losses"]
            winrate = round(100 * stats["wins"] / games, 1) if games else 0.0
            rows.append({
                "spieler": player,
                "gegner": opp,
                "spiele": games,
                "siege": stats["wins"],
                "niederlagen": stats["losses"],
                "winrate_prozent": winrate,
            })
    df = pd.DataFrame(rows)
    return df.sort_values(["spieler", "winrate_prozent"], ascending=[True, False]).reset_index(drop=True)

def process_match(player_ratings: dict, team1: list[str], team2: list[str],
                   winner: str, k: float = K_FACTOR, alpha: float = ALPHA) -> dict:
    """
    Berechnet die neuen Ratings nach einem Match.

    player_ratings: dict {name: aktuelles_rating}
    team1, team2:    Listen von Spielernamen
    winner:          "team1" oder "team2"

    Gibt ein dict {name: delta} zurueck (Rating-Aenderung pro Spieler).
    Wendet die Aenderung NICHT selbst auf player_ratings an -> macht der Aufrufer.
    """
    r1 = [player_ratings[n] for n in team1]
    r2 = [player_ratings[n] for n in team2]

    tr1 = team_rating(r1, alpha)
    tr2 = team_rating(r2, alpha)

    e1 = expected_score(tr1, tr2)
    e2 = 1 - e1

    s1 = 1.0 if winner == "team1" else 0.0
    s2 = 1.0 - s1

    delta1_total = k * (s1 - e1)
    delta2_total = k * (s2 - e2)

    w1 = distribute_weights(r1)
    w2 = distribute_weights(r2)

    deltas = {}
    for name, w in zip(team1, w1):
        deltas[name] = delta1_total * w * len(team1)
    for name, w in zip(team2, w2):
        deltas[name] = delta2_total * w * len(team2)

    return deltas
