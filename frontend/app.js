let allJobs = [];
    let currentJob = null;
    let selectedDocId = null;
    let selectedPageNum = 1;
    let lgpdAnonymizedMode = false;
    let activeTab = 'explorer';
    let ocrSearchQuery = '';
    let userGeminiKey = localStorage.getItem('GEMINI_API_KEY') || '';

    const DOC_TYPE_LABELS = {
      AVISO_RECEBIMENTO_CORREIOS: { label: 'AR Correios (Notificação GRT / Compliance)', color: 'bg-amber-500/20 text-amber-300 border-amber-500/40', icon: 'mail-check' },
      DOCUMENTO_MANUSCRITO: { label: 'Termo Manuscrito (EPI / Apontamento Horas)', color: 'bg-purple-500/20 text-purple-300 border-purple-500/40', icon: 'pen-tool' },
      ASO_SAUDE_OCUPACIONAL: { label: 'ASO - Saúde Ocupacional (SST / NR-07)', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40', icon: 'heart-pulse' },
      FICHA_EPI_MANUSCRITA: { label: 'Ficha de Entrega de EPI (NR-06)', color: 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/40', icon: 'hard-hat' },
      CARTAO_PONTO_TRABALHISTA: { label: 'Cartão de Ponto / Cálculo Judicial', color: 'bg-orange-500/20 text-orange-300 border-orange-500/40', icon: 'clock' },
      CERTIDAO_NEGATIVA_CND: { label: 'Certidão Negativa (CNDT / FGTS / INSS)', color: 'bg-teal-500/20 text-teal-300 border-teal-500/40', icon: 'shield-check' },
      CNH: { label: 'CNH Colaborador Terceiro (Mobilização GRT)', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', icon: 'id-card' },
      RG: { label: 'RG - Identificação de Terceiro', color: 'bg-teal-500/20 text-teal-300 border-teal-500/40', icon: 'contact' },
      CONTRATO: { label: 'Contrato de Prestação de Serviços Terceirizados', color: 'bg-sky-500/20 text-sky-300 border-sky-500/40', icon: 'file-signature' },
      COMPROVANTE_RESIDENCIA: { label: 'Comprovante de Residência', color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40', icon: 'home' },
      NOTA_FISCAL: { label: 'Nota Fiscal / BPO Fiscal', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40', icon: 'receipt' },
      HOLERITE: { label: 'Folha Analítica (FOPAG / Holerite)', color: 'bg-lime-500/20 text-lime-300 border-lime-500/40', icon: 'banknote' },
      OUTROS: { label: 'Outros Documentos de Terceiros', color: 'bg-slate-700 text-slate-300 border-slate-600', icon: 'file' },
    };

    async function initApp() {
      updateApiKeyBadge();
      await fetchJobs();
      lucide.createIcons();
    }

    async function fetchJobs(preferJobId = null) {
      const res = await fetch('/api/jobs');
      allJobs = await res.json();
      renderJobHistorySelect();
      if (allJobs.length > 0) {
        const target = preferJobId ? allJobs.find(j => j.job_id === preferJobId) : allJobs[0];
        setCurrentJob(target || allJobs[0]);
      }
    }

    function setCurrentJob(job) {
      currentJob = job;
      const docs = job.documents || [];
      if (docs.length > 0) {
        const keep = docs.find(d => d.id === selectedDocId);
        const activeDoc = keep || docs[0];
        selectedDocId = activeDoc.id;
        selectedPageNum = activeDoc.pagina_inicial || 1;
      } else {
        selectedDocId = null;
        selectedPageNum = 1;
      }
      renderAll();
    }

    function renderJobHistorySelect() {
      const sel = document.getElementById('job-history-select');
      sel.innerHTML = allJobs.map(j => {
        const st = j.status === 'INTERRUPTED_FAILURE' ? '⚠️ FALHA PARCIAL' : (j.status === 'NEEDS_HUMAN_REVIEW' ? '🔎 REVISÃO HUMANA' : '✅ CONCLUÍDO');
        return `<option value="${j.job_id}" ${currentJob && currentJob.job_id === j.job_id ? 'selected' : ''}>
          ${j.job_id} • ${j.filename} (${st})
        </option>`;
      }).join('');
    }

    async function selectJobById(jobId) {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (res.ok) {
        const job = await res.json();
        setCurrentJob(job);
      }
    }

    async function triggerPreset(preset) {
      const badge = document.getElementById('active-job-badge');
      badge.textContent = 'Processando lote no motor multimodal...';
      const q = userGeminiKey ? `?api_key=${encodeURIComponent(userGeminiKey)}` : '';
      const res = await fetch(`/api/jobs/demo/${preset}${q}`, { method: 'POST' });
      const newJob = await res.json();
      await fetchJobs(newJob.job_id);
    }

    async function handleFileUpload(ev) {
      const file = ev.target.files[0];
      if (!file) return;
      const simFail = document.getElementById('chk-simulate-fail').checked;
      const formData = new FormData();
      formData.append('file', file);
      if (simFail) formData.append('simulate_failure_at_page', '3');
      if (userGeminiKey) formData.append('api_key', userGeminiKey);

      document.getElementById('active-job-badge').textContent = `Enviando e fatiando ${file.name}...`;
      const res = await fetch('/api/jobs/upload', { method: 'POST', body: formData });
      if (res.ok) {
        const newJob = await res.json();
        ev.target.value = '';
        await fetchJobs(newJob.job_id);
      }
    }

    async function resumeCurrentJob() {
      if (!currentJob) return;
      document.getElementById('active-job-badge').textContent = 'Retomando páginas pendentes a partir do checkpoint...';
      const q = userGeminiKey ? `?api_key=${encodeURIComponent(userGeminiKey)}` : '';
      const res = await fetch(`/api/jobs/${currentJob.job_id}/resume${q}`, { method: 'POST' });
      if (res.ok) {
        const updated = await res.json();
        await fetchJobs(updated.job_id);
      }
    }

    function toggleLgpdMode() {
      lgpdAnonymizedMode = !lgpdAnonymizedMode;
      const btn = document.getElementById('btn-lgpd-toggle');
      const dot = document.getElementById('lgpd-dot');
      const lbl = document.getElementById('lgpd-label');
      if (lgpdAnonymizedMode) {
        btn.className = 'flex items-center gap-2.5 px-3.5 py-2 rounded-xl border text-xs font-bold transition-all duration-200 bg-rose-500/20 border-rose-500 text-rose-200 shadow-lg shadow-rose-500/20';
        dot.className = 'w-2.5 h-2.5 rounded-full bg-rose-400 animate-ping';
        lbl.textContent = 'Anonimização LGPD: ATIVA (PII Tarjado)';
      } else {
        btn.className = 'flex items-center gap-2.5 px-3.5 py-2 rounded-xl border text-xs font-bold transition-all duration-200 bg-slate-900 border-slate-700 text-slate-300 hover:border-sky-500/50';
        dot.className = 'w-2.5 h-2.5 rounded-full bg-slate-500';
        lbl.textContent = 'Anonimização LGPD: DESATIVADA';
      }
      renderAll();
    }

    function switchTab(tab) {
      activeTab = tab;
      const expBtn = document.getElementById('tab-btn-explorer');
      const hitlBtn = document.getElementById('tab-btn-hitl');
      const expView = document.getElementById('view-explorer');
      const hitlView = document.getElementById('view-hitl');

      if (tab === 'explorer') {
        expBtn.className = 'px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition bg-sky-500 text-slate-950 shadow-md shadow-sky-500/20';
        hitlBtn.className = 'px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800';
        expView.classList.remove('hidden');
        hitlView.classList.add('hidden');
      } else {
        hitlBtn.className = 'px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition bg-rose-500 text-white shadow-md shadow-rose-500/20';
        expBtn.className = 'px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800';
        expView.classList.add('hidden');
        hitlView.classList.remove('hidden');
      }
      renderAll();
    }

    function handleOcrSearch(val) {
      ocrSearchQuery = val.trim();
      const clearBtn = document.getElementById('btn-clear-search');
      if (ocrSearchQuery) clearBtn.classList.remove('hidden');
      else clearBtn.classList.add('hidden');
      renderAll();
    }

    function clearOcrSearch() {
      document.getElementById('ocr-search-input').value = '';
      handleOcrSearch('');
    }

    function highlightOcrText(text, query) {
      const escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      if (!query) return escaped;
      const safeQ = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(${safeQ})`, 'gi');
      return escaped.replace(regex, '<mark class="ocr-highlight">$1</mark>');
    }

    function renderAll() {
      if (!currentJob) return;
      const docs = currentJob.documents || [];
      const pages = currentJob.pages || [];
      const pendingHitl = docs.filter(d => d.needs_review).length;
      const handwrittenCount = docs.filter(d => d.possui_manuscrito || d.tipo === 'AVISO_RECEBIMENTO_CORREIOS' || d.tipo === 'DOCUMENTO_MANUSCRITO').length;

      document.getElementById('active-job-badge').textContent = `Lote Ativo: ${currentJob.job_id} (${currentJob.status})`;
      document.getElementById('kpi-pages').textContent = `${currentJob.completed_pages} / ${currentJob.total_pages}`;
      document.getElementById('kpi-docs').textContent = docs.length;
      document.getElementById('kpi-handwritten').textContent = handwrittenCount;
      document.getElementById('kpi-review').textContent = `${pendingHitl} pendente(s)`;
      document.getElementById('badge-tab-docs').textContent = docs.length;
      document.getElementById('badge-tab-hitl').textContent = pendingHitl;

      renderCheckpointGrid(pages);
      renderDocumentsList(docs);
      renderDocumentInspector(docs);
      renderHitlQueue(docs);
      lucide.createIcons();
    }

    function renderCheckpointGrid(pages) {
      const banner = document.getElementById('failure-banner');
      if (currentJob.status === 'INTERRUPTED_FAILURE') {
        banner.classList.remove('hidden');
        document.getElementById('failure-reason-text').textContent = currentJob.failure_reason || 'Falha durante o processamento de página.';
      } else {
        banner.classList.add('hidden');
      }

      const container = document.getElementById('checkpoint-pages-grid');
      container.innerHTML = pages.map(p => {
        let style = 'bg-slate-950 border-slate-800 text-slate-400';
        let badge = '⏳ PENDENTE';
        if (p.status === 'COMPLETED') {
          style = 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300';
          badge = `✅ SALVO (${p.processed_at || 'OK'})`;
        } else if (p.status === 'FAILED') {
          style = 'bg-rose-500/20 border-rose-500 text-rose-200 animate-pulse';
          badge = '❌ FALHA AQUI';
        }
        return `
          <div class="p-2.5 rounded-xl border ${style} flex items-center justify-between text-xs">
            <span class="font-bold">Página ${p.page_number}</span>
            <span class="text-[10px] mono font-semibold">${badge}</span>
          </div>
        `;
      }).join('');
    }

    function getFilteredDocs(docs) {
      if (!ocrSearchQuery) return docs;
      const q = ocrSearchQuery.toLowerCase();
      return docs.filter(d => {
        const textToSearch = lgpdAnonymizedMode ? (d.texto_ocr_anonimizado || d.texto_ocr) : d.texto_ocr;
        return (
          textToSearch.toLowerCase().includes(q) ||
          d.tipo.toLowerCase().includes(q) ||
          (d.titulo_resumo || '').toLowerCase().includes(q)
        );
      });
    }

    function renderDocumentsList(docs) {
      const container = document.getElementById('documents-list-container');
      if (currentJob.status === 'INTERRUPTED_FAILURE' && docs.length === 0) {
        container.innerHTML = `
          <div class="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-center space-y-3">
            <p class="text-xs text-amber-200 font-semibold">
              O lote foi interrompido na Página ${currentJob.failed_page} antes da consolidação final.
            </p>
            <button onclick="resumeCurrentJob()" class="px-4 py-2 rounded-xl bg-amber-400 text-slate-950 font-bold text-xs">
              ⚡ Retomar da Página ${currentJob.failed_page} Agora
            </button>
          </div>
        `;
        return;
      }

      const filtered = getFilteredDocs(docs);
      if (filtered.length === 0) {
        container.innerHTML = `<div class="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-400 text-center">Nenhum documento encontrado para "${ocrSearchQuery}".</div>`;
        return;
      }

      container.innerHTML = filtered.map(doc => {
        const isSelected = doc.id === selectedDocId;
        const meta = DOC_TYPE_LABELS[doc.tipo] || DOC_TYPE_LABELS.OUTROS;
        const pct = Math.round(doc.confianca * 100);
        const confBadge = doc.needs_review
          ? `<span class="px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/40 text-[10px] font-bold">⚠️ ${pct}% • Revisar</span>`
          : `<span class="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold">✓ ${pct}% Confiança</span>`;

        const pageRangeLabel = doc.paginas.length > 1
          ? `Páginas ${doc.pagina_inicial} a ${doc.pagina_final} (${doc.paginas.length} págs agrupadas)`
          : `Página ${doc.pagina_inicial} (1 página)`;

        return `
          <div
            onclick="selectDocument('${doc.id}')"
            class="cursor-pointer p-3.5 rounded-2xl border transition-all ${
              isSelected
                ? 'bg-sky-500/15 border-sky-400 shadow-lg shadow-sky-500/10'
                : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
            }"
          >
            <div class="flex items-center justify-between gap-2 mb-1.5">
              <span class="px-2.5 py-0.5 rounded-lg border text-[11px] font-bold ${meta.color}">
                ${meta.label}
              </span>
              ${confBadge}
            </div>

            <h4 class="text-xs font-bold text-white mb-1">${doc.titulo_resumo}</h4>
            <p class="text-[11px] text-emerald-400/90 font-medium mb-1">🏢 ${doc.vertical_bernhoeft || 'Gestão de Riscos com Terceiros (GRT)'}</p>

            <div class="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/80">
              <span class="font-semibold text-sky-300">📑 ${pageRangeLabel}</span>
              ${doc.possui_manuscrito ? '<span class="text-amber-300 font-semibold">✍️ Escrita à Mão</span>' : ''}
            </div>
          </div>
        `;
      }).join('');
    }

    function selectDocument(docId) {
      selectedDocId = docId;
      const doc = (currentJob.documents || []).find(d => d.id === docId);
      if (doc) selectedPageNum = doc.pagina_inicial;
      renderAll();
    }

    function selectPageInDoc(pnum) {
      selectedPageNum = pnum;
      renderAll();
    }

    function renderDocumentInspector(docs) {
      const container = document.getElementById('document-inspector-content');
      const doc = docs.find(d => d.id === selectedDocId) || docs[0];
      if (!doc) {
        container.innerHTML = `<div class="p-8 text-center text-slate-400 text-xs">Selecione ou processe um lote documental para visualizar.</div>`;
        return;
      }

      const meta = DOC_TYPE_LABELS[doc.tipo] || DOC_TYPE_LABELS.OUTROS;
      const pct = Math.round(doc.confianca * 100);
      const imgUrl = `/api/pages/${currentJob.job_id}/${selectedPageNum}?anonymized=${lgpdAnonymizedMode}&t=${Date.now()}`;
      const displayOcr = lgpdAnonymizedMode ? (doc.texto_ocr_anonimizado || doc.texto_ocr) : doc.texto_ocr;

      // Bloco Especial se for AR dos Correios
      let arBlockHtml = '';
      if (doc.tipo === 'AVISO_RECEBIMENTO_CORREIOS' && doc.campos_ar) {
        const ar = doc.campos_ar;
        const maskIfLgpd = (val) => lgpdAnonymizedMode ? '[PROTEGIDO PELA LGPD]' : (val || '—');
        arBlockHtml = `
          <div class="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-extrabold uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
                📬 Extração Especializada: Aviso de Recebimento (AR Correios)
              </span>
              <span class="mono text-xs font-bold px-2 py-0.5 rounded bg-amber-400 text-slate-950">
                ${ar.codigo_rastreio || 'BR984512390BR'}
              </span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div class="bg-slate-950/70 p-2 rounded-lg">
                <span class="text-[10px] text-slate-400 block">Destinatário:</span>
                <span class="font-semibold text-white">${maskIfLgpd(ar.destinatario)}</span>
              </div>
              <div class="bg-slate-950/70 p-2 rounded-lg">
                <span class="text-[10px] text-slate-400 block">Data de Entrega (Escrita à Mão):</span>
                <span class="font-semibold text-amber-300">${ar.data_entrega_manuscrita || '05/11/2026'}</span>
              </div>
              <div class="bg-slate-950/70 p-2 rounded-lg">
                <span class="text-[10px] text-slate-400 block">Recebedor Manuscrito (À Caneta):</span>
                <span class="font-semibold text-sky-300">${maskIfLgpd(ar.nome_recebedor_manuscrito)}</span>
              </div>
              <div class="bg-slate-950/70 p-2 rounded-lg">
                <span class="text-[10px] text-slate-400 block">Doc. Identidade Manuscrito:</span>
                <span class="font-semibold text-white">${maskIfLgpd(ar.documento_recebedor_manuscrito)}</span>
              </div>
            </div>
          </div>
        `;
      }

      container.innerHTML = `
        <div class="space-y-4">
          <!-- Cabeçalho do Documento Selecionado -->
          <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div>
              <div class="flex items-center gap-2 mb-1">
                <span class="px-2.5 py-0.5 rounded-lg border text-xs font-bold ${meta.color}">${meta.label}</span>
                <span class="text-xs mono text-slate-400">Início: Pág ${doc.pagina_inicial} ➔ Fim: Pág ${doc.pagina_final}</span>
              </div>
              <h3 class="text-base font-extrabold text-white">${doc.titulo_resumo}</h3>
            </div>

            <div class="flex items-center gap-2">
              ${
                doc.needs_review
                  ? `<button onclick="switchTab('hitl')" class="px-3 py-1.5 rounded-xl bg-rose-500 hover:bg-rose-400 text-white font-bold text-xs flex items-center gap-1.5">
                      <span>Ir para Fila Humana (${pct}%)</span>
                    </button>`
                  : `<span class="px-3 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-bold text-xs">
                      ✓ Validado (${pct}% Confiança)
                    </span>`
              }
            </div>
          </div>

          <!-- Visor Lado a Lado: Imagem Original/Anonimizada vs OCR Pesquisável -->
          <div class="grid grid-cols-1 md:grid-cols-12 gap-4">
            <!-- Esquerda: Imagem da Página com seletor de páginas agrupadas -->
            <div class="md:col-span-6 flex flex-col space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-slate-300">
                  Visualização da Página (${lgpdAnonymizedMode ? '🔒 Com Tarjas LGPD' : '📄 Original'})
                </span>
                <div class="flex items-center gap-1">
                  ${doc.paginas.map(pnum => `
                    <button
                      onclick="selectPageInDoc(${pnum})"
                      class="px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                        selectedPageNum === pnum
                          ? 'bg-sky-500 text-slate-950'
                          : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                      }"
                    >
                      Pág ${pnum}
                    </button>
                  `).join('')}
                </div>
              </div>

              <div class="rounded-xl overflow-hidden border border-slate-700 bg-slate-950 flex items-center justify-center min-h-[420px]">
                <img
                  src="${imgUrl}"
                  alt="Página ${selectedPageNum}"
                  class="max-h-[520px] w-auto object-contain"
                />
              </div>
            </div>

            <!-- Direita: Campos AR + OCR Pesquisável + Auditoria LGPD -->
            <div class="md:col-span-6 flex flex-col space-y-3">
              ${arBlockHtml}

              <div class="flex-1 flex flex-col bg-slate-950 border border-slate-800 rounded-xl p-3.5">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-bold uppercase tracking-wider text-sky-400">
                    📝 OCR Pesquisável (Impresso + Manuscrito)
                  </span>
                  <span class="text-[11px] text-slate-400">
                    ${lgpdAnonymizedMode ? '🛡️ PII Mascarado' : 'Texto Integral'}
                  </span>
                </div>
                <pre class="mono text-xs text-slate-200 whitespace-pre-wrap leading-relaxed overflow-y-auto max-h-[280px] p-2 rounded bg-slate-900/70">${highlightOcrText(displayOcr, ocrSearchQuery)}</pre>
              </div>

              <!-- Lista de Dados Sensíveis Protegidos pela LGPD -->
              <div class="bg-slate-950 border border-slate-800 rounded-xl p-3">
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-xs font-bold text-purple-300">
                    🛡️ Mapeamento de Dados Sensíveis (LGPD • ${doc.dados_sensiveis_lgpd ? doc.dados_sensiveis_lgpd.length : 0} itens detectados)
                  </span>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  ${
                    (doc.dados_sensiveis_lgpd || []).length > 0
                      ? doc.dados_sensiveis_lgpd.map(item => `
                          <span class="px-2 py-1 rounded-md bg-purple-500/15 border border-purple-500/30 text-[11px] text-purple-200 mono">
                            <strong>${item.tipo}:</strong> ${item.valor_mascarado}
                          </span>
                        `).join('')
                      : '<span class="text-xs text-slate-500">Nenhum dado sensível crítico adicional.</span>'
                  }
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    function renderHitlQueue(docs) {
      const container = document.getElementById('hitl-queue-container');
      if (!docs || docs.length === 0) {
        container.innerHTML = `<div class="p-6 rounded-xl bg-slate-900 border border-slate-800 text-center text-xs text-slate-400">Nenhum documento no lote atual.</div>`;
        return;
      }

      container.innerHTML = docs.map(doc => {
        const pct = Math.round(doc.confianca * 100);
        const isPending = doc.needs_review;
        const borderClass = isPending ? 'border-rose-500/60 bg-rose-500/5' : 'border-slate-800 bg-slate-900/80';

        return `
          <div class="rounded-2xl border ${borderClass} p-4 sm:p-5 grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div class="lg:col-span-4 flex flex-col justify-between space-y-3">
              <div>
                <div class="flex items-center justify-between gap-2 mb-2">
                  <span class="px-2.5 py-1 rounded-lg text-xs font-bold ${
                    isPending ? 'bg-rose-500 text-white' : 'bg-emerald-500/20 text-emerald-300'
                  }">
                    ${isPending ? `⚠️ REVISÃO HUMANA PENDENTE (${pct}%)` : `✅ VALIDADO (${pct}%)`}
                  </span>
                  <span class="text-xs mono text-slate-400">Pág(s): ${doc.paginas.join(', ')}</span>
                </div>
                <h4 class="text-sm font-bold text-white">${doc.titulo_resumo}</h4>
                ${
                  doc.review_reason
                    ? `<p class="mt-2 p-2.5 rounded-lg bg-rose-500/15 border border-rose-500/30 text-xs text-rose-200">
                        <strong>Motivo da Retenção:</strong> ${doc.review_reason}
                      </p>`
                    : ''
                }
              </div>

              <div class="rounded-xl overflow-hidden border border-slate-700 bg-slate-950 flex justify-center">
                <img
                  src="/api/pages/${currentJob.job_id}/${doc.pagina_inicial}?anonymized=${lgpdAnonymizedMode}"
                  class="max-h-56 object-contain"
                  alt="Preview Revisão"
                />
              </div>
            </div>

            <div class="lg:col-span-8 flex flex-col justify-between space-y-3">
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label class="text-xs font-bold text-slate-300 block mb-1">Classificação Documental:</label>
                  <select
                    id="rev-type-${doc.id}"
                    class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                  >
                    ${Object.keys(DOC_TYPE_LABELS).map(k => `
                      <option value="${k}" ${doc.tipo === k ? 'selected' : ''}>${DOC_TYPE_LABELS[k].label}</option>
                    `).join('')}
                  </select>
                </div>
                <div>
                  <label class="text-xs font-bold text-slate-300 block mb-1">Operador Responsável:</label>
                  <input
                    id="rev-user-${doc.id}"
                    type="text"
                    value="${doc.revisado_por || 'Operador HITL (Davi / Lucas)'}"
                    class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                  />
                </div>
              </div>

              <div>
                <label class="text-xs font-bold text-slate-300 block mb-1">
                  Transcrição OCR / Manuscrito (Editável pelo Revisor Humano):
                </label>
                <textarea
                  id="rev-ocr-${doc.id}"
                  rows="5"
                  class="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-xs text-slate-100 mono focus:outline-none focus:border-sky-500"
                >${doc.texto_ocr}</textarea>
              </div>

              <div class="flex flex-wrap items-center justify-between gap-3 pt-2">
                <span class="text-xs text-slate-400">
                  Status: <strong class="text-white">${doc.review_status}</strong>
                </span>
                <button
                  onclick="submitHumanReview('${doc.id}')"
                  class="px-5 py-2.5 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-extrabold text-xs flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition"
                >
                  <span>✅ Aprovar e Validar Documento (HITL)</span>
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    async function submitHumanReview(docId) {
      const tipo = document.getElementById(`rev-type-${docId}`).value;
      const texto_ocr = document.getElementById(`rev-ocr-${docId}`).value;
      const revisado_por = document.getElementById(`rev-user-${docId}`).value;

      const res = await fetch(`/api/documents/${docId}/review`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tipo,
          texto_ocr,
          revisado_por,
          notas_revisao: 'Aprovado e revisado na Fila HITL',
        }),
      });
      if (res.ok) {
        const updatedJob = await res.json();
        await fetchJobs(updatedJob.job_id);
      }
    }

    function openApiKeyModal() {
      document.getElementById('input-gemini-key').value = userGeminiKey;
      document.getElementById('modal-apikey').classList.remove('hidden');
    }
    function closeApiKeyModal() {
      document.getElementById('modal-apikey').classList.add('hidden');
    }
    function saveApiKey() {
      userGeminiKey = document.getElementById('input-gemini-key').value.trim();
      localStorage.setItem('GEMINI_API_KEY', userGeminiKey);
      updateApiKeyBadge();
      closeApiKeyModal();
    }
    function updateApiKeyBadge() {
      const el = document.getElementById('api-key-badge');
      el.textContent = userGeminiKey ? 'Gemini 3.8 Flash (Key Ativa)' : 'Gemini 3.8 Multimodal';
    }
    function openTeamModal() {
      document.getElementById('modal-team').classList.remove('hidden');
    }
    function closeTeamModal() {
      document.getElementById('modal-team').classList.add('hidden');
    }

    window.addEventListener('DOMContentLoaded', initApp);