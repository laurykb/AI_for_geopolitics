"""Horloge à sauts pour les deadlines humaines (tour / scrutin) — `game_api._clock`.

Chaque LECTURE avance d'un grand pas : une deadline posée à la lecture n est déjà
échue à la lecture n+1. Le silence du joueur expire donc sans horloge réelle, et la
course « POST tardif vs deadline » se rejoue en déterministe. À réserver aux tests
où l'humain reste muet : sous cette horloge, tout tour expire avant qu'un POST
puisse l'attraper."""


class SteppingClock:
    def __init__(self, start: float = 1_000_000.0, step: float = 3600.0):
        self.now = start
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now
