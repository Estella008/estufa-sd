
import sys
import grpc
import estufa_pb2 as pb2
import estufa_pb2_grpc as pb2_grpc
from config import PORTA_MIDDLEWARE

with grpc.insecure_channel(f"localhost:{PORTA_MIDDLEWARE}") as canal:
    stub = pb2_grpc.EstufaStub(canal)
    try:
        if len(sys.argv) == 4:
            _, cultura, atuador, modo = sys.argv
            r = stub.DefinirModo(pb2.ModoRequest(cultura=cultura, atuador=atuador, modo=modo), timeout=5)
            print(r.mensagem)
        else:
            r = stub.ObterStatus(pb2.StatusRequest(cultura=sys.argv[1]), timeout=5)
            print(f"respondido pelo controlador {r.controlador_id} (líder? {r.lider})")
            for grandeza, valor in r.leituras.items():
                print(f"  {grandeza:<13} {valor}")
            for nome, a in r.atuadores.items():
                print(f"  {nome:<13} {'LIGADO' if a.ligado else 'desligado'} ({a.modo})")
    except grpc.RpcError as erro:
        print("falhou:", erro.code(), erro.details())
