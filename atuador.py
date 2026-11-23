import json, sys
import paho.mqtt.client as mqtt
from config import culturas_validas, atuadores, regras, grandezas

if len(sys.argv) < 2:
    print("uso: python atuador.py <cultura>")
    sys.exit(1)
cultura = sys.argv[1]

estado = {atuador: False for atuador in atuadores}


if cultura not in culturas_validas:
    print(f"cultura inválida: {cultura}")
    sys.exit(1)

def ao_conectar(client, userdata, flags, reason_code, properties):
    print(f"atuadores do {cultura} prontos")
    client.subscribe(f"estufa/{cultura}/atuador/+/comando", qos=1)

def ao_receber(client, userdata, msg):
    atuador = msg.topic.split("/")[3]
    dados = json.loads(msg.payload)
    estado[atuador] = dados["ligar"]
    print(f"{atuador} {'LIGADO' if dados['ligar'] else 'DESLIGADO'} ({dados['motivo']})")
    print("   estado atual:", estado)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"atuador-{cultura}")
client.on_connect = ao_conectar
client.on_message = ao_receber
client.connect("localhost", 1883)
client.loop_forever()