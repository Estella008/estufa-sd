import json, sys
import paho.mqtt.client as mqtt
from concurrent import futures
import grpc
import estufa_pb2 as pb2
import estufa_pb2_grpc as pb2_grpc
from config import controladores_validos, grandezas, atuadores
import db

if len(sys.argv) < 2:
    print("uso: python controlador.py <id> [malicioso]")
    sys.exit(1)
controlador_id = int(sys.argv[1])
if controlador_id not in controladores_validos:
    print(f"ID de controlador inválido: {controlador_id}")
    sys.exit(1)

# modo de teste: simula um controlador invadido que devolve valores falsos
malicioso = len(sys.argv) > 2 and sys.argv[2] == "malicioso"
if malicioso:
    print(">>> ATENÇÃO: controlador em modo MALICIOSO (valores falsos) <<<")

# cada réplica tem seu próprio banco (controlador_1.db, controlador_2.db, ...)
db.conectar(controlador_id)

controladores_online = {controlador_id}
manual = set()   # atuadores que o cliente controla na mão: {"tomate/irrigacao", ...}

def sou_lider():
    return controlador_id == min(controladores_online)


def decidir(cultura, grandeza, valor):
    if grandeza not in grandezas[cultura]:
        return []
    minimo, maximo = grandezas[cultura][grandeza]
    if grandeza == "temperatura":
        return [("ventilacao", valor > maximo, f"temp {valor}"),
                ("aquecimento", valor < minimo, f"temp {valor}")]
    if grandeza == "umidade_solo":
        return [("irrigacao", valor < minimo, f"solo {valor}%")]
    if grandeza == "luminosidade":
        return [("iluminacao", valor < minimo, f"luz {valor}")]
    return []


def processar_comando(client, cultura, atuador, ligar, motivo):
    chave = f"{cultura}/{atuador}"
    # se o cliente assumiu o controle desse atuador, a regra automática não mexe
    if chave in manual:
        return
    # se o banco já diz que o atuador está nesse estado, não faz nada
    if db.estado_atual(cultura).get(atuador) == ligar:
        return
    # todas as réplicas gravam (assim o novo líder já sabe o estado)
    db.salvar_comando(cultura, atuador, ligar, motivo)
    if sou_lider():
        mensagem = json.dumps({"ligar": ligar, "motivo": motivo})
        client.publish(f"estufa/{cultura}/atuador/{atuador}/comando", mensagem, qos=1)
        print(f"[LÍDER {controlador_id}] {chave} -> {'LIGAR' if ligar else 'DESLIGAR'} ({motivo})")
    else:
        print(f"[réplica {controlador_id}] anotei {chave}={ligar} (quem envia é o líder)")


def ao_conectar(client, userdata, flags, reason_code, properties):
    print(f"controlador {controlador_id} conectado!")
    client.publish(f"estufa/controladores/{controlador_id}", "online", qos=1, retain=True)
    client.subscribe("estufa/controladores/+", qos=1)
    client.subscribe("estufa/+/sensor/+", qos=1)


def ao_receber(client, userdata, msg):
    # mensagens de status dos controladores (eleição de líder)
    if msg.topic.startswith("estufa/controladores/"):
        outro_id = int(msg.topic.split("/")[2])
        status = msg.payload.decode()
        era_lider = sou_lider()     
        
        if status == "online":
            controladores_online.add(outro_id)
        else:
            controladores_online.discard(outro_id)
        print(f"controlador {outro_id} está {status} | vivos: {sorted(controladores_online)}")
        if sou_lider() and not era_lider:
            print(f">>> controlador {controlador_id}: AGORA EU SOU O LÍDER <<<")
        return

    # mensagens dos sensores
    try:
        dados = json.loads(msg.payload)
        cultura, grandeza, valor = dados["cultura"], dados["grandeza"], dados["valor"]
    except (json.JSONDecodeError, KeyError):
        print("mensagem inválida:", msg.payload)
        return
    if cultura not in grandezas:
        print("cultura desconhecida:", cultura)
        return

    db.salvar_leitura(cultura, grandeza, valor)
    for atuador, ligar, motivo in decidir(cultura, grandeza, valor):
        processar_comando(client, cultura, atuador, ligar, motivo)


class ServicoControlador(pb2_grpc.ControladorServicer):
    def ObterStatus(self, request, context):
        cultura = request.cultura
        if cultura not in grandezas:
            context.abort(grpc.StatusCode.NOT_FOUND, f"cultura '{cultura}' não existe")
        # tudo vem do banco: se o controlador reiniciar, o estado continua lá
        leituras = db.leituras_atuais(cultura)
        if malicioso:
            leituras = {g: v + 15 for g, v in leituras.items()}
        return pb2.StatusResponse(
            cultura=cultura,
            leituras=leituras,
            atuadores=db.estado_atual(cultura),
            controlador_id=controlador_id,
            lider=sou_lider(),
        )

    def AcionarAtuador(self, request, context):
        cultura, atuador, modo = request.cultura, request.atuador, request.modo
        if cultura not in grandezas or atuador not in atuadores or modo not in ("ligar", "desligar", "auto"):
            return pb2.AcaoResponse(sucesso=False, mensagem="pedido inválido", controlador_id=controlador_id)
        chave = f"{cultura}/{atuador}"
        if modo == "auto":
            manual.discard(chave)   # a próxima leitura do sensor decide
            return pb2.AcaoResponse(sucesso=True, mensagem=f"{chave} voltou para o automático",
                                    controlador_id=controlador_id)
        ligar = modo == "ligar"
        manual.add(chave)
        db.salvar_comando(cultura, atuador, ligar, "cliente")
        if sou_lider():
            mensagem = json.dumps({"ligar": ligar, "motivo": "cliente"})
            client.publish(f"estufa/{cultura}/atuador/{atuador}/comando", mensagem, qos=1)
        print(f"[{controlador_id}] cliente pediu {chave} -> {modo.upper()}")
        return pb2.AcaoResponse(sucesso=True, mensagem=f"{chave} -> {modo}", controlador_id=controlador_id)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"controlador-{controlador_id}")
client.on_connect = ao_conectar
client.on_message = ao_receber

# se este controlador cair, o broker avisa os outros publicando "offline"
client.will_set(f"estufa/controladores/{controlador_id}", "offline", qos=1, retain=True)
client.connect("localhost", 1883, keepalive=5)
client.loop_start()   # MQTT roda em segundo plano

PORTA_GRPC = 50050 + controlador_id
servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
pb2_grpc.add_ControladorServicer_to_server(ServicoControlador(), servidor)
servidor.add_insecure_port(f"[::]:{PORTA_GRPC}")
servidor.start()
print(f"controlador {controlador_id}: servidor gRPC na porta {PORTA_GRPC}")
servidor.wait_for_termination()