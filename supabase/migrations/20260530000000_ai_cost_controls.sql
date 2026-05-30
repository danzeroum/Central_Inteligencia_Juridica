-- ============================================================================
-- Controle de custo e observabilidade de IA (cache, rate limiting, uso/tokens)
-- Suporta as recomendações de "média prioridade" da Auditoria Multidomínio:
--   - Cache de respostas de IA (reduz custo de API para entradas repetidas)
--   - Rate limiting nas Edge Functions
--   - Monitoramento de custos/tokens por domínio (área jurídica)
-- Todas as tabelas são escritas pela Edge Function via service role
-- (que ignora RLS); o RLS abaixo apenas controla o acesso pelo cliente anon.
-- ============================================================================

-- Cache de respostas de IA -----------------------------------------------------
CREATE TABLE public.ai_response_cache (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  cache_key TEXT NOT NULL UNIQUE,            -- hash de área + prompt(+versão) + dados de entrada
  area_id UUID REFERENCES public.areas_juridicas(id) ON DELETE CASCADE,
  conteudo TEXT NOT NULL,                     -- conteúdo gerado pela IA (reutilizável)
  hits INTEGER NOT NULL DEFAULT 0,            -- quantas vezes serviu como cache
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  last_used_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Registro de uso/custo de IA --------------------------------------------------
CREATE TABLE public.ai_usage_log (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  area_id UUID REFERENCES public.areas_juridicas(id) ON DELETE SET NULL,
  peticao_id UUID REFERENCES public.peticoes(id) ON DELETE SET NULL,
  model TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  cached BOOLEAN NOT NULL DEFAULT false,      -- true = atendido pelo cache (custo zero de LLM)
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Controle de taxa (rate limiting) por janela ----------------------------------
CREATE TABLE public.ai_rate_limit (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  identifier TEXT NOT NULL,                   -- ex.: IP do chamador
  window_start TIMESTAMP WITH TIME ZONE NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0,
  UNIQUE (identifier, window_start)
);

-- Incremento atômico da contagem de requisições na janela (rate limiting) ------
CREATE OR REPLACE FUNCTION public.increment_rate_limit(
  p_identifier TEXT,
  p_window_start TIMESTAMP WITH TIME ZONE
) RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_count INTEGER;
BEGIN
  INSERT INTO public.ai_rate_limit (identifier, window_start, request_count)
  VALUES (p_identifier, p_window_start, 1)
  ON CONFLICT (identifier, window_start)
  DO UPDATE SET request_count = public.ai_rate_limit.request_count + 1
  RETURNING request_count INTO v_count;

  RETURN v_count;
END;
$$;

-- Índices ----------------------------------------------------------------------
CREATE INDEX idx_ai_cache_key ON public.ai_response_cache(cache_key);
CREATE INDEX idx_ai_cache_area ON public.ai_response_cache(area_id);
CREATE INDEX idx_ai_usage_area ON public.ai_usage_log(area_id);
CREATE INDEX idx_ai_usage_created ON public.ai_usage_log(created_at);
CREATE INDEX idx_ai_rate_identifier ON public.ai_rate_limit(identifier, window_start);

-- RLS --------------------------------------------------------------------------
ALTER TABLE public.ai_response_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_usage_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_rate_limit ENABLE ROW LEVEL SECURITY;

-- O dashboard de custos precisa ler o uso agregado (mantém o padrão de
-- "leitura pública" já usado nas demais tabelas do projeto).
CREATE POLICY "Permitir leitura pública de uso de IA"
  ON public.ai_usage_log FOR SELECT
  USING (true);

-- Cache e rate limit são internos: sem políticas para anon (apenas a Edge
-- Function, via service role, escreve/lê — o service role ignora RLS).

-- View de custo agregado por área (conveniência para o dashboard) --------------
CREATE OR REPLACE VIEW public.ai_usage_por_area AS
SELECT
  a.id   AS area_id,
  a.nome AS area_nome,
  COUNT(*)                                   AS total_geracoes,
  COUNT(*) FILTER (WHERE u.cached)           AS geracoes_em_cache,
  COALESCE(SUM(u.total_tokens), 0)           AS total_tokens,
  COALESCE(SUM(u.total_tokens) FILTER (WHERE NOT u.cached), 0) AS tokens_faturaveis
FROM public.ai_usage_log u
LEFT JOIN public.areas_juridicas a ON a.id = u.area_id
GROUP BY a.id, a.nome;
