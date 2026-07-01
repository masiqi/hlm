const views = document.querySelectorAll(".view");

function showView(id) {
  views.forEach((view) => view.classList.toggle("active", view.id === id));
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`请求失败：${response.status}`);
  return response.json();
}

function renderAnswer(answer) {
  const container = document.querySelector("#answer");
  if (answer.status === "refused") {
    container.innerHTML = `<h3>当前资料不足</h3><p>${answer.refusal.message}</p>`;
    showView("ask");
    return;
  }
  const claims = answer.shortConclusion.map((claim) => `<li>${claim.text}</li>`).join("");
  const sources = answer.evidence
    .map((evidence) => `<li class="source">第 ${evidence.chapter} 回：${evidence.evidenceText}</li>`)
    .join("");
  const facts = (answer.quotableFacts?.claims || []).map((claim) => `<li>${claim.text}</li>`).join("");
  const partialNote =
    answer.status === "partial" && answer.refusal ? `<h3>未回答部分</h3><p>${answer.refusal.message}</p>` : "";
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
    .map((entry) => `<button data-question="${entry.target}">${entry.label}</button>`)
    .join("");
}

async function loadChapter(number = 27) {
  const data = await getJson(`/api/chapters/${number}`);
  const focusCards = data.knowledgeCards
    .map((card) => `<li><strong>${card.name}</strong>：${card.brief}</li>`)
    .join("");
  const focusAngles = data.reviewCard.understandingFocus.map((item) => `<li>${item}</li>`).join("");
  document.querySelector("#chapter-content").innerHTML = `
    <h3>第 ${data.chapter.number} 回：${data.chapter.title}</h3>
    <section><h4>本回梗概</h4><p>${data.reviewCard.plainSummary}</p></section>
    <section><h4>关键情节</h4><ul>${data.reviewCard.plotChain.map((item) => `<li>${item}</li>`).join("")}</ul></section>
    <section><h4>原文</h4><pre>${data.originalText}</pre></section>
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
    .map((topic) => `<article><h3>${topic.title}</h3><p>${topic.description}</p></article>`)
    .join("");
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
});

document.querySelector("#ask-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = new FormData(event.currentTarget).get("question");
  ask(String(question || ""));
});

loadHome();
