import json, sys
import paho.mqtt.client as mqtt
from config import ATUADORES, CULTURAS

if len(sys.argv) < 2 or sys.argv[1] not in CULTURAS:
    print(f"uso: py atuador.py <cultura>   (culturas válidas: {', '.join(CULTURAS)})")
    sys.exit(1)
cultura = sys.argv[1]
estado = {atuador: False for atuador in ATUADORES}

def publicar_estado(client, atuador):

    client.publish(f"estufa/{cultura}/atuador/{atuador}/estado",
                   json.dumps({"ligado": estado[atuador]}), qos=1, retain=True)

def ao_conectar(client, userdata, flags, reason_code, properties):
    print(f"atuadores do {cultura} prontos")
    client.subscribe(f"estufa/{cultura}/atuador/+/comando", qos=1)
    for atuador in ATUADORES:
        publicar_estado(client, atuador)

def ao_receber(client, userdata, msg):
    atuador = msg.topic.split("/")[3]
    if atuador not in estado:
        print(f"comando para atuador desconhecido '{atuador}' ignorado")
        return
    dados = json.loads(msg.payload)
    estado[atuador] = dados["ligar"]
    print(f"{atuador} {'LIGADO' if dados['ligar'] else 'DESLIGADO'} ({dados['motivo']})")
    publicar_estado(client, atuador)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"atuador-{cultura}")
client.on_connect = ao_conectar
client.on_message = ao_receber
client.connect("localhost", 1883)
client.loop_forever()