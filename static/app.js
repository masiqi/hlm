const views = document.querySelectorAll(".view");
let currentChapterPayload = null;

function showView(id) {
  views.forEach((view) => view.classList.toggle("active", view.id === id));
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`请求失败：${response.status}`);
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderAnnotatedOriginalText(text, annotations) {
  if (!annotations.length) return escapeHtml(text);
  const sortedAnnotations = [...annotations]
    .filter((item) => (item.inlineEntityId || item.entityId) && item.startOffset >= 0 && item.endOffset > item.startOffset)
    .sort((left, right) => left.startOffset - right.startOffset || right.endOffset - left.endOffset);
  let cursor = 0;
  let html = "";
  sortedAnnotations.forEach((annotation) => {
    if (annotation.startOffset < cursor) return;
    html += escapeHtml(text.slice(cursor, annotation.startOffset));
    const label = text.slice(annotation.startOffset, annotation.endOffset);
    const entityId = annotation.inlineEntityId || annotation.entityId;
    html += `<button class="annotation-link" data-annotation-id="${escapeHtml(annotation.id)}" data-inline-entity-id="${escapeHtml(entityId)}">${escapeHtml(label)}</button>`;
    cursor = annotation.endOffset;
  });
  html += escapeHtml(text.slice(cursor));
  return html;
}

function renderList(items = [], renderItem = (item) => escapeHtml(item)) {
  if (!items.length) return "<li>暂无可靠资料</li>";
  return items.map((item) => `<li>${renderItem(item)}</li>`).join("");
}

function renderRichSection(title, items = [], renderItem) {
  return `<section><h4>${escapeHtml(title)}</h4><ul>${renderList(items, renderItem)}</ul></section>`;
}

function entityTypeLabel(type) {
  if (type === "person") return "人物";
  if (type === "place") return "地点";
  if (type === "object") return "物件";
  if (type === "literary_text") return "语言";
  if (type === "foreshadowing") return "线索";
  return "相关信息";
}

function findInlineEntity(entityId) {
  return (currentChapterPayload?.inlineEntities || []).find((entity) => entity.id === entityId);
}

function renderChapterJumps(jumps = []) {
  return renderList(jumps, (jump) => {
    const label = jump.label || `第${jump.chapter}回`;
    return `<button data-chapter-number="${escapeHtml(jump.chapter)}">${escapeHtml(label)}</button>`;
  });
}

function renderEntityPopover(entity) {
  if (!entity) return "";
  const details = renderList(entity.details || []);
  const relations = renderList(entity.relations || [], (relation) => {
    const endpoints = [relation.source, relation.type, relation.target].filter(Boolean).join(" — ");
    const description = relation.description || relation.evidence || "";
    return `<strong>${escapeHtml(endpoints || "关系")}</strong>${description ? `：${escapeHtml(description)}` : ""}`;
  });
  const laterClues = renderList(entity.laterClues || [], (clue) => {
    const title = clue.topic || "后文关联";
    const description = clue.description || clue.evidence || "";
    return `<strong>${escapeHtml(title)}</strong>${description ? `：${escapeHtml(description)}` : ""}`;
  });
  return `
    <div class="entity-popover-card">
      <button class="panel-close entity-popover-close" data-entity-popover-close>关闭</button>
      <p class="entity-type">${escapeHtml(entityTypeLabel(entity.type))}</p>
      <h3>${escapeHtml(entity.name)}</h3>
      <p>${escapeHtml(entity.summary || "暂无可靠资料")}</p>
      <h4>本回信息</h4>
      <ul>${details}</ul>
      <h4>关系线索</h4>
      <ul>${relations}</ul>
      <h4>后文关联</h4>
      <ul>${laterClues}</ul>
      <h4>相关章回</h4>
      <ul>${renderChapterJumps(entity.chapterJumps || [])}</ul>
    </div>
  `;
}

function openEntityPopover(entityId) {
  const entity = findInlineEntity(entityId);
  if (!entity) return;
  let popover = document.querySelector("#entity-popover");
  if (!popover) {
    popover = document.createElement("aside");
    popover.id = "entity-popover";
    popover.className = "entity-popover";
    document.body.append(popover);
  }
  popover.innerHTML = renderEntityPopover(entity);
  popover.classList.add("open");
}

function closeEntityPopover() {
  document.querySelector("#entity-popover")?.classList.remove("open");
}

