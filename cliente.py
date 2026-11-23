# Cliente: acompanha e controla a estufa através do middleware.
import middleware
from config import grandezas, atuadores

while True:
    print("\n1) Ver estado   2) Acionar atuador   0) Sair")
    op = input("> ").strip()
    if op == "0":
        break
    if op not in ("1", "2"):
        continue

    cultura = input(f"cultura {list(grandezas)}: ").strip()
    try:
        if op == "1":
            r = middleware.obter_status(cultura)
            papel = "líder" if r.lider else "réplica"
            print(f"\n{cultura.upper()} (resposta do controlador {r.controlador_id}, {papel})")
            for grandeza, valor in sorted(r.leituras.items()):
                print(f"  {grandeza:<14} {valor}")
            for atuador, ligado in sorted(r.atuadores.items()):
                print(f"  {atuador:<14} {'LIGADO' if ligado else 'desligado'}")
        else:
            atuador = input(f"atuador {atuadores}: ").strip()
            modo = input("ligar / desligar / auto: ").strip().lower()
            ok, msg = middleware.acionar(cultura, atuador, modo)
            print("OK:" if ok else "FALHOU:", msg)
    except (ValueError, RuntimeError) as erro:
        print("Erro:", erro)