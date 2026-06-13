/* fiscal-data.js — dados fictícios do fio-de-ouro fiscal (uma escrituração SPED).
   Valores em centavos? Não: usar números e formatar com fmtBRL. PII mascarada. */

const BRL = (n) => 'R$\u00a0' + n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtNum = (n) => n.toLocaleString('pt-BR');

const ESCRITURACAO = {
  db_id: 'esc_9f3a21c7',
  empresa: 'Metalúrgica Andrade Indústria Ltda',
  cnpj_masked: '12.***.***/0001-90',
  arquivo: 'EFD-ICMS-IPI_122025_metalurgica.txt',
  tamanho: '84,2 MB',
  regime: 'lucro_real',
  uf: 'SP',
  periodo: '2025-12',
  registros: 184320,
  blocos: ['0', 'C', 'D', 'E', 'G', 'H', 'K', '1', '9'],
};

// Linhas do log de processamento assíncrono (job)
const JOB_LOG = [
  { t: 120, msg: 'Arquivo recebido · validando assinatura e layout EFD' },
  { t: 520, msg: 'Bloco 0 · cadastro de participantes e itens (12.480 registros)' },
  { t: 1180, msg: 'Bloco C · documentos fiscais — NF-e / NFC-e (98.220 registros)' },
  { t: 1980, msg: 'Bloco E · apuração de ICMS e IPI (E100/E110/E520)' },
  { t: 2480, msg: 'Bloco K · controle de produção e estoque' },
  { t: 3050, msg: 'Cruzando registros · executando 47 regras de validação' },
  { t: 3600, msg: 'Processamento concluído · 6 achados (3 erros, 3 avisos)' },
];

const ACHADOS = [
  { id: 'ac1', sev: 'ERRO', regra: 'C170-CST', registro: 'C170', linha: 48213, campo: 'CST_ICMS',
    desc: 'CST 060 (ICMS-ST cobrado anteriormente) sem informar o valor de ICMS-ST recolhido.',
    dica: 'Preencher VL_ICMS_ST ou ajustar a CST para 000/020 conforme a operação.' },
  { id: 'ac2', sev: 'ERRO', regra: 'E110-SALDO', registro: 'E110', linha: 181002, campo: 'VL_SLD_APURADO',
    desc: 'Saldo de ICMS apurado diverge do computado a partir de débitos e créditos do período.',
    dica: 'Recalcular após corrigir os C170; divergência atual de R$ 3.200,00.' },
  { id: 'ac3', sev: 'ERRO', regra: 'C100-CHAVE', registro: 'C100', linha: 30774, campo: 'CHV_NFE',
    desc: 'Chave de acesso da NF-e com dígito verificador inválido (44 dígitos).',
    dica: 'Conferir a chave junto ao XML de origem; possível erro de digitação.' },
  { id: 'ac4', sev: 'AVISO', regra: 'C190-ALIQ', registro: 'C190', linha: 52900, campo: 'ALIQ_ICMS',
    desc: 'Alíquota de 25% incomum para o NCM informado nesta operação interna.',
    dica: 'Verificar enquadramento; alíquota usual para o NCM é 18%.' },
  { id: 'ac5', sev: 'AVISO', regra: '0150-IE', registro: '0150', linha: 312, campo: 'IE',
    desc: 'Participante (fornecedor) sem inscrição estadual informada.',
    dica: 'Complementar o cadastro do participante quando aplicável.' },
  { id: 'ac6', sev: 'AVISO', regra: 'E520-IPI', registro: 'E520', linha: 181440, campo: 'VL_CRED_IPI',
    desc: 'Crédito de IPI lançado sem documento fiscal vinculado identificado.',
    dica: 'Vincular a nota de entrada correspondente ao crédito.' },
];

