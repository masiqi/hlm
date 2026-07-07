const views = document.querySelectorAll(".view");
const CHAPTER_TITLES = [
  "甄士隐梦幻识通灵 贾雨村风尘怀闺秀",
  "贾夫人仙逝扬州城 冷子兴演说荣国府",
  "托内兄如海荐西宾 接外孙贾母惜孤女",
  "薄命女偏逢簿命郎 葫芦僧判断葫芦案",
  "贾宝玉神游太虚境 警幻仙曲演红楼梦",
  "贾宝玉初试云雨情 刘老老一进荣国府",
  "送宫花贾琏戏熙凤 宴宁府宝玉会秦钟",
  "贾宝玉奇缘识金锁 薛宝钗巧合认通灵",
  "训劣子李贵承申饬 嗔顽童茗烟闹书房",
  "金寡妇贪利权受辱 张太医论病细穷源",
  "庆寿辰宁府排家宴 见熙凤贾瑞起淫心",
  "王熙凤毒设相思局 贾天祥正照风月鉴",
  "秦可卿死封龙禁尉 王熙凤协理宁国府",
  "林如海灵返苏州郡 贾宝玉路遏北静王",
  "王凤姐弄权铁槛寺 秦鲸卿得趣馒头庵",
  "贾元春才选凤藻宫 秦鲸卿夭逝黄泉路",
  "大观园试才题对额 荣国府归省庆元宵",
  "皇恩重元妃省父母 天伦乐宝玉呈才藻",
  "情切切良宵花解语 意绵绵静日玉生香",
  "王熙凤正言弹妒意 林黛玉俏语谑娇音",
  "贤袭人娇嗔箴宝玉 俏平儿软语救贾琏",
  "听曲文宝玉悟禅机 制灯迷贾政悲谶语",
  "西厢记妙词通戏语 牡丹亭艳曲警芳心",
  "醉金刚轻财尚义侠 痴女儿遗帕惹相思",
  "魇魔法叔嫂逢五鬼 通灵玉蒙蔽遇双真",
  "蜂腰桥设言传心事 潇湘馆春困发幽情",
  "滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红",
  "蒋玉函情赠茜香罗 薛宝钗羞笼红麝串",
  "享福人福深还祷福 多情女情重愈斟情",
  "宝钗借扇机带双敲 椿龄画蔷痴及局外",
  "撕扇子作千金一笑 因麒麟伏白首双星",
  "诉肺腑心迷活宝玉 含耻辱情烈死金钏",
  "手足眈眈小动唇舌 不肖种种大承苔挞",
  "情中情因情感妹妹 错里错以错劝哥哥",
  "白玉钏亲尝莲叶羹 黄金莺巧结梅花络",
  "绣鸳鸯梦兆绛芸轩 识分定情悟梨香院",
  "秋爽斋偶结海棠社 蘅芜院夜拟菊花题",
  "林潇湘魁夺菊花诗 薛蘅芜讽和螃蟹咏",
  "村老老是信口开河 情哥哥偏寻根究底",
  "史太君两宴大观园 金鸳鸯三宣牙牌令",
  "贾宝玉品茶栊翠庵 刘老老醉卧怡红院",
  "蘅芜君兰言解疑癖 潇湘子雅谑补馀音",
  "闲取乐偶攒金庆寿 不了情暂撮土为香",
  "变生不测凤姐泼醋 喜出望外平儿理妆",
  "金兰契互剖金兰语 风雨夕闷制风雨词",
  "尴尬人难免尴尬事 鸳鸯女誓绝鸳鸯偶",
  "呆霸王调情遭苦打 冷郎君惧祸走他乡",
  "滥情人情误思游艺 慕雅女雅集苦吟诗",
  "琉璃世界白雪红梅 脂粉香娃割腥啖膻",
  "芦雪庭争联即景诗 暖香坞雅制春灯谜",
  "薛小妹新编怀古诗 胡庸医乱用虎狼药",
  "俏平儿情掩虾须镯 勇晴雯病补孔雀裘",
  "宁国府除夕祭宗祠 荣国府元宵开夜宴",
  "史太君破陈腐旧套 王熙凤效戏彩斑衣",
  "辱亲女愚妾争闲气 欺幼主刁奴蓄险心",
  "敏探春兴利除宿弊 贤宝钗小惠全大体",
  "慧紫鹃情辞试莽玉 慈姨妈爱语慰痴颦",
  "杏子阴假凤泣虚凰 茜纱窗真情揆痴理",
  "柳叶渚边嗔莺叱燕 绛芸轩里召将飞符",
  "茉莉粉替去蔷薇硝 玫瑰露引出茯苓霜",
  "投鼠忌器宝王瞒赃 判冤决狱平儿行权",
  "憨湘云醉眠芍药裀 呆香菱情解石榴裙",
  "寿怡红群芳开夜宴 死金丹独艳理亲丧",
  "幽淑女悲题五美吟 浪荡子情遗九龙佩",
  "贾二舍偷娶尤二姨 尤三姐思嫁柳二郎",
  "情小妹耻情归地府 冷二郎一冷入空门",
  "见土仪颦卿思故里 闻秘事凤姐讯家童",
  "苦尤娘赚入大观园 酸凤姐大闹宁国府",
  "弄小巧用借剑杀人 觉大限吞生金自逝",
  "林黛玉重建桃花社 史湘云偶填柳絮词",
  "嫌隙人有心生嫌隙 鸳鸯女无意遇鸳鸯",
  "王熙凤恃强羞说病 来旺妇倚势霸成亲",
  "痴丫头误拾绣春囊 懦小姐不问累金凤",
  "惑奸谗抄检大观园 避嫌隙杜绝宁国府",
  "开夜宴异兆发悲音 赏中秋新词得佳谶",
  "凸碧堂品笛感凄清 凹晶馆联诗悲寂寞",
  "俏丫鬟抱屈夭风流 美优怜斩情归水月",
  "老学士闲征姽婳词 痴公子杜撰芙蓉诔",
  "薛文起悔娶河东吼 贾迎春误嫁中山狼",
  "美香菱屈受贪夫棒 王道士胡诌妒妇方",
  "占旺相四美钓游鱼 奉严词两番入家塾",
  "老学究讲义警顽心 病潇湘痴魂惊恶梦",
  "省宫闱贾元妃染恙 闹闺阃薛宝钗吞声",
  "试文字宝玉始提亲 探惊风贾环重结怨",
  "贾存周报升郎中任 薛文起复惹放流刑",
  "受私贿老官翻案牍 寄闲情淑女解琴书",
  "感秋声抚琴悲往事 坐禅寂走火入邪魔",
  "博庭欢宝玉赞孤儿 正家法贾珍鞭悍仆",
  "人亡物在公子填词 蛇影杯弓颦卿绝粒",
  "失绵衣贫女耐嗷嘈 送果品小郎惊叵测",
  "纵淫心宝蟾工设计 步疑阵宝玉妄谈禅",
  "评女传巧姐慕贤良 玩母珠贾政参聚散",
  "甄家仆投靠贾家门 水月庵掀翻风月案",
  "宴海棠贾母赏花妖 失宝玉通灵知奇祸",
  "因讹成实元妃薨逝 以假混真宝玉疯癫",
  "瞒消息凤姐设奇谋 泄机关颦儿迷本性",
  "林黛玉焚稿断痴情 薛宝钗出闺成大礼",
  "苦绛珠魂归离恨天 病神瑛泪洒相思地",
  "守官箴恶奴同破例 阅邸报老舅自担惊",
  "破好事香菱结深恨 悲远嫁宝玉感离情",
  "大观园月夜警幽魂 散花寺神签惊异兆",
  "宁国府骨肉病灾襟 大观园符水驱妖孽",
  "施毒计金桂自焚身 昧真禅雨村空遇旧",
  "醉金刚小鳅生大浪 痴公子馀痛触前情",
  "锦农军查抄宁国府 骢马使弹劾平安州",
  "王熙凤致祸抱羞惭 贾太君祷天消祸患",
  "散馀资贾母明大义 复世职政老沐天恩",
  "强欢笑蘅芜庆生辰 死缠绵潇湘闻鬼哭",
  "候芳魂五儿承错爱 还孽债迎女返真元",
  "史太君寿终归地府 王凤姐力诎失人心",
  "鸳鸯女殉主登太虚 狗彘奴欺天招伙盗",
  "活冤孽妙姑遭大劫 死雠仇赵妾赴冥曹",
  "忏宿冤凤姐托村妪 释旧憾情婢感痴郎",
  "王熙凤历幻返金陵 甄应嘉蒙恩还玉阙",
  "惑偏私惜春矢素志 证同类宝玉失相知",
  "得通灵幻境悟仙缘 送慈柩故乡全孝道",
  "阻超凡佳人双护玉 欣聚党恶子独承家",
  "记微嫌舅兄欺弱女 惊谜语妻妾谏痴人",
  "中乡魁宝玉却尘缘 沐皇恩贾家延世泽",
  "甄士隐详说太虚情 贾雨村归结红楼梦",
];
let currentChapterPayload = null;
let chapterLoadRequestId = 0;
let activeEntityPopoverId = null;
let activeChapterTab = "plot";

