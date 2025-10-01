import json
import os
import time

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
INPUT_QUEUE = "fila:jurisprudencia"
OUTPUT_QUEUE = "fila:resultados"


def connect_to_redis():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        print("[Agente Jurisprudencia] Conectado ao Redis!")
        return r
    except redis.exceptions.ConnectionError as e:
        print(
            f"[Agente Jurisprudencia] ERRO: Nao foi possivel conectar ao Redis. Detalhe: {e}"
        )
        return None


def processar_tarefa(tarefa: dict):
    print(f"[Agente Jurisprudencia] Recebi a tarefa: {tarefa.get('descricao')}")
    print("[Agente Jurisprudencia] Simulando busca intensiva...")
    time.sleep(5)
    resultado = {
        "id_tarefa": tarefa.get("id_tarefa"),
        "agente": "jurisprudencia",
        "status": "concluido",
        "dados": f"Analise para '{tarefa.get('descricao')}' concluida (simulacao).",
    }
    print("[Agente Jurisprudencia] Tarefa finalizada.")
    return resultado


def main():
    redis_conn = connect_to_redis()
    if not redis_conn:
        return
    print(f"[Agente Jurisprudencia] Aguardando tarefas na fila '{INPUT_QUEUE}'...")
    while True:
        try:
            _, tarefa_json = redis_conn.brpop(INPUT_QUEUE, timeout=0)
            tarefa = json.loads(tarefa_json)
            resultado = processar_tarefa(tarefa)
            redis_conn.lpush(OUTPUT_QUEUE, json.dumps(resultado))
        except Exception as e:  # pragma: no cover - laço resiliente
            print(f"[Agente Jurisprudencia] Erro inesperado: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