function renderContinuationLinks(links = []) {
  if (!links.length) return "<li>暂无可靠资料</li>";
  return links
    .map((link) => {
      const label = escapeHtml(link.label);
      const targetId = escapeHtml(link.targetId);
      if (link.targetType === "chapter") return `<li><button data-chapter-number="${targetId}">${label}</button></li>`;
      if (link.targetType === "card") return `<li><button data-card-id="${targetId}">${label}</button></li>`;
      if (link.targetType === "topic") return `<li><button data-topic-id="${targetId}">${label}</button></li>`;
      return `<li>${label}</li>`;
    })
    .join("");
}

function sourceLabel(sourceType) {
  if (sourceType === "original_text") return "原文依据";
  if (sourceType === "processed_material" || sourceType === "knowledge_card") return "章节资料";
  if (sourceType === "graph_relation") return "关系线索";
  return "相关资料";
}

function renderAnswer(answer) {
  const container = document.querySelector("#answer");
  if (answer.status === "refused") {
    const conflictNote = answer.refusal.message.includes("不一致") ? "<p>资料存在不一致，优先查看原文依据。</p>" : "";
    container.innerHTML = `
      <h3>当前资料不足</h3>
      ${conflictNote}
      <p>${escapeHtml(answer.refusal.message)}</p>
      <h3>继续查看</h3>
      <ul>${renderContinuationLinks(answer.continuationLinks || [])}</ul>
    `;
    showView("ask");
    return;
  }
  const claims = answer.shortConclusion.map((claim) => `<li>${escapeHtml(claim.text)}</li>`).join("");
  const sources = answer.evidence
    .map(
      (evidence) =>
        `<li class="source"><strong>${sourceLabel(evidence.sourceType)}</strong> 第 ${escapeHtml(evidence.chapter)} 回：${escapeHtml(evidence.evidenceText)}</li>`,
    )
    .join("");
  const facts = (answer.quotableFacts?.claims || []).map((claim) => `<li>${escapeHtml(claim.text)}</li>`).join("");
  const partialNote =
    answer.status === "partial" && answer.refusal ? `<h3>资料不足部分</h3><p>${escapeHtml(answer.refusal.message)}</p>` : "";
  container.innerHTML = `
    <h3>${answer.status === "partial" ? "已支持部分" : "短结论"}</h3>
    <ul>${claims}</ul>
    ${partialNote}
    <h3>依据</h3>
    <ul>${sources}</ul>
    <h3>可引用事实</h3>
    <ul>${facts}</ul>
    <h3>继续查看</h3>
    <ul>${renderContinuationLinks(answer.continuationLinks || [])}</ul>
  `;
  showView("ask");
}