function showView(id) {
  views.forEach((view) => view.classList.toggle("active", view.id === id));
}

function clampChapterNumber(value) {
  const number = Number(value || 1);
  if (!Number.isInteger(number)) return 1;
  return Math.min(120, Math.max(1, number));
}

function parseRouteFromHash(hash = window.location.hash) {
  const rawHash = String(hash || "").replace(/^#/, "");
  const rawRoute = rawHash || "/";
  const [rawPath, rawQuery = ""] = rawRoute.split("?");
  const parts = rawPath.split("/").filter(Boolean).map((part) => decodeURIComponent(part));
  const query = new URLSearchParams(rawQuery);
  if (parts[0] === "ask") {
    return { view: "ask", question: query.get("q") || "" };
  }
  if (parts[0] === "chapters") {
    return { view: "chapters", chapterNumber: clampChapterNumber(parts[1] || 1), cardId: query.get("card") || "" };
  }
  if (parts[0] === "topics" && parts[1]) {
    return { view: "topicDetail", topicId: parts[1], cardId: query.get("card") || "" };
  }
  if (parts[0] === "topics") {
    return { view: "topics" };
  }
  return { view: "home" };
}

function routeQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    const text = String(value || "").trim();
    if (text) query.set(key, text);
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

function routeToHash(route = {}) {
  if (route.view === "ask") {
    return `#/ask${routeQuery({ q: route.question })}`;
  }
  if (route.view === "chapters") {
    return `#/chapters/${clampChapterNumber(route.chapterNumber)}${routeQuery({ card: route.cardId })}`;
  }
  if (route.view === "topicDetail" && route.topicId) {
    return `#/topics/${encodeURIComponent(route.topicId)}${routeQuery({ card: route.cardId })}`;
  }
  if (route.view === "topics") {
    return "#/topics";
  }
  return "#/";
}

function navigate(route, options = {}) {
  const hash = routeToHash(route);
  if (window.location.hash === hash) {
    renderRoute(parseRouteFromHash());
    return;
  }
  if (options.replace) {
    window.history.replaceState(null, "", hash);
    renderRoute(parseRouteFromHash());
    return;
  }
  window.location.hash = hash;
}

async function renderRoute(route = parseRouteFromHash()) {
  closeEntityPopover();
  if (route.view === "ask") {
    showView("ask");
    const input = document.querySelector("#question");
    if (input) input.value = route.question || "";
    if (route.question) {
      await ask(route.question);
    }
    return;
  }
  if (route.view === "chapters") {
    showView("chapters");
    await loadChapter(route.chapterNumber || 1);
    if (route.cardId) await loadKnowledgeCard(route.cardId, "#knowledge-panel");
    return;
  }
  if (route.view === "topics") {
    showView("topics");
    await loadTopics();
    return;
  }
  if (route.view === "topicDetail" && route.topicId) {
    showView("topics");
    await loadTopicDetail(route.topicId);
    if (route.cardId) await loadKnowledgeCard(route.cardId, "#topic-knowledge-panel");
    return;
  }
  showView("home");
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`请求失败：${response.status}`);
  return response.json();
}