// Registros candidatos à edição em lote (resolvem o achado C170-CST)
const LOTE_REGISTROS = [
  { id: 'r1', registro: 'C170', linha: 48213, item: 'Chapa de aço 2,0mm', cst_atual: '060', cst_novo: '000', vl: 12480.00 },
  { id: 'r2', registro: 'C170', linha: 48590, item: 'Perfil U 100x50', cst_atual: '060', cst_novo: '000', vl: 8320.50 },
  { id: 'r3', registro: 'C170', linha: 49102, item: 'Tubo galvanizado 1"', cst_atual: '060', cst_novo: '000', vl: 4115.00 },
  { id: 'r4', registro: 'C170', linha: 50233, item: 'Solda MIG 1,2mm', cst_atual: '060', cst_novo: '000', vl: 2280.75 },
];

const APURACAO = [
  { trib: 'ICMS', reg: 'E110', deb: 184320.55, cred: 142880.12, ajuste: 3200.00, saldo: 44640.43,
    sit: 'devedor', computado: 44640.43, declarado: 41440.43 },
  { trib: 'PIS', reg: 'M200', deb: 12430.80, cred: 9880.40, ajuste: 0, saldo: 2550.40,
    sit: 'devedor', computado: 2550.40, declarado: 2550.40 },
  { trib: 'COFINS', reg: 'M600', deb: 57210.33, cred: 45480.10, ajuste: 0, saldo: 11730.23,
    sit: 'devedor', computado: 11730.23, declarado: 11730.23 },
  { trib: 'ICMS-ST', reg: 'E210', deb: 8940.00, cred: 8940.00, ajuste: 0, saldo: 0,
    sit: 'equilibrado', computado: 0, declarado: 0 },
  { trib: 'IPI', reg: 'E520', deb: 21300.00, cred: 24110.50, ajuste: 0, saldo: 2810.50,
    sit: 'credor', computado: 2810.50, declarado: 2810.50 },
];

// Diff da retificação (trecho original × retificado)
const DIFF = [
  { ln: '|C170|01|...|', orig: '|...|CST_ICMS=060|VL_ICMS_ST=|...|', ret: '|...|CST_ICMS=000|VL_ICMS=2246,40|...|', tipo: 'chg', reg: 'C170 · linha 48213' },
  { ln: '|C170|02|...|', orig: '|...|CST_ICMS=060|VL_ICMS_ST=|...|', ret: '|...|CST_ICMS=000|VL_ICMS=1497,69|...|', tipo: 'chg', reg: 'C170 · linha 48590' },
  { ln: '|E110|', orig: '|E110|41440,43|...|', ret: '|E110|44640,43|...|', tipo: 'chg', reg: 'E110 · saldo recalculado' },
  { ln: '|C100|', orig: '|C100|...|CHV=3520...8841|', ret: '|C100|...|CHV=3520...8847|', tipo: 'chg', reg: 'C100 · linha 30774' },
];

const PERDCOMP_TIPOS = [
  { id: 'per', nome: 'PER — Pedido de Restituição', desc: 'Restituição de crédito tributário federal apurado.' },
  { id: 'dcomp', nome: 'DCOMP — Declaração de Compensação', desc: 'Compensação de crédito com débitos próprios.' },
  { id: 'rest_ressarc', nome: 'Ressarcimento de IPI', desc: 'Ressarcimento de saldo credor de IPI.' },
];

const PERDCOMP_FICHA = {
  tipo: 'DCOMP — Declaração de Compensação',
  numero: '41028.92831.130626.1.3.04-9920',
  periodo: '2025-12',
  origem: 'Saldo credor de IPI — E520',
  credito: 2810.50,
  selic: 84.31,
  total: 2894.81,
  debito_compensado: 'PIS a recolher — 2026-01',
  situacao: 'rascunho',
};

const TRANSMISSAO = {
  ambiente: 'homologacao',
  protocolo: 'HML-2026.06.13-004271',
  recibo: null,
};

Object.assign(window, {
  BRL, fmtNum, ESCRITURACAO, JOB_LOG, ACHADOS, LOTE_REGISTROS,
  APURACAO, DIFF, PERDCOMP_TIPOS, PERDCOMP_FICHA, TRANSMISSAO,
});
