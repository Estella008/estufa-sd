import json, os, random, sys, threading
from concurrent import futures
import grpc
import paho.mqtt.client as mqtt
import estufa_pb2 as pb2
import estufa_pb2_grpc as pb2_grpc
from config import ATUADORES, CULTURAS, FAIXAS, GRANDEZAS, MODOS, NUM_CONTROLADORES, porta_controlador

if len(sys.argv) < 2 or sys.argv[1] not in [str(i) for i in range(1, NUM_CONTROLADORES + 1)]:
    print(f"uso: py controlador.py <id>   (id de 1 a {NUM_CONTROLADORES})")
    sys.exit(1)
MEU_ID = int(sys.argv[1])
ARQUIVO = f"dados_controlador_{MEU_ID}.json"

if os.path.exists(ARQUIVO):
    with open(ARQUIVO) as f:
        salvo = json.load(f)
    print(f"estado recuperado de {ARQUIVO}")
else:
    salvo = {}

leituras = salvo.get("leituras", {})
ultimo_comando = salvo.get("comandos", {})
modos = salvo.get("modos", {})

trava = threading.RLock()

falha_injetada = False

def salvar():
    with open(ARQUIVO, "w") as f:
        json.dump({"leituras": leituras, "comandos": ultimo_comando, "modos": modos}, f, indent=2)

controladores_online = {MEU_ID}

def sou_lider():
    return MEU_ID == min(controladores_online)

def decidir(cultura, grandeza, valor):
    if grandeza not in FAIXAS[cultura]:
        return []
    minimo, maximo = FAIXAS[cultura][grandeza]
    meio = (minimo + maximo) / 2

    def regra(atuador, ligar_se, desligar_se):
        if ligar_se:
            return [(atuador, True, f"{grandeza} {valor}")]
        if desligar_se:
            return [(atuador, False, f"{grandeza} {valor}")]
        return []

    if grandeza == "temperatura":
        return (regra("ventilacao", valor > maximo, valor <= meio) +
                regra("aquecimento", valor < minimo, valor >= meio))
    if grandeza == "umidade_solo":
        return regra("irrigacao", valor < minimo, valor >= meio)
    if grandeza == "luminosidade":
        return regra("iluminacao", valor < minimo, valor >= meio)
    return []

def aplicar(cultura, atuador, ligar, motivo, forcar=False):
    chave = f"{cultura}/{atuador}"
    if ultimo_comando.get(chave) == ligar and not forcar:
        return
    ultimo_comando[chave] = ligar
    if sou_lider():
        mensagem = json.dumps({"ligar": ligar, "motivo": motivo})
        client.publish(f"estufa/{cultura}/atuador/{atuador}/comando", mensagem, qos=1)
        print(f"[LÍDER {MEU_ID}] {chave} -> {'LIGAR' if ligar else 'DESLIGAR'} ({motivo})")
    else:
        print(f"[réplica {MEU_ID}] anotei {chave}={ligar}")

class ServicoControlador(pb2_grpc.ControladorServicer):

    def ObterStatus(self, request, context):
        cultura = request.cultura
        if cultura not in FAIXAS:
            context.abort(grpc.StatusCode.NOT_FOUND, f"cultura '{cultura}' não existe")
        with trava:
            resposta = pb2.StatusResponse(
                cultura=cultura,
                leituras={g: v for k, v in leituras.items()
                          for c, g in [k.split("/")] if c == cultura},
                atuadores={a: pb2.Atuador(ligado=ultimo_comando.get(f"{cultura}/{a}", False),
                                          modo=modos.get(f"{cultura}/{a}", "auto"))
                           for a in ATUADORES},
                faixas={g: pb2.Faixa(minimo=lo, maximo=hi) for g, (lo, hi) in FAIXAS[cultura].items()},
                controlador_id=MEU_ID,
                lider=sou_lider(),
            )
        if falha_injetada:

            for g in resposta.leituras:
                resposta.leituras[g] += random.uniform(15, 30)
            for a in resposta.atuadores.values():
                a.ligado = not a.ligado
            print(f"[INVADIDO {MEU_ID}] respondi valores FALSOS sobre {cultura}")
        return resposta

    def DefinirModo(self, request, context):
        cultura, atuador, modo = request.cultura, request.atuador, request.modo
        if cultura not in FAIXAS or atuador not in ATUADORES or modo not in MODOS:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "cultura, atuador ou modo inválido")
        with trava:
            modos[f"{cultura}/{atuador}"] = modo
            print(f"[{MEU_ID}] modo de {cultura}/{atuador} agora é '{modo}'")
            if modo != "auto":
                aplicar(cultura, atuador, modo == "ligado", "manual pelo painel", forcar=True)
            salvar()
        return pb2.ModoResponse(ok=True, mensagem=f"controlador {MEU_ID} aplicou", confirmacoes=1)

    def InjetarFalha(self, request, context):
        global falha_injetada
        falha_injetada = request.ativa
        print(f"!!! controlador {MEU_ID}: modo INVADIDO {'ATIVADO' if falha_injetada else 'desativado'} !!!")
        return pb2.ModoResponse(ok=True, mensagem="ok", confirmacoes=1)