function chapterCacheUrl(number) {
  return `/chapter_cache/${String(number).padStart(3, "0")}.json`;
}

async function loadChapterPayload(number) {
  try {
    return await getJson(chapterCacheUrl(number));
  } catch (error) {
    return getJson(`/api/chapters/${number}`);
  }
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
    html += `<button class="annotation-link" data-annotation-id="${escapeHtml(annotation.id)}" data-inline-entity-id="${escapeHtml(entityId)}" data-surface-text="${escapeHtml(label)}">${escapeHtml(label)}</button>`;
    cursor = annotation.endOffset;
  });
  html += escapeHtml(text.slice(cursor));
  return html;
}

function normalizeSearchText(value) {
  return String(value || "").replace(/[，。、“”‘’：；！？\s]/g, "");
}

function highlightOriginalTarget(target) {
  document.querySelectorAll(".original-hit-highlight").forEach((item) => item.classList.remove("original-hit-highlight"));
  target.classList.add("original-hit-highlight");
  window.setTimeout(() => target.classList.remove("original-hit-highlight"), 1800);
}

function scrollOriginalTextToNeedle(needle) {
  const original = document.querySelector(".annotated-original");
  if (!original) return;
  const normalizedNeedle = normalizeSearchText(needle);
  if (!normalizedNeedle) return;
  const annotationTarget = Array.from(original.querySelectorAll("[data-surface-text]")).find((item) => {
    const normalizedSurface = normalizeSearchText(item.dataset.surfaceText || item.textContent || "");
    return normalizedSurface && (normalizedNeedle.includes(normalizedSurface) || normalizedSurface.includes(normalizedNeedle));
  });
  const target = annotationTarget || original;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  highlightOriginalTarget(target);
}

function renderList(items = [], renderItem = (item) => escapeHtml(item)) {
  if (!items.length) return "<li>暂无可靠资料</li>";
  return items.map((item) => `<li>${renderItem(item)}</li>`).join("");
}

function renderRichSection(title, items = [], renderItem) {
  return `<section><h4>${escapeHtml(title)}</h4><ul>${renderList(items, renderItem)}</ul></section>`;
}

