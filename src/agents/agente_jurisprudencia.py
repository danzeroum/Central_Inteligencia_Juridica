import json
import logging
import os
import time

import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
INPUT_QUEUE = "fila:jurisprudencia"
OUTPUT_QUEUE = "fila:resultados"


def connect_to_redis():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        logger.info("Conectado ao Redis!")
        return r
    except redis.exceptions.ConnectionError as e:
        logger.error("Nao foi possivel conectar ao Redis. Detalhe: %s", e)
        return None


def processar_tarefa(tarefa: dict):
    logger.info("Recebi a tarefa: %s", tarefa.get("descricao"))
    logger.debug("Simulando busca intensiva...")
    time.sleep(5)
    resultado = {
        "id_tarefa": tarefa.get("id_tarefa"),
        "agente": "jurisprudencia",
        "status": "concluido",
        "dados": f"Analise para '{tarefa.get('descricao')}' concluida (simulacao).",
    }
    logger.info("Tarefa finalizada.")
    return resultado


def main():
    redis_conn = connect_to_redis()
    if not redis_conn:
        return
    logger.info("Aguardando tarefas na fila '%s'...", INPUT_QUEUE)
    while True:
        try:
            _, tarefa_json = redis_conn.brpop(INPUT_QUEUE, timeout=0)
            tarefa = json.loads(tarefa_json)
            resultado = processar_tarefa(tarefa)
            redis_conn.lpush(OUTPUT_QUEUE, json.dumps(resultado))
        except Exception as e:  # pragma: no cover - laço resiliente
            logger.error("Erro inesperado: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
