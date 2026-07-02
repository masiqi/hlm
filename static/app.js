const views = document.querySelectorAll(".view");

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

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function renderAnnotatedOriginalText(text, cards) {
  let annotated = escapeHtml(text);
  const sortedCards = [...cards].sort((left, right) => right.name.length - left.name.length);
  sortedCards.forEach((card) => {
    const escapedName = escapeHtml(card.name);
    if (!escapedName) return;
    const pattern = new RegExp(escapeRegExp(escapedName), "g");
    annotated = annotated.replaceAll(
      pattern,
      `<button class="inline-knowledge-link" data-card-id="${escapeHtml(card.id)}">${escapedName}</button>`,
    );
  });
  return annotated;
}

function renderAnswer(answer) {
  const container = document.querySelector("#answer");
  if (answer.status === "refused") {
    container.innerHTML = `<h3>当前资料不足</h3><p>${escapeHtml(answer.refusal.message)}</p>`;
    showView("ask");
    return;
  }
  const claims = answer.shortConclusion.map((claim) => `<li>${escapeHtml(claim.text)}</li>`).join("");
  const sources = answer.evidence
    .map((evidence) => `<li class="source">第 ${escapeHtml(evidence.chapter)} 回：${escapeHtml(evidence.evidenceText)}</li>`)
    .join("");
  const facts = (answer.quotableFacts?.claims || []).map((claim) => `<li>${escapeHtml(claim.text)}</li>`).join("");
  const partialNote =
    answer.status === "partial" && answer.refusal ? `<h3>未回答部分</h3><p>${escapeHtml(answer.refusal.message)}</p>` : "";
  container.innerHTML = `
    <h3>${answer.status === "partial" ? "部分回答" : "短结论"}</h3>
    <ul>${claims}</ul>
    ${partialNote}
    <h3>依据</h3>
    <ul>${sources}</ul>
    <h3>可引用事实</h3>
    <ul>${facts}</ul>
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
    .map((entry) => `<button data-question="${escapeHtml(entry.target)}">${escapeHtml(entry.label)}</button>`)
    .join("");
}

function renderKnowledgeButtons(cards) {
  return cards
    .map((card) => `<button data-card-id="${escapeHtml(card.id)}">${escapeHtml(card.name)}</button>`)
    .join("");
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
  const sources = data.evidence
    .map((item) => `<li class="source">第 ${escapeHtml(item.chapter)} 回：${escapeHtml(item.evidenceText)}</li>`)
    .join("");
  document.querySelector(targetSelector).innerHTML = `
    <h3>${escapeHtml(data.card.name)}</h3>
    <h4>文本理解</h4>
    <ul>${textUnderstanding || "<li>暂无可靠资料</li>"}</ul>
    <h4>理解角度</h4>
    <ul>${understandingAngles || "<li>暂无可靠资料</li>"}</ul>
    <h4>关系线索</h4>
    <ul>${relationClues || "<li>暂无可靠资料</li>"}</ul>
    <h4>相关章回</h4>
    <ul>${sources || "<li>暂无可靠资料</li>"}</ul>
  `;
}

async function loadChapter(number = 27) {
  const data = await getJson(`/api/chapters/${number}`);
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
  const focusAngles = hasReviewCard
    ? data.reviewCard.understandingFocus.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>暂无可靠资料</li>";
  document.querySelector("#chapter-content").innerHTML = `
    <h3>第 ${escapeHtml(data.chapter.number)} 回：${escapeHtml(data.chapter.title)}</h3>
    <p>${materialMessage}</p>
    <section><h4>本回梗概</h4><p>${plainSummary}</p></section>
    <section><h4>关键情节</h4><ul>${plotChain}</ul></section>
    <section><h4>本回主要人物</h4><div>${renderKnowledgeButtons(data.knowledgeCards)}</div></section>
    <section><h4>原文</h4><pre class="annotated-original">${renderAnnotatedOriginalText(data.originalText, data.knowledgeCards)}</pre></section>
  `;
  document.querySelector("#knowledge-panel").innerHTML = `
    <h3>本回重点</h3>
    <h4>主要人物</h4>
    <ul>${focusCards || "<li>暂无可靠资料</li>"}</ul>
    <h4>理解角度</h4>
    <ul>${focusAngles || "<li>暂无可靠资料</li>"}</ul>
  `;
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
  document.querySelector("#topic-knowledge-panel").innerHTML = "";
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (target.matches("[data-view]")) {
    showView(target.dataset.view);
    if (target.dataset.view === "chapters") loadChapter();
    if (target.dataset.view === "topics") loadTopics();
  }
  if (target.matches("[data-question]")) {
    ask(target.dataset.question);
  }
  if (target.matches("[data-card-id]")) {
    const panel = target.closest("#topics") ? "#topic-knowledge-panel" : "#knowledge-panel";
    loadKnowledgeCard(target.dataset.cardId, panel);
  }
  if (target.matches("[data-topic-id]")) {
    loadTopicDetail(target.dataset.topicId);
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