function renderSourceList(items = [], sourceText = (item) => item) {
  if (!items.length) return "<li>暂无可靠资料</li>";
  return items
    .map((item) => {
      const text = String(sourceText(item) || item || "").trim();
      if (!text) return "<li>暂无可靠资料</li>";
      return `<li><button class="text-link source-jump-link" data-source-needle="${escapeHtml(text)}">${escapeHtml(text)}</button></li>`;
    })
    .join("");
}

function renderChapterTabs(tabs = []) {
  return `
    <div class="chapter-tabs" role="tablist" aria-label="本回资料">
      ${tabs
        .map(
          (tab) =>
            `<button class="chapter-tab${tab.id === activeChapterTab ? " active" : ""}" type="button" role="tab" aria-selected="${tab.id === activeChapterTab ? "true" : "false"}" data-chapter-tab="${escapeHtml(tab.id)}">${escapeHtml(tab.label)}</button>`,
        )
        .join("")}
    </div>
    <div class="chapter-tab-panels">
      ${tabs
        .map(
          (tab) =>
            `<section class="chapter-tab-panel${tab.id === activeChapterTab ? " active" : ""}" role="tabpanel" data-chapter-tab-panel="${escapeHtml(tab.id)}">${tab.html}</section>`,
        )
        .join("")}
    </div>
  `;
}

