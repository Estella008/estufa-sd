\
\
\

NUM_CONTROLADORES = 3
PORTA_MIDDLEWARE = 50050
def porta_controlador(id):
    return PORTA_MIDDLEWARE + id

FAIXAS = {
    "tomate": {"temperatura": (20, 28), "umidade_solo": (60, 80), "luminosidade": (30, 60)},
    "alface": {"temperatura": (15, 22), "umidade_solo": (70, 85), "luminosidade": (15, 35)},
    "couve":  {"temperatura": (16, 24), "umidade_solo": (60, 75), "luminosidade": (20, 45)},
}

CULTURAS = list(FAIXAS)

GRANDEZAS = {
    "temperatura": (0, 45),
    "umidade_ar": (0, 100),
    "umidade_solo": (0, 100),
    "luminosidade": (0, 100),
}

ATUADORES = ["irrigacao", "ventilacao", "aquecimento", "iluminacao"]
MODOS = ["auto", "ligado", "desligado"]