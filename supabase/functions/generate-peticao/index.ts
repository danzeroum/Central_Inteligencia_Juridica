import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

// CORS — restringe a origem por configuração (fallback "*" para compatibilidade).
// Defina ALLOWED_ORIGINS como lista separada por vírgulas, ex.:
//   "https://app.exemplo.com,https://staging.exemplo.com"
const ALLOWED_ORIGINS = (Deno.env.get("ALLOWED_ORIGINS") ?? "*")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);

function corsHeaders(origin: string | null): Record<string, string> {
  let allow = "*";
  if (!ALLOWED_ORIGINS.includes("*")) {
    allow = origin && ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0] ?? "";
  }
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Vary": "Origin",
  };
}

// Rate limiting — janela e limite configuráveis por ambiente.
const RATE_LIMIT_WINDOW_SECONDS = Number(Deno.env.get("RATE_LIMIT_WINDOW_SECONDS") ?? "60");
const RATE_LIMIT_MAX_REQUESTS = Number(Deno.env.get("RATE_LIMIT_MAX_REQUESTS") ?? "20");

const MODEL = "google/gemini-2.5-flash";

// SHA-256 hex de uma string (chave de cache estável).
async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

serve(async (req) => {
  const origin = req.headers.get("origin");
  const cors = corsHeaders(origin);

  if (req.method === "OPTIONS") {
    return new Response(null, { headers: cors });
  }

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { ...cors, "Content-Type": "application/json" },
    });

  try {
    if (req.method !== "POST") {
      return json({ error: "Método não permitido" }, 405);
    }

    const { area, dadosEntrada, peticaoId } = await req.json().catch(() => ({}));

    // Validação de entrada -----------------------------------------------------
    if (typeof area !== "string" || area.length === 0) {
      return json({ error: "Campo 'area' é obrigatório" }, 400);
    }
    if (dadosEntrada != null && typeof dadosEntrada !== "object") {
      return json({ error: "Campo 'dadosEntrada' deve ser um objeto" }, 400);
    }
    if (peticaoId != null && typeof peticaoId !== "string") {
      return json({ error: "Campo 'peticaoId' deve ser uma string" }, 400);
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Rate limiting ------------------------------------------------------------
    const identifier =
      req.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
      req.headers.get("cf-connecting-ip") ||
      "desconhecido";
    const now = new Date();
    const windowStart = new Date(
      Math.floor(now.getTime() / (RATE_LIMIT_WINDOW_SECONDS * 1000)) *
        (RATE_LIMIT_WINDOW_SECONDS * 1000),
    ).toISOString();

    // Incremento atômico da contagem na janela atual (função SQL).
    const { data: currentCount, error: rlError } = await supabase.rpc("increment_rate_limit", {
      p_identifier: identifier,
      p_window_start: windowStart,
    });

    if (!rlError && typeof currentCount === "number" && currentCount > RATE_LIMIT_MAX_REQUESTS) {
      return json(
        { error: "Limite de requisições excedido. Tente novamente em instantes." },
        429,
      );
    }

    // Buscar área e prompt ativo ----------------------------------------------
    const { data: areaData } = await supabase
      .from("areas_juridicas")
      .select("*")
      .eq("id", area)
      .single();

    const { data: promptData } = await supabase
      .from("prompts")
      .select("*")
      .eq("area_id", area)
      .eq("ativo", true)
      .order("versao", { ascending: false })
      .limit(1)
      .single();

    if (!promptData) {
      return json({ error: "Nenhum prompt ativo encontrado para esta área" }, 404);
    }

    // Construir o prompt substituindo variáveis {{campo}} ----------------------
    let promptContent = promptData.conteudo as string;
    Object.entries(dadosEntrada || {}).forEach(([key, value]) => {
      promptContent = promptContent.replace(new RegExp(`{{${key}}}`, "g"), String(value));
    });

    // Cache de respostas de IA -------------------------------------------------
    // Chave estável por área + prompt + versão + conteúdo final do prompt.
    const cacheKey = await sha256Hex(
      `${area}::${promptData.id}::${promptData.versao}::${promptContent}`,
    );

    const { data: cached } = await supabase
      .from("ai_response_cache")
      .select("*")
      .eq("cache_key", cacheKey)
      .maybeSingle();

    if (cached) {
      // Cache hit: sem custo de LLM.
      await supabase
        .from("ai_response_cache")
        .update({ hits: (cached.hits ?? 0) + 1, last_used_at: new Date().toISOString() })
        .eq("id", cached.id);

      await supabase.from("ai_usage_log").insert({
        area_id: areaData?.id ?? null,
        peticao_id: peticaoId ?? null,
        model: MODEL,
        cached: true,
      });

      if (peticaoId) {
        await supabase
          .from("peticoes")
          .update({ conteudo: cached.conteudo, status: "gerado" })
          .eq("id", peticaoId);
      }

      return json({ generatedContent: cached.conteudo, cached: true });
    }

    // Chamada ao LLM -----------------------------------------------------------
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY")!;
    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          {
            role: "system",
            content:
              "Você é um assistente jurídico especializado em petições. Gere petições profissionais e juridicamente embasadas.",
          },
          { role: "user", content: promptContent },
        ],
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("Erro na API Lovable:", errorText);
      return json({ error: `Erro ao gerar petição: ${response.status}` }, 502);
    }

    const data = await response.json();
    const generatedContent = data.choices?.[0]?.message?.content ?? "";
    const usage = data.usage ?? {};

    // Persistir cache e uso ----------------------------------------------------
    await supabase.from("ai_response_cache").insert({
      cache_key: cacheKey,
      area_id: areaData?.id ?? null,
      conteudo: generatedContent,
    });

    await supabase.from("ai_usage_log").insert({
      area_id: areaData?.id ?? null,
      peticao_id: peticaoId ?? null,
      model: MODEL,
      prompt_tokens: usage.prompt_tokens ?? 0,
      completion_tokens: usage.completion_tokens ?? 0,
      total_tokens: usage.total_tokens ?? 0,
      cached: false,
    });

    if (peticaoId) {
      await supabase
        .from("peticoes")
        .update({ conteudo: generatedContent, status: "gerado" })
        .eq("id", peticaoId);
    }

    return json({ generatedContent, cached: false });
  } catch (e) {
    const error = e as Error;
    console.error("Erro:", error);
    return json({ error: error.message }, 500);
  }
});
