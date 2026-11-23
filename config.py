BROKER = "localhost"
PORTA = 1883

grandezas = {
    "tomate": {
        "temperatura": (20, 28),
        "umidade_ar": (60, 80),
        "umidade_solo": (60, 80),
        "luminosidade": (30, 70),
    },
    "alface": {
        "temperatura": (15, 22),
        "umidade_ar": (60, 80),
        "umidade_solo": (70, 90),
        "luminosidade": (15, 40),
    },
    "morango": {
        "temperatura": (15, 25),
        "umidade_ar": (65, 75),
        "umidade_solo": (60, 75),
        "luminosidade": (20, 50),
    },
}

culturas_validas = list(grandezas.keys())

atuadores = ["irrigacao", "ventilacao", "aquecimento", "iluminacao"]


regras = {
    "temperatura": ("aquecimento", "ventilacao"),
    "umidade_solo": ("irrigacao", None),
    "luminosidade": ("iluminacao", None),
    "umidade_ar": (None, None),
}

controladores_validos = [1, 2, 3]