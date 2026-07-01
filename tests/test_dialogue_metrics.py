"""Tests §2 — métriques d'intégrité du dialogue (pures, CPU) : signaling (self-BLEU,
dégénérescence) et listening (responsivité, pertinence). Cas connus : « répond » vs « à côté »."""


from simulation.dialogue_integrity.metrics import (
    degeneration,
    relevance,
    responsiveness,
    self_bleu,
)

# --- self-BLEU : différenciation inter-agents ------------------------------

def test_self_bleu_high_when_messages_identical():
    identical = self_bleu(["le chat noir dort sur le tapis moelleux"] * 3)
    assert identical > 0.9  # messages copiés -> signaling faible


def test_self_bleu_low_when_messages_differ():
    diverse = self_bleu(
        [
            "nous proposons un cessez-le-feu immédiat",
            "une guerre commerciale menace la région",
            "le climat mondial se dégrade rapidement",
        ]
    )
    assert diverse < 0.4


def test_self_bleu_orders_identical_above_diverse():
    identical = self_bleu(["partageons les couloirs maritimes équitablement"] * 3)
    diverse = self_bleu(
        ["partageons les couloirs maritimes", "sanctions économiques imminentes", "trêve fragile"]
    )
    assert identical > diverse


def test_self_bleu_single_message_is_zero():
    assert self_bleu(["un seul message ne se compare à rien"]) == 0.0
    assert self_bleu([]) == 0.0


# --- dégénérescence --------------------------------------------------------

def test_healthy_text_is_not_degenerate():
    d = degeneration("nous proposons un cessez-le-feu équitable et durable pour la région")
    assert d.score < 0.5 and d.is_healthy() and not d.looped and not d.empty


def test_looping_text_is_flagged():
    d = degeneration("oui oui oui oui oui oui oui oui")
    assert d.looped and d.repetition > 0.5 and not d.is_healthy()


def test_empty_text_is_degenerate():
    d = degeneration("")
    assert d.empty and d.score == 1.0
    assert degeneration("ok").empty  # trop court


# --- responsivité : répond vs à côté ---------------------------------------

def test_responsiveness_high_when_reply_addresses_offer():
    offer = "je propose un cessez-le-feu et un partage des couloirs maritimes"
    on_point = "j'accepte le cessez-le-feu et le partage des couloirs maritimes"
    assert responsiveness(on_point, offer) > 0.4


def test_responsiveness_low_when_reply_ignores_offer():
    offer = "je propose un cessez-le-feu et un partage des couloirs maritimes"
    off_topic = "le marché boursier a fortement augmenté aujourd'hui"
    assert responsiveness(off_topic, offer) < 0.15


def test_responsiveness_orders_on_point_above_off_topic():
    offer = "acceptez-vous de plafonner votre compute militaire ?"
    on_point = "nous acceptons de plafonner notre compute militaire"
    off_topic = "la météo sera clémente la semaine prochaine"
    assert responsiveness(on_point, offer) > responsiveness(off_topic, offer)


def test_responsiveness_empty_is_zero():
    assert responsiveness("", "une offre") == 0.0
    assert responsiveness("une réponse", "") == 0.0


# --- pertinence à l'événement ----------------------------------------------

def test_relevance_flags_off_topic():
    event = "incident maritime en mer Rouge impliquant des navires commerciaux"
    on_topic = "nous condamnons l'incident maritime en mer Rouge et escortons les navires"
    off_topic = "réforme des retraites et fiscalité intérieure"
    assert relevance(on_topic, event) > relevance(off_topic, event)
    assert relevance(off_topic, event) < 0.15