function setActiveChapterTab(tabId) {
  activeChapterTab = tabId || "plot";
  document.querySelectorAll("[data-chapter-tab]").forEach((tab) => {
    const active = tab.dataset.chapterTab === activeChapterTab;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll("[data-chapter-tab-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.chapterTabPanel === activeChapterTab);
  });
}

function sourceNeedleFromParts(...parts) {
  return parts
    .flat()
    .filter(Boolean)
    .map((part) => String(part).trim())
    .find(Boolean) || "";
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

function sortChapterJumps(jumps = []) {
  return jumps.sort(
    (left, right) => (Number(right.importance || 0) - Number(left.importance || 0)) || (Number(left.chapter || 0) - Number(right.chapter || 0)),
  );
}

function jumpRank(jump, entity) {
  const label = jump.label || "";
  const nameOnlyLabel = `第${jump.chapter}回：${entity.name}`;
  return [
    label === nameOnlyLabel ? 0 : 1,
    Number(jump.importance || 0),
    String(jump.description || "").length,
  ];
}

function shouldReplaceJump(existing, incoming, entity) {
  const currentRank = jumpRank(existing, entity);
  const nextRank = jumpRank(incoming, entity);
  for (let index = 0; index < nextRank.length; index += 1) {
    if (nextRank[index] > currentRank[index]) return true;
    if (nextRank[index] < currentRank[index]) return false;
  }
  return false;
}

function mergeChapterJumpList(existing = [], jump, entity) {
  const index = existing.findIndex((item) => Number(item.chapter || 0) === Number(jump.chapter || 0));
  if (index === -1) return sortChapterJumps([...existing, jump]);
  if (shouldReplaceJump(existing[index], jump, entity)) {
    const next = [...existing];
    next[index] = jump;
    return sortChapterJumps(next);
  }
  return sortChapterJumps(existing);
}

function mergeTraceItems(entity, traceItems = []) {
  const currentChapter = Number(currentChapterPayload?.chapter?.number || 0);
  let previous = entity.previousChapterJumps || [];
  let later = entity.laterChapterJumps || [];
  traceItems.forEach((item) => {
    const jump = {
      chapter: item.chapter,
      label: item.label || `第${item.chapter}回：${item.topic || entity.name}`,
      description: item.description || "",
      importance: item.importance || 0,
    };
    if (currentChapter && Number(jump.chapter || 0) < currentChapter) {
      previous = mergeChapterJumpList(previous, jump, entity);
    } else if (!currentChapter || Number(jump.chapter || 0) > currentChapter) {
      later = mergeChapterJumpList(later, jump, entity);
    }
  });
  entity.previousChapterJumps = previous;
  entity.laterChapterJumps = later;
  entity.chapterJumps = later;
}

function mergeThemeExtensions(entity, themeExtensions = []) {
  const existing = entity.themeExtensions || [];
  const seen = new Set(existing.map((extension) => `${extension.topic}|${extension.description || ""}`));
  themeExtensions.forEach((extension) => {
    const key = `${extension.topic}|${extension.description || ""}`;
    if (!seen.has(key)) {
      seen.add(key);
      existing.push(extension);
    }
  });
  entity.themeExtensions = existing;
}

function renderThemeExtensions(extensions = []) {
  return renderList(extensions, (extension) => {
    const jumps = renderChapterJumps(extension.chapterJumps || []);
    return `<strong>${escapeHtml(extension.topic || "主题线索")}</strong>${extension.description ? `：${escapeHtml(extension.description)}` : ""}<ul>${jumps}</ul>`;
  });
}

function renderExtendedNeighbors(neighbors = []) {
  return renderList(neighbors, (neighbor) => {
    const target = neighbor.to || "相关线索";
    const title = neighbor.via ? `由${escapeHtml(neighbor.via)}延伸到${escapeHtml(target)}` : escapeHtml(target);
    const relationship = neighbor.relationship || "关联";
    const description = neighbor.description || "";
    return `<strong>${title}</strong>${relationship ? `（${escapeHtml(relationship)}）` : ""}${description ? `：${escapeHtml(description)}` : ""}`;
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
      <h4>延伸关联</h4>
      <ul>${renderExtendedNeighbors(entity.extendedNeighbors || [])}</ul>
      <h4>后文关联</h4>
      <ul>${laterClues}</ul>
      <h4>前文关联</h4>
      <ul>${renderChapterJumps(entity.previousChapterJumps || [])}</ul>
      <h4>相关章回</h4>
      <ul>${renderChapterJumps(entity.laterChapterJumps || entity.chapterJumps || [])}</ul>
      <h4>主题延展</h4>
      <ul>${renderThemeExtensions(entity.themeExtensions || [])}</ul>
    </div>
  `;
}

function hasPrefetchedEntityTrace(entity) {
  return Boolean(entity.tracePrefetched);
}

async function loadEntityTrace(entity) {
  if (hasPrefetchedEntityTrace(entity)) return;
  if (activeEntityPopoverId !== entity.id) return;
  const currentChapter = currentChapterPayload?.chapter?.number || "";
  try {
    const data = await getJson(
      `/api/entity-trace?name=${encodeURIComponent(entity.name)}&chapter=${encodeURIComponent(currentChapter)}&type=${encodeURIComponent(entity.type || "")}`,
    );
    if (activeEntityPopoverId !== entity.id) return;
    mergeTraceItems(entity, data.traceItems || []);
    mergeThemeExtensions(entity, data.themeExtensions || []);
    const popover = document.querySelector("#entity-popover.open");
    if (popover) popover.innerHTML = renderEntityPopover(entity);
  } catch (error) {
    // Keep the existing evidence-only content if the supplemental trace cannot be loaded.
  }
}

function markActiveEntityControls(entityId) {
  document.querySelectorAll("[data-inline-entity-id]").forEach((control) => {
    const active = control.dataset.inlineEntityId === entityId;
    control.classList.toggle("entity-chip-active", active && control.classList.contains("entity-chip"));
    control.classList.toggle("annotation-link-active", active && control.classList.contains("annotation-link"));
    control.classList.toggle("text-link-active", active && control.classList.contains("text-link"));
    control.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function openEntityPopover(entityId) {
  const entity = findInlineEntity(entityId);
  if (!entity) return;
  activeEntityPopoverId = entityId;
  let popover = document.querySelector("#entity-popover");
  if (!popover) {
    popover = document.createElement("aside");
    popover.id = "entity-popover";
    popover.className = "entity-popover entity-popover-backdrop";
    document.body.append(popover);
  }
  popover.innerHTML = renderEntityPopover(entity);
  popover.classList.add("open");
  markActiveEntityControls(entityId);
  loadEntityTrace(entity);
}

function closeEntityPopover() {
  activeEntityPopoverId = null;
  document.querySelector("#entity-popover")?.classList.remove("open");
  markActiveEntityControls(null);
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
    navigate({ view: "ask", question: target.dataset.target });
  }
  if (target.dataset.targetType === "chapter") {
    navigate({ view: "chapters", chapterNumber: Number(target.dataset.target) });
  }
  if (target.dataset.targetType === "topic") {
    navigate({ view: "topicDetail", topicId: target.dataset.target });
  }
  if (target.dataset.targetType === "card") {
    navigate({ view: "chapters", chapterNumber: 1, cardId: target.dataset.target });
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

function chapterOptionLabel(number, title = CHAPTER_TITLES[number - 1] || "") {
  return title ? `第 ${number} 回：${title}` : `第 ${number} 回`;
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
    option.textContent = chapterOptionLabel(number);
    chapterSelect.append(option);
  }
}

function updateSelectedChapterOption(chapter) {
  const chapterSelect = document.querySelector("#chapter-select");
  if (!chapterSelect || !chapter?.number) return;
  const option = Array.from(chapterSelect.options).find((item) => item.value === String(chapter.number));
  if (option) option.textContent = chapterOptionLabel(Number(chapter.number), chapter.title || "");
}

function updateChapterNavigation(chapterNumber) {
  const previousChapterButton = document.querySelector("#previous-chapter");
  const nextChapterButton = document.querySelector("#next-chapter");
  if (previousChapterButton) previousChapterButton.disabled = chapterNumber <= 1;
  if (nextChapterButton) nextChapterButton.disabled = chapterNumber >= 120;
}

function inlineEntityIdForName(entities = [], name = "") {
  return (entities || []).find((entity) => entity.name === name)?.id || "";
}

function renderCharacterRows(characters = [], inlineEntities = []) {
  return renderList(characters, (item) => {
    const entityId = inlineEntityIdForName(inlineEntities, item.name);
    const name = entityId
      ? `<button class="text-link" data-inline-entity-id="${escapeHtml(entityId)}">${escapeHtml(item.name)}</button>`
      : `<strong>${escapeHtml(item.name || "人物")}</strong>`;
    return `${name}：${escapeHtml(item.importance || item.role || "")}<br>${escapeHtml((item.actions || []).join("；"))}`;
  });
}

function renderRelationshipRows(relationships = []) {
  return renderList(relationships, (item) => {
    const title = [item.source, item.type, item.target].filter(Boolean).join(" — ");
    const description = item.description || item.chapterEvidence || "";
    return `${escapeHtml(title || "关系线索")}：${escapeHtml(description)}`;
  });
}

function renderNamedRows(items = [], valueForItem = (item) => item.function || item.meaning || item.context || "") {
  return renderList(items, (item) => {
    const name = item.name || item.title || item.quote || "相关信息";
    const value = valueForItem(item);
    return `<button class="text-link source-jump-link" data-source-needle="${escapeHtml(sourceNeedleFromParts(name, value))}"><strong>${escapeHtml(name)}</strong></button>：${escapeHtml(value)}`;
  });
}

function renderChapterSummary(data, hasReviewCard) {
  const plainSummary = hasReviewCard ? escapeHtml(data.reviewCard.plainSummary) : "暂无可靠资料";
  return `<section class="chapter-summary"><h4>本回梗概</h4><p>${plainSummary}</p></section>`;
}

function renderChapterReviewTabs(data, hasReviewCard) {
  const reviewCard = data.reviewCard || {};
  const inlineEntities = data.inlineEntities || [];
  const plotChain = hasReviewCard ? renderSourceList(data.reviewCard.plotChain) : "<li>暂无可靠资料</li>";
  const keyEvents = hasReviewCard ? renderSourceList(data.reviewCard.keyEvents) : "<li>暂无可靠资料</li>";
  const focusAngles = hasReviewCard ? renderSourceList(data.reviewCard.understandingFocus) : "<li>暂无可靠资料</li>";
  const sections = {
    plot: `<section><h4>关键情节</h4><ul>${plotChain}</ul></section>`,
    events: `<section><h4>关键事件</h4><ul>${keyEvents}</ul></section>`,
    focus: `<section><h4>本回怎么读</h4><ul>${focusAngles}</ul></section>`,
    characters: `<section><h4>主要人物</h4><ul>${renderCharacterRows(reviewCard.characters || [], inlineEntities)}</ul></section>`,
    relationships: `<section><h4>人物与事件关系</h4><ul>${renderRelationshipRows(reviewCard.relationships || [])}</ul></section>`,
    places: `<section><h4>地点与物件</h4><ul>${renderNamedRows([...(reviewCard.places || []), ...(reviewCard.objects || [])])}</ul></section>`,
    literary: `<section><h4>诗词语言</h4><ul>${renderNamedRows(
      [...(reviewCard.literaryTexts || []), ...(reviewCard.modernExplanations || [])],
      (item) => item.explanation || item.modernText || item.function || item.value || "",
    )}</ul></section>`,
    later: renderRichSection(
      "后文关联",
      reviewCard.laterAssociations || [],
      (item) => `<strong>${escapeHtml(item.topic || "线索")}</strong>：${escapeHtml(item.description || item.evidence || "")}`,
    ),
    cards: `<section><h4>本回信息卡</h4><div class="entity-chip-list">${renderInlineEntityButtons(inlineEntities)}</div></section>`,
  };
  const allSections = [
    `<div class="chapter-section-grid">${[
      sections.plot,
      sections.events,
      sections.focus,
      sections.cards,
      sections.characters,
      sections.relationships,
      sections.places,
      sections.literary,
      sections.later,
    ].join("")}</div>`,
  ].join("");
  const tabs = [
    { id: "plot", label: "关键情节", html: sections.plot },
    { id: "events", label: "关键事件", html: sections.events },
    { id: "focus", label: "本回怎么读", html: sections.focus },
    { id: "characters", label: "主要人物", html: sections.characters },
    { id: "relationships", label: "人物与事件关系", html: sections.relationships },
    { id: "places", label: "地点与物件", html: sections.places },
    { id: "literary", label: "诗词语言", html: sections.literary },
    { id: "later", label: "后文关联", html: sections.later },
    { id: "cards", label: "本回信息卡", html: sections.cards },
    { id: "all", label: "展示全部", html: allSections },
  ];
  if (!tabs.some((tab) => tab.id === activeChapterTab)) activeChapterTab = "plot";
  return renderChapterTabs(tabs);
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

async function loadChapter(number = 1) {
  const requestId = ++chapterLoadRequestId;
  const data = await loadChapterPayload(number);
  if (requestId !== chapterLoadRequestId) return;
  currentChapterPayload = data;
  closeEntityPopover();
  const chapterSelect = document.querySelector("#chapter-select");
  if (chapterSelect) chapterSelect.value = String(data.chapter.number);
  updateSelectedChapterOption(data.chapter);
  updateChapterNavigation(Number(data.chapter.number));
  const hasReviewCard = Boolean(data.materialStatus?.hasReviewCard && data.reviewCard);
  const reviewCard = data.reviewCard || {};
  const focusAngles = hasReviewCard
    ? data.reviewCard.understandingFocus.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>暂无可靠资料</li>";
  const focusCards = (reviewCard.characters || [])
    .map((item) => `<li><strong>${escapeHtml(item.name)}</strong>：${escapeHtml(item.importance || item.role || "")}</li>`)
    .join("");
  document.querySelector("#chapter-content").innerHTML = `
    <h3>第 ${escapeHtml(data.chapter.number)} 回：${escapeHtml(data.chapter.title)}</h3>
    ${renderChapterSummary(data, hasReviewCard)}
    ${renderChapterReviewTabs(data, hasReviewCard)}
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
  const topicList = document.querySelector("#topic-list");
  topicList.className = "topic-groups";
  topicList.innerHTML = renderTopicGroups(data.topicGroups || groupTopicsByCategory(data.topics || []));
  document.querySelector(panelContentSelector("#topic-knowledge-panel")).innerHTML = "";
  closeKnowledgePanel("topic-knowledge-panel");
}

function groupTopicsByCategory(topics = []) {
  const groupsByCategory = new Map();
  topics.forEach((topic) => {
    const category = topic.category || "专题";
    if (!groupsByCategory.has(category)) {
      groupsByCategory.set(category, {
        category,
        description: "围绕相关专题线索组织。",
        count: 0,
        topics: [],
      });
    }
    const group = groupsByCategory.get(category);
    group.topics.push(topic);
    group.count = group.topics.length;
  });
  return Array.from(groupsByCategory.values());
}

function renderTopicGroups(groups = []) {
  if (!groups.length) return "<p>暂无可靠资料</p>";
  return groups
    .map((group) => {
      const topics = group.topics || [];
      return `
        <details class="topic-group">
          <summary class="topic-group-header">
            <div>
              <h3>${escapeHtml(group.category || "专题")}</h3>
              <p>${escapeHtml(group.description || "")}</p>
            </div>
            <span>${escapeHtml(group.count || topics.length)} 个专题</span>
          </summary>
          <div class="topic-grid">${topics.map(renderTopicCard).join("")}</div>
        </details>
      `;
    })
    .join("");
}

function renderTopicCard(topic) {
  return `<article><h4>${escapeHtml(topic.title)}</h4><p>${escapeHtml(topic.description)}</p><button data-topic-id="${escapeHtml(topic.id)}">查看专题</button></article>`;
}

function renderChapterJumpButton(label, chapter, labelIsEscaped = false) {
  const chapterNumber = Number(chapter);
  const text = labelIsEscaped ? label : escapeHtml(label);
  if (!Number.isInteger(chapterNumber) || chapterNumber < 1) return text;
  return `<button class="text-link" data-chapter-number="${escapeHtml(chapterNumber)}">${text}</button>`;
}

function renderTopicGraphRelations(relations = []) {
  if (!relations.length) return "";
  return relations
    .map((relation) => {
      const relationship = relation.relationship ? `（${escapeHtml(relation.relationship)}）` : "";
      const description = relation.description ? `：${escapeHtml(relation.description)}` : "";
      return `<li><strong>${escapeHtml(relation.name || "相关线索")}</strong>${relationship}${description}</li>`;
    })
    .join("");
}

async function loadTopicDetail(topicId) {
  const data = await getJson(`/api/topics/${topicId}`);
  const cards = data.cards.map((card) => `<li><button data-card-id="${escapeHtml(card.id)}">${escapeHtml(card.name)}</button></li>`).join("");
  const relations = data.relations
    .map((relation) => `<li>${renderChapterJumpButton(escapeHtml(relation.description), relation.chapters?.[0], true)}</li>`)
    .join("");
  const graphRelations = renderTopicGraphRelations(data.topicContext?.graphRelations || []);
  const relationClues = [relations, graphRelations].filter(Boolean).join("");
  const facts = data.evidence
    .map((item) => `<li class="source">${renderChapterJumpButton(`第 ${item.chapter || ""} 回：${item.evidenceText}`, item.chapter)}</li>`)
    .join("");
  const patterns = data.topic.typicalQuestionPatterns.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const introduction = data.topicContext?.introduction
    ? `<h4>专题简介</h4><p>${escapeHtml(data.topicContext.introduction)}</p>`
    : "";
  const topicList = document.querySelector("#topic-list");
  topicList.className = "topic-detail";
  topicList.innerHTML = `
    <article>
      <button data-topic-list-return type="button">返回专题</button>
      <h3>${escapeHtml(data.topic.title)}</h3>
      <p>${escapeHtml(data.topic.description)}</p>
      ${introduction}
      <h4>核心知识卡</h4>
      <ul>${cards || "<li>暂无可靠资料</li>"}</ul>
      <h4>关系线索</h4>
      <ul>${relationClues || "<li>暂无可靠资料</li>"}</ul>
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
  const viewTarget = target.closest("[data-view]");
  const commonTarget = target.closest("[data-target-type]");
  const cardTarget = target.closest("[data-card-id]");
  const inlineEntityTarget = target.closest("[data-inline-entity-id]");
  const popoverCloseTarget = target.closest("[data-entity-popover-close]");
  const popoverBackdropTarget = target.id === "entity-popover" ? target : null;
  const topicTarget = target.closest("[data-topic-id]");
  const chapterTarget = target.closest("[data-chapter-number]");
  const chapterStepTarget = target.closest("[data-chapter-step]");
  const chapterTabTarget = target.closest("[data-chapter-tab]");
  const sourceNeedleTarget = target.closest("[data-source-needle]");
  const traceChapterTarget = target.closest("[data-trace-chapter-number]");
  const panelCloseTarget = target.closest("[data-panel-close]");
  const topicListReturnTarget = target.closest("[data-topic-list-return]");
  if (viewTarget) {
    const view = viewTarget.dataset.view;
    if (view === "ask") navigate({ view: "ask" });
    if (view === "chapters") navigate({ view: "chapters", chapterNumber: 1 });
    if (view === "topics") navigate({ view: "topics" });
    if (view === "home") navigate({ view: "home" });
    return;
  }
  if (commonTarget) {
    handleCommonEntry(commonTarget);
    return;
  }
  if (cardTarget) {
    const route = parseRouteFromHash();
    if (route.view === "topicDetail") {
      navigate({ ...route, cardId: cardTarget.dataset.cardId });
    } else if (route.view === "chapters") {
      navigate({ ...route, cardId: cardTarget.dataset.cardId });
    } else {
      navigate({ view: "chapters", chapterNumber: 1, cardId: cardTarget.dataset.cardId });
    }
    return;
  }
  if (inlineEntityTarget) {
    openEntityPopover(inlineEntityTarget.dataset.inlineEntityId);
    return;
  }
  if (popoverCloseTarget) {
    closeEntityPopover();
    return;
  }
  if (popoverBackdropTarget) {
    closeEntityPopover();
    return;
  }
  if (topicTarget) {
    navigate({ view: "topicDetail", topicId: topicTarget.dataset.topicId });
    return;
  }
  if (topicListReturnTarget) {
    navigate({ view: "topics" });
    return;
  }
  if (chapterTarget) {
    navigate({ view: "chapters", chapterNumber: Number(chapterTarget.dataset.chapterNumber) });
    return;
  }
  if (chapterStepTarget) {
    const currentNumber = Number(currentChapterPayload?.chapter?.number || document.querySelector("#chapter-select")?.value || 1);
    const nextNumber = Math.min(120, Math.max(1, currentNumber + Number(chapterStepTarget.dataset.chapterStep || 0)));
    navigate({ view: "chapters", chapterNumber: nextNumber });
    return;
  }
  if (chapterTabTarget) {
    setActiveChapterTab(chapterTabTarget.dataset.chapterTab);
    return;
  }
  if (sourceNeedleTarget) {
    scrollOriginalTextToNeedle(sourceNeedleTarget.dataset.sourceNeedle);
    return;
  }
  if (traceChapterTarget) {
    navigate({ view: "chapters", chapterNumber: Number(traceChapterTarget.dataset.traceChapterNumber) });
    return;
  }
  if (panelCloseTarget) {
    const route = parseRouteFromHash();
    if (route.cardId) {
      const { cardId, ...routeWithoutCard } = route;
      navigate(routeWithoutCard);
    } else {
      closeKnowledgePanel(panelCloseTarget.dataset.panelClose);
    }
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeEntityPopover();
});

document.querySelector("#chapter-select").addEventListener("change", (event) => {
  navigate({ view: "chapters", chapterNumber: Number(event.currentTarget.value) });
});

document.querySelector("#ask-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = new FormData(event.currentTarget).get("question");
  navigate({ view: "ask", question: String(question || "") });
});

initChapterSelector();
loadHome();
window.addEventListener("hashchange", () => {
  renderRoute(parseRouteFromHash());
});
renderRoute(parseRouteFromHash());
