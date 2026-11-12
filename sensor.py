import json, math, random, sys, time
import paho.mqtt.client as mqtt
from config import ATUADORES, CULTURAS, FAIXAS, GRANDEZAS

if len(sys.argv) < 2 or sys.argv[1] not in CULTURAS:
    print(f"uso: py sensor.py <cultura>   (culturas válidas: {', '.join(CULTURAS)})")
    sys.exit(1)
cultura = sys.argv[1]

faixa = FAIXAS[cultura]
valores = {
    "temperatura": faixa["temperatura"][1] + 3,
    "umidade_ar": 70.0,
    "umidade_solo": faixa["umidade_solo"][0] - 8,
    "luminosidade": 20.0,
}
atuadores = {a: False for a in ATUADORES}
fase = random.uniform(0, 2 * math.pi)

def simular():
    ciclo = math.sin(2 * math.pi * time.time() / 360 + fase)
    externa = 23 + 10 * ciclo
    v = valores
    v["temperatura"] += 0.1 * (externa - v["temperatura"])
    v["temperatura"] += 0.8 if atuadores["aquecimento"] else 0
    v["temperatura"] -= 0.8 if atuadores["ventilacao"] else 0
    v["umidade_ar"] += 0.05 * (85 - v["umidade_ar"])
    v["umidade_ar"] -= 1.5 if atuadores["ventilacao"] else 0
    v["umidade_solo"] -= 0.5
    v["umidade_solo"] += 2.5 if atuadores["irrigacao"] else 0
    v["luminosidade"] = max(0, 70 * ciclo) + (10 if atuadores["iluminacao"] else 0)
    for grandeza, (minimo, maximo) in GRANDEZAS.items():
        v[grandeza] = min(maximo, max(minimo, v[grandeza] + random.gauss(0, 0.2)))

def ao_conectar(client, userdata, flags, reason_code, properties):

    client.subscribe(f"estufa/{cultura}/atuador/+/estado", qos=1)

def ao_receber(client, userdata, msg):
    atuador = msg.topic.split("/")[3]
    if atuador in atuadores:
        atuadores[atuador] = json.loads(msg.payload)["ligado"]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sensor-{cultura}")
client.on_connect = ao_conectar
client.on_message = ao_receber
client.connect("localhost", 1883)
client.loop_start()

while True:
    simular()
    for grandeza, valor in valores.items():
        mensagem = json.dumps({"cultura": cultura, "grandeza": grandeza, "valor": round(valor, 1)})
        client.publish(f"estufa/{cultura}/sensor/{grandeza}", mensagem, qos=1)
    print("enviei:", "  ".join(f"{g}={v:.1f}" for g, v in valores.items()))
    time.sleep(2)