def ao_conectar(client, userdata, flags, reason_code, properties):
    print(f"controlador {MEU_ID} conectado!")
    client.publish(f"estufa/controladores/{MEU_ID}", "online", qos=1, retain=True)
    client.subscribe("estufa/controladores/+", qos=1)
    client.subscribe("estufa/+/sensor/+", qos=1)

def ao_receber(client, userdata, msg):
    if msg.topic.startswith("estufa/controladores/"):
        outro_id = int(msg.topic.split("/")[2])
        status = msg.payload.decode()
        with trava:
            era_lider = sou_lider()
            if status == "online":
                controladores_online.add(outro_id)
            else:
                controladores_online.discard(outro_id)
            print(f"controlador {outro_id} está {status} | vivos: {sorted(controladores_online)}")
            if sou_lider() and not era_lider:
                print(f">>> controlador {MEU_ID}: AGORA EU SOU O LÍDER <<<")
        return

    dados = json.loads(msg.payload)
    cultura = dados.get("cultura")
    if cultura not in FAIXAS:
        print(f"leitura de cultura desconhecida ignorada: {cultura}")
        return

    grandeza, valor = dados.get("grandeza"), dados.get("valor")
    if grandeza not in GRANDEZAS or not isinstance(valor, (int, float)) \
            or not GRANDEZAS[grandeza][0] <= valor <= GRANDEZAS[grandeza][1]:
        print(f"leitura impossível descartada: {cultura} {grandeza}={valor}")
        return
    with trava:
        leituras[f"{cultura}/{dados['grandeza']}"] = dados["valor"]
        for atuador, ligar, motivo in decidir(cultura, dados["grandeza"], dados["valor"]):
            if modos.get(f"{cultura}/{atuador}", "auto") == "auto":
                aplicar(cultura, atuador, ligar, motivo)
        salvar()

def sincronizar_com_outra_replica():
    for outro_id in range(1, NUM_CONTROLADORES + 1):
        if outro_id == MEU_ID:
            continue
        try:
            with grpc.insecure_channel(f"localhost:{porta_controlador(outro_id)}") as canal:
                stub = pb2_grpc.ControladorStub(canal)
                for cultura in CULTURAS:
                    r = stub.ObterStatus(pb2.StatusRequest(cultura=cultura), timeout=1)
                    for atuador, info in r.atuadores.items():
                        modos[f"{cultura}/{atuador}"] = info.modo
                        ultimo_comando[f"{cultura}/{atuador}"] = info.ligado
            print(f"estado sincronizado com o controlador {outro_id}")
            return
        except grpc.RpcError:
            continue
    print("nenhuma outra réplica respondeu; seguindo com o estado do disco")

sincronizar_com_outra_replica()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"controlador-{MEU_ID}")
client.on_connect = ao_conectar
client.on_message = ao_receber

client.will_set(f"estufa/controladores/{MEU_ID}", "offline", qos=1, retain=True)
client.connect("localhost", 1883, keepalive=5)
client.loop_start()

servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
pb2_grpc.add_ControladorServicer_to_server(ServicoControlador(), servidor)
servidor.add_insecure_port(f"[::]:{porta_controlador(MEU_ID)}")
servidor.start()
print(f"controlador {MEU_ID}: servidor gRPC na porta {porta_controlador(MEU_ID)}")
servidor.wait_for_termination()