async function ask(question) {
  const answer = await getJson("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  renderAnswer(answer);
}

async function loadHome() {
  const data = await getJson("/api/home");
  document.querySelector("#common-entries").innerHTML = data.commonEntries
    .map(
      (entry) =>
        `<button data-target-type="${escapeHtml(entry.targetType)}" data-target="${escapeHtml(entry.target)}">${escapeHtml(entry.label)}</button>`,
    )
    .join("");
}

function handleCommonEntry(target) {
  if (target.dataset.targetType === "ask") {
    ask(target.dataset.target);
  }
  if (target.dataset.targetType === "chapter") {
    showView("chapters");
    loadChapter(Number(target.dataset.target));
  }
  if (target.dataset.targetType === "topic") {
    showView("topics");
    loadTopicDetail(target.dataset.target);
  }
  if (target.dataset.targetType === "card") {
    showView("chapters");
    loadKnowledgeCard(target.dataset.target);
  }
}

function renderKnowledgeButtons(cards) {
  return cards
    .map((card) => `<button data-card-id="${escapeHtml(card.id)}">${escapeHtml(card.name)}</button>`)
    .join("");
}

function renderInlineEntityButtons(entities = []) {
  if (!entities.length) return "<p>暂无可靠资料</p>";
  return entities
    .map(
      (entity) =>
        `<button class="entity-chip" data-inline-entity-id="${escapeHtml(entity.id)}"><strong>${escapeHtml(entity.name)}</strong><span>${escapeHtml(entityTypeLabel(entity.type))}</span></button>`,
    )
    .join("");
}

function renderTraceItems(traceItems = []) {
  if (!traceItems.length) return "<li>暂无可靠资料</li>";
  return traceItems
    .map(
      (item) =>
        `<li><button class="trace-link" data-trace-chapter-number="${escapeHtml(item.chapter)}" data-trace-id="${escapeHtml(item.id)}">${escapeHtml(item.title)}</button><p>${escapeHtml(item.description)}</p></li>`,
    )
    .join("");
}

function panelContentSelector(targetSelector) {
  return `${targetSelector} .knowledge-panel-content`;
}

function openKnowledgePanel(targetSelector) {
  document.querySelector(targetSelector).className = "knowledge-panel open";
}

function closeKnowledgePanel(panelId) {
  document.querySelector(`#${panelId}`).className = "knowledge-panel";
}

function initChapterSelector() {
  const chapterSelect = document.querySelector("#chapter-select");
  if (!chapterSelect || chapterSelect.options.length) return;
  for (let number = 1; number <= 120; number += 1) {
    const option = document.createElement("option");
    option.value = String(number);
    option.textContent = `第 ${number} 回`;
    chapterSelect.append(option);
  }
}

async function loadKnowledgeCard(cardId, targetSelector = "#knowledge-panel") {
  const data = await getJson(`/api/cards/${cardId}`);
  const textUnderstanding = data.card.textUnderstanding.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const understandingAngles = data.card.understandingAngles.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const relationClues = data.relations.map((item) => `<li>${escapeHtml(item.description)}</li>`).join("");
  const traceItems = renderTraceItems(data.traceItems || []);
  const sources = data.evidence
    .map((item) => `<li class="source">第 ${escapeHtml(item.chapter)} 回：${escapeHtml(item.evidenceText)}</li>`)
    .join("");
  document.querySelector(panelContentSelector(targetSelector)).innerHTML = `
    <h3>${escapeHtml(data.card.name)}</h3>
    <h4>文本理解</h4>
    <ul>${textUnderstanding || "<li>暂无可靠资料</li>"}</ul>
    <h4>理解角度</h4>
    <ul>${understandingAngles || "<li>暂无可靠资料</li>"}</ul>
    <h4>关系线索</h4>
    <ul>${relationClues || "<li>暂无可靠资料</li>"}</ul>
    <h4>全书线索</h4>
    <ul class="trace-list">${traceItems}</ul>
    <h4>相关章回</h4>
    <ul>${sources || "<li>暂无可靠资料</li>"}</ul>
  `;
  openKnowledgePanel(targetSelector);
}

async function loadChapter(number = 27) {
  const data = await getJson(`/api/chapters/${number}`);
  currentChapterPayload = data;
  closeEntityPopover();
  const chapterSelect = document.querySelector("#chapter-select");
  if (chapterSelect) chapterSelect.value = String(data.chapter.number);
  const focusCards = data.knowledgeCards
    .map((card) => `<li><strong>${escapeHtml(card.name)}</strong>：${escapeHtml(card.brief)}</li>`)
    .join("");
  const hasReviewCard = Boolean(data.materialStatus?.hasReviewCard && data.reviewCard);
  const materialMessage = escapeHtml(data.materialStatus?.message || "章节资料暂未生成，可先阅读原文。");
  const plainSummary = hasReviewCard ? escapeHtml(data.reviewCard.plainSummary) : "暂无可靠资料";
  const plotChain = hasReviewCard
    ? data.reviewCard.plotChain.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>暂无可靠资料</li>";
  const keyEvents = hasReviewCard
    ? data.reviewCard.keyEvents.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>暂无可靠资料</li>";
  const focusAngles = hasReviewCard
    ? data.reviewCard.understandingFocus.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>暂无可靠资料</li>";
  const reviewCard = data.reviewCard || {};
  document.querySelector("#chapter-content").innerHTML = `
    <h3>第 ${escapeHtml(data.chapter.number)} 回：${escapeHtml(data.chapter.title)}</h3>
    <p>${materialMessage}</p>
    <section><h4>本回梗概</h4><p>${plainSummary}</p></section>
    <div class="chapter-section-grid">
      <section><h4>关键情节</h4><ul>${plotChain}</ul></section>
      <section><h4>关键事件</h4><ul>${keyEvents}</ul></section>
      <section><h4>本回怎么读</h4><ul>${focusAngles}</ul></section>
      <section><h4>本回信息卡</h4><div class="entity-chip-list">${renderInlineEntityButtons(data.inlineEntities || [])}</div></section>
      ${renderRichSection("主要人物", reviewCard.characters || [], (item) => `<button class="text-link" data-inline-entity-id="${escapeHtml((data.inlineEntities || []).find((entity) => entity.name === item.name)?.id || "")}">${escapeHtml(item.name)}</button>：${escapeHtml(item.importance || item.role || "")}<br>${escapeHtml((item.actions || []).join("；"))}`)}
      ${renderRichSection("人物与事件关系", reviewCard.relationships || [], (item) => `${escapeHtml([item.source, item.type, item.target].filter(Boolean).join(" — "))}：${escapeHtml(item.description || item.chapterEvidence || "")}`)}
      ${renderRichSection("地点与物件", [...(reviewCard.places || []), ...(reviewCard.objects || [])], (item) => `<strong>${escapeHtml(item.name)}</strong>：${escapeHtml(item.function || item.meaning || item.context || "")}`)}
      ${renderRichSection("诗词语言", [...(reviewCard.literaryTexts || []), ...(reviewCard.modernExplanations || [])], (item) => `<strong>${escapeHtml(item.title || item.quote || "语言细节")}</strong>：${escapeHtml(item.explanation || item.modernText || item.function || item.value || "")}`)}
      ${renderRichSection("后文关联", reviewCard.laterAssociations || [], (item) => `<strong>${escapeHtml(item.topic || "线索")}</strong>：${escapeHtml(item.description || item.evidence || "")}`)}
    </div>
    <section><h4>已有知识卡</h4><div>${renderKnowledgeButtons(data.knowledgeCards)}</div></section>
    <section><h4>原文</h4><pre class="annotated-original">${renderAnnotatedOriginalText(data.originalText, data.annotations || [])}</pre></section>
  `;
  document.querySelector(panelContentSelector("#knowledge-panel")).innerHTML = `
    <h3>本回重点</h3>
    <h4>主要人物</h4>
    <ul>${focusCards || "<li>暂无可靠资料</li>"}</ul>
    <h4>理解角度</h4>
    <ul>${focusAngles || "<li>暂无可靠资料</li>"}</ul>
  `;
  closeKnowledgePanel("knowledge-panel");
}

async function loadTopics() {
  const data = await getJson("/api/topics");
  document.querySelector("#topic-list").innerHTML = data.topics
    .map(
      (topic) =>
        `<article><h3>${escapeHtml(topic.title)}</h3><p>${escapeHtml(topic.description)}</p><button data-topic-id="${escapeHtml(topic.id)}">查看专题</button></article>`,
    )
    .join("");
}

async function loadTopicDetail(topicId) {
  const data = await getJson(`/api/topics/${topicId}`);
  const cards = data.cards.map((card) => `<li><button data-card-id="${escapeHtml(card.id)}">${escapeHtml(card.name)}</button></li>`).join("");
  const relations = data.relations.map((relation) => `<li>${escapeHtml(relation.description)}</li>`).join("");
  const facts = data.evidence
    .map((item) => `<li class="source">第 ${escapeHtml(item.chapter)} 回：${escapeHtml(item.evidenceText)}</li>`)
    .join("");
  const patterns = data.topic.typicalQuestionPatterns.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  document.querySelector("#topic-list").innerHTML = `
    <article>
      <h3>${escapeHtml(data.topic.title)}</h3>
      <p>${escapeHtml(data.topic.description)}</p>
      <h4>核心知识卡</h4>
      <ul>${cards || "<li>暂无可靠资料</li>"}</ul>
      <h4>关系线索</h4>
      <ul>${relations || "<li>暂无可靠资料</li>"}</ul>
      <h4>典型问法</h4>
      <ul>${patterns || "<li>暂无可靠资料</li>"}</ul>
      <h4>可引用事实</h4>
      <ul>${facts || "<li>暂无可靠资料</li>"}</ul>
    </article>
  `;
  document.querySelector(panelContentSelector("#topic-knowledge-panel")).innerHTML = "";
  closeKnowledgePanel("topic-knowledge-panel");
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (target.matches("[data-view]")) {
    showView(target.dataset.view);
    if (target.dataset.view === "chapters") loadChapter();
    if (target.dataset.view === "topics") loadTopics();
  }
  if (target.matches("[data-target-type]")) {
    handleCommonEntry(target);
  }
  if (target.matches("[data-card-id]")) {
    const panel = target.closest("#topics") ? "#topic-knowledge-panel" : "#knowledge-panel";
    loadKnowledgeCard(target.dataset.cardId, panel);
  }
  if (target.matches("[data-inline-entity-id]")) {
    openEntityPopover(target.dataset.inlineEntityId);
  }
  if (target.matches("[data-entity-popover-close]")) {
    closeEntityPopover();
  }
  if (target.matches("[data-topic-id]")) {
    showView("topics");
    loadTopicDetail(target.dataset.topicId);
  }
  if (target.matches("[data-chapter-number]")) {
    showView("chapters");
    loadChapter(Number(target.dataset.chapterNumber));
  }
  if (target.matches("[data-trace-chapter-number]")) {
    showView("chapters");
    loadChapter(Number(target.dataset.traceChapterNumber));
  }
  if (target.matches("[data-panel-close]")) {
    closeKnowledgePanel(target.dataset.panelClose);
  }
});

document.querySelector("#chapter-select").addEventListener("change", (event) => {
  loadChapter(Number(event.currentTarget.value));
});

document.querySelector("#ask-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = new FormData(event.currentTarget).get("question");
  ask(String(question || ""));
});

initChapterSelector();
loadHome();
