import json, random, sys, time
import paho.mqtt.client as mqtt
from config import culturas_validas, grandezas, BROKER, PORTA


if len(sys.argv) < 2:
    print("uso: python sensor.py <cultura>")
    sys.exit(1)


cultura = sys.argv[1]

if cultura not in culturas_validas:
    print(f"cultura inválida: {cultura}")
    sys.exit(1)





client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sensor-{cultura}")
client.connect(BROKER, PORTA)
client.loop_start()

while True:
    for grandeza, (minimo, maximo) in grandezas[cultura].items():
        valor = round(random.uniform(minimo - 10, maximo + 10), 1)
        mensagem = json.dumps({"cultura": cultura, "grandeza": grandeza, "valor": valor})
        client.publish(f"estufa/{cultura}/sensor/{grandeza}", mensagem, qos=1)
        print("enviei:", mensagem)
    time.sleep(2)