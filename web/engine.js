/* 내규챗봇 엔진: 문답 카드 검색, 되묻기 판단, 조문 검색, 계산기.
 * 브라우저에서는 NaegyuEngine 전역으로, node 에서는 require 로 쓴다. 외부 의존성 없음. */
(function (root) {
  "use strict";

  // ── 글자 정리와 일상어 → 규정어 보강 ──────────────────────────────
  // 일상어를 지우지 않고 규정어를 덧붙인다. 원래 표현도 계속 검색에 쓰인다.
  var SYNONYMS = [
    [/와이프|아내|부인|집사람|와입|신랑|남편/, "배우자"],
    [/아빠|남자|남성|남직원/, "배우자 남성직원"],
    [/엄마|여자|여성|여직원/, "여성직원"],
    [/부부|둘\s?다|같이|함께|남편도|아내도|와이프도/, "부모 모두"],
    [/쉬어도|쉬고|쉴\s?수|쉬어야|빠져도|빠질/, "휴가"],
    [/예정/, "출산예정일"],
    [/애기|아기|아가|신생아|갓난/, "자녀 유아"],
    [/아이|애들|자식|아들|딸|첫째|둘째|셋째|막내|(^|\s)애($|\s|가|를|는|랑|도|의)/, "자녀"],
    [/육휴/, "육아휴직"],
    [/산휴|산전후|출산\s?휴가/, "출산전후휴가"],
    [/배출|배우자\s?출산/, "배우자 출산전후휴가"],
    [/시험관|체외\s?수정|ivf|인공\s?수정|난임|이식/, "난임치료 난임"],
    [/유축|모유|젖|수유/, "수유시간"],
    [/생리/, "보건휴가"],
    [/야근|초과\s?근무|연장\s?근[무로]|잔업|밤\s?늦게/, "시간외 근로 야간"],
    [/주말|토요일|일요일|공휴일/, "휴일 토요일 공휴일"],
    [/월급|급여|봉급|임금/, "보수 유급 급여"],
    [/연차/, "연가"],
    [/단축\s?근무|덜\s?일|근무\s?시간\s?줄/, "근로시간 단축"],
    [/등원|하원|등교|하교/, "육아돌봄시간 출근 퇴근"],
    [/어린이집|유치원|학교/, "어린이집등"],
    [/방학|휴원|휴교|휴업/, "방학 휴원 휴교"],
    [/노산|마흔|40살/, "40세"],
    [/쌍둥이|세쌍둥이|다둥이|다태아/, "둘 이상 다태아"],
    [/조산|고위험|위험\s?임신/, "위험 유산 조산"],
    [/입덧|임신\s?초기|힘들/, "임신 중"],
    [/막달/, "37주 이후"],
    [/계류|자연\s?유산|잃었|유산/, "유산 사산"],
    [/낙태|중절/, "인공임신중절"],
    [/상담|학부모|행사|입학식|졸업식/, "공식 행사 상담"],
    [/예방\s?접종|병원|진료|아파|아프|독감|감기|수술/, "병원 진료 질병"],
    [/간병|간호|병간호/, "간호 돌봄 요양"],
    [/포인트|복지\s?카드/, "복지포인트"],
    [/수당/, "가족수당"],
    [/경력|호봉|근속|승진/, "근속년수 근속기간"],
    [/평가|고과/, "평가"],
    [/해외|외국|출국|여행|미국/, "국외 출국"],
    [/축하금|장려금|지원금|선물/, "축하금"],
    [/보육|베이비\s?시터|돌보미/, "어린이집 보육"],
    [/검진|산부인과|정기\s?검사|산전\s?검사|정기\s?진료/, "정기건강진단 임산부"],
    [/출퇴근|출근\s?시간|퇴근\s?시간|늦게\s?출근|일찍\s?퇴근|시차/, "출근 퇴근 시각"],
    [/비행기|항공|좌석|비즈니스/, "항공운임 국외출장"],
    [/신청서|양식|서식/, "신청서 서식"],
    [/제왕\s?절개|분만|낳/, "출산"]
  ];

  var SPOUSE_CUE = /배우자|와이프|아내|부인|집사람|와입|남편|신랑|아빠|남자|남성/;

  function normalize(s) {
    return String(s || "").normalize("NFC").toLowerCase().replace(/[^0-9a-z가-힣\s]/g, " ").replace(/\s+/g, " ").trim();
  }

  // 질문의 말끝과 군말. 뜻이 없는데 글자 수가 많아 점수를 끌고 다니므로 뺀다.
  var STOP_TOKENS = new Set(("어떻게 어떡해 어케 되나요 돼요 되요 될까요 되는지 되는 해요 하나요 할까요 하는지 있나요 있어요 있어 있음 있는 있는지 있을까요 " +
    "인가요 뭐예요 뭔가요 무엇 뭐 얼마 얼마나 몇 며칠 몇일 알려주세요 알려줘 궁금해요 궁금 싶어요 싶어 싶은데 가능한가요 가능 할 쓸 받을 수 " +
    "주세요 좀 혹시 제가 저는 저도 저 나 내가 나도 그 이 거 것 건가요 하면 되면 그냥 이거 어디 언제 왜 누가 맞나요 맞아요 해야 돼 되나 " +
    "하는데 인데 는데 있는데 같은데 요 네 음 대해 관련 경우 때 " +
    "오늘 내일 모레 지금 곧 이번주 다음주 이번달 다음달 지난주 지난달 올해 내년 작년 " +
    "싶 있 없 되 받 하 가 타 썼 됐 쓰 줄 드 쉴 가려 가야 하셔서 해서 했 됨 함 임 너무 정말 진짜 많이 " +
    "전 후 전에 후에 동안 이후 이전 개월 쉬어야 써야 해야").split(" "));
  // 말끝 → 조사 순서로 한 번씩 뗀다. 조사는 남는 글자가 2자 이상일 때만 뗀다("휴가"의 '가'는 그대로).
  var ENDINGS = /(했어요|했는데|해요|해야|하나요|합니다|이에요|예요|에요|인가요|나요|까요|어요|아요|돼요|되요|게요|는데|인데|이라서|이라|라서|이요|요|하고|하면|해서)$/;
  var PARTICLES = /(에서|에게|한테|으로|이랑|부터는|은|는|을|를|도|에|랑|로)$/;

  // '가', '이'는 낱말 끝 글자인 경우가 많아(휴가, 평가, 어린이) 따로 지킨다.
  var KEEP_GA_I = /(휴가|평가|단가|참가|국가|대가|추가|어린이)$/;

  function content(s) {
    return normalize(s).split(" ").map(function (t) {
      var u = t.replace(ENDINGS, "");
      if (!u) u = t;
      var v = u.replace(PARTICLES, "");
      if (v.length < 2) v = u;
      if (/[가이]$/.test(v) && v.length >= 3 && !KEEP_GA_I.test(v)) v = v.slice(0, -1);
      return v;
    }).filter(function (t) { return t && !STOP_TOKENS.has(t); }).join(" ");
  }

  // 일상어에 맞는 규정어 목록. 원래 표현은 남기고 규정어를 따로 돌려준다.
  function synonymsOf(s) {
    var n = normalize(s), extra = [];
    for (var i = 0; i < SYNONYMS.length; i++) if (SYNONYMS[i][0].test(n)) extra.push(SYNONYMS[i][1]);
    return extra.join(" ");
  }

  function expand(s) {
    var c = content(s), x = synonymsOf(s);
    return x ? c + " " + x : c;
  }

  // 낱말마다 두 글자씩 자른다. 낱말 경계를 넘는 조각("아내 제왕"→"내제")은 뜻이 없어 만들지 않는다.
  // "육아 휴직"과 "육아휴직"은 '육아', '휴직'을 함께 가져 띄어쓰기가 달라도 잘 맞는다.
  function bigrams(s) {
    var m = new Map();
    s.split(/\s+/).forEach(function (t) {
      if (t.length === 1) { m.set(t, (m.get(t) || 0) + 1); return; }
      for (var i = 0; i < t.length - 1; i++) {
        var g = t.slice(i, i + 2);
        m.set(g, (m.get(g) || 0) + 1);
      }
    });
    return m;
  }

  function vectorize(counts, idf) {
    var v = new Map(), norm = 0;
    counts.forEach(function (c, g) {
      var w = (1 + Math.log(c)) * (idf.get(g) || 0);
      if (w > 0) { v.set(g, w); norm += w * w; }
    });
    norm = Math.sqrt(norm) || 1;
    v.forEach(function (w, g) { v.set(g, w / norm); });
    return v;
  }

  function cosine(a, b) {
    var s = 0, small = a.size < b.size ? a : b, big = small === a ? b : a;
    small.forEach(function (w, g) { var o = big.get(g); if (o) s += w * o; });
    return s;
  }

  // ── 문답 카드 색인 ──────────────────────────────────────────────
  // 카드 하나에 여러 문서: 제목, 요약, 예상 질문 하나하나, 사실 항목 묶음.
  function CardIndex(cards) {
    this.cards = cards;
    this.byId = new Map(cards.map(function (c) { return [c.id, c]; }));
    var docs = [];
    cards.forEach(function (c) {
      docs.push({ card: c.id, text: c.title, weight: 1.0, kind: "title" });
      docs.push({ card: c.id, text: c.summary, weight: 0.8, kind: "summary" });
      c.questions.forEach(function (q, i) { docs.push({ card: c.id, text: q, weight: 1.0, kind: "q", qi: i }); });
      (c.keywords || []).forEach(function (k) { docs.push({ card: c.id, text: k, weight: 0.9, kind: "kw" }); });
      docs.push({ card: c.id, text: c.facts.map(function (f) { return f.label + " " + f.value; }).join(" "), weight: 0.7, kind: "facts" });
    });
    // 카드 쪽 글에는 동의어를 덧붙이지 않는다. 덧붙이면 '육아휴직 수당' 같은 문장이 '가족수당'과도 맞아 버린다.
    var df = new Map();
    docs.forEach(function (d) {
      d.counts = bigrams(content(d.text));
      d.counts.forEach(function (_, g) { df.set(g, (df.get(g) || 0) + 1); });
    });
    var N = docs.length, idf = new Map();
    df.forEach(function (n, g) { idf.set(g, Math.log((N + 1) / (n + 0.5))); });
    this.idf = idf;
    // 카드 어디에도 없는 글자는 드문 글자로 친다. 그래야 분야 밖 질문의 포괄도가 낮아진다.
    this.unseenIdf = Math.log((N + 1) / 2);
    docs.forEach(function (d) {
      d.vec = vectorize(d.counts, idf);
      d.mass = 0;
      d.counts.forEach(function (_, g) { d.mass += idf.get(g); });
    });
    this.docs = docs;
  }

  // 질문 글자 묶음. 직원이 쓴 말은 무게 1, 덧붙인 규정어는 무게 0.5.
  CardIndex.prototype.query = function (text) {
    var own = bigrams(content(text)), syn = bigrams(normalize(synonymsOf(text))), w = new Map(), self = this;
    own.forEach(function (_, g) { w.set(g, 1); });
    syn.forEach(function (_, g) { if (!w.has(g)) w.set(g, 0.5); });
    // 포괄도의 분모는 직원이 쓴 말만. 덧붙인 규정어는 맞으면 더해 주고, 안 맞아도 깎지 않는다.
    var total = 0;
    own.forEach(function (_, g) { total += self.idf.get(g) || self.unseenIdf; });
    var counts = new Map(own);
    syn.forEach(function (c, g) { counts.set(g, (counts.get(g) || 0) + c); });
    // 분야 적합도: 직원이 쓴 글자 중 카드에 나오는 글자의 비중. 알아들은 규정어는 '아는 말'로 더한다.
    var seen = 0, all = 0;
    own.forEach(function (_, g) { var v = self.idf.get(g); all += v || self.unseenIdf; if (v) seen += v; });
    syn.forEach(function (_, g) { var v = self.idf.get(g) || 0; seen += 0.5 * v; all += 0.5 * v; });
    return { weights: w, total: total || 1, vec: vectorize(counts, this.idf), domain: all ? seen / all : 0, spouse: SPOUSE_CUE.test(normalize(text)) };
  };

  // 문서 점수 = 포괄도(질문 글자가 문서에 얼마나 들어 있나) 0.5 + 정밀도(문서 글자가 질문에 얼마나 들어 있나) 0.25
  //           + 코사인 유사도 0.25. 정밀도는 짧은 질문이 여러 카드에 똑같이 걸릴 때 더 딱 맞는 쪽을 고른다.
  // skip(doc) 이 참인 문서는 빼고 점수를 낸다. 시험에서 질문 자신을 빼는 데 쓴다.
  CardIndex.prototype.score = function (query, skip) {
    var q = this.query(query), best = new Map(), idf = this.idf, unseen = this.unseenIdf;
    for (var i = 0; i < this.docs.length; i++) {
      var d = this.docs[i];
      if (skip && skip(d)) continue;
      var hit = 0, back = 0;
      q.weights.forEach(function (wt, g) { if (d.counts.has(g)) { hit += wt * (idf.get(g) || unseen); back += idf.get(g) || 0; } });
      var s = (0.5 * Math.min(1, hit / q.total) + 0.25 * (d.mass ? Math.min(1, back / d.mass) : 0) + 0.25 * cosine(q.vec, d.vec)) * d.weight;
      if (s > (best.get(d.card) || 0)) best.set(d.card, s);
    }
    // 누구의 일인지 단서: 배우자 카드는 배우자 단서가 없으면, 본인 카드는 배우자 단서가 있으면 깎는다.
    var byId = this.byId;
    best.forEach(function (s, id) {
      var cue = byId.get(id).cue;
      if ((cue === "spouse" && !q.spouse) || (cue === "self" && q.spouse)) best.set(id, s * 0.8);
    });
    this.lastQuery = q;
    var out = [];
    best.forEach(function (s, id) { out.push({ id: id, score: s }); });
    out.sort(function (a, b) { return b.score - a.score; });
    return out;
  };

  var T = { HI: 0.40, LO: 0.24, GAP: 0.12, NEAR: 0.80, DOMAIN: 0.30 };

  // 점수로 답할지, 되물을지, 조문 검색으로 넘길지 정한다.
  // 질문 글자 대부분이 카드에 없는 말이면(분야 밖) 조문 검색으로 넘긴다.
  // "출산", "아기"처럼 한 단어뿐인 질문은 점수가 높아도 되묻는다.
  function decide(ranked, queryText, q) {
    var top = ranked[0], second = ranked[1] || { score: 0 };
    if (!top || top.score < T.LO) return { mode: "fallback" };
    if (q && q.domain < T.DOMAIN) return { mode: "fallback", offDomain: true, ids: ranked.slice(0, 2).map(function (r) { return r.id; }) };
    var c = queryText === undefined ? null : content(queryText);
    if (c !== null && c.indexOf(" ") < 0 && c.replace(/\s/g, "").length <= 4 && top.score - second.score < 0.2) {
      var cands = ranked.filter(function (r) { return r.score >= T.LO; }).slice(0, 4);
      if (cands.length > 1) return { mode: "ask", ids: cands.map(function (r) { return r.id; }), vague: true };
    }
    var near = ranked.filter(function (r) { return r.score >= Math.max(T.LO, top.score * T.NEAR); }).slice(0, 4);
    if (top.score >= T.HI && (top.score - second.score >= T.GAP || near.length === 1)) {
      return { mode: "answer", id: top.id, alts: ranked.slice(1, 4).filter(function (r) { return r.score >= T.LO; }).map(function (r) { return r.id; }) };
    }
    if (near.length === 1) return { mode: "answer", id: top.id, soft: true, alts: [] };
    return { mode: "ask", ids: near.map(function (r) { return r.id; }) };
  }

  // ── 조문 검색 (BM25) ───────────────────────────────────────────
  function ArticleIndex(rules) {
    var docs = [];
    rules.forEach(function (r) {
      r.articles.forEach(function (a) {
        docs.push({ rule: r.name, no: a.no, title: a.title, text: a.text, kind: "article" });
      });
      (r.annexes || []).forEach(function (x) {
        docs.push({ rule: r.name, no: x.title, title: "", text: x.text, kind: "annex" });
      });
    });
    var df = new Map(), total = 0;
    docs.forEach(function (d) {
      d.counts = bigrams(normalize(d.rule + " " + d.title + " " + d.text));
      d.len = 0;
      d.counts.forEach(function (c, g) { d.len += c; df.set(g, (df.get(g) || 0) + 1); });
      total += d.len;
    });
    this.docs = docs;
    this.df = df;
    this.avg = total / Math.max(1, docs.length);
  }

  ArticleIndex.prototype.search = function (query, k) {
    var q = bigrams(expand(query)), N = this.docs.length, df = this.df, avg = this.avg, k1 = 1.2, b = 0.75;
    var scored = this.docs.map(function (d) {
      var s = 0;
      q.forEach(function (_, g) {
        var f = d.counts.get(g);
        if (!f) return;
        var idf = Math.log(1 + (N - df.get(g) + 0.5) / (df.get(g) + 0.5));
        s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * d.len / avg));
      });
      return { doc: d, score: s };
    });
    scored.sort(function (a, b2) { return b2.score - a.score; });
    return scored.slice(0, k || 5).filter(function (r) { return r.score > 0; });
  };

  // 검색어 글자가 가장 많이 몰린 구간을 미리보기로 잘라낸다.
  function snippet(text, query, width) {
    width = width || 140;
    var q = bigrams(normalize(query)), flat = text.replace(/\s+/g, " "), best = 0, bestAt = 0;
    for (var i = 0; i < flat.length; i += 10) {
      var win = flat.slice(i, i + width), s = 0;
      q.forEach(function (_, g) { if (win.indexOf(g) >= 0) s++; });
      if (s > best) { best = s; bestAt = i; }
    }
    var out = flat.slice(bestAt, bestAt + width);
    return (bestAt > 0 ? "…" : "") + out + (bestAt + width < flat.length ? "…" : "");
  }

  // ── 날짜 계산 ─────────────────────────────────────────────────
  // 시간대 문제를 피하려고 날짜를 UTC 자정으로만 다룬다.
  function parseDate(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || "");
    return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : null;
  }
  function addDays(d, n) { return new Date(d.getTime() + n * 86400000); }
  function fmt(d) {
    var w = "일월화수목금토"[d.getUTCDay()];
    return d.getUTCFullYear() + "." + (d.getUTCMonth() + 1) + "." + d.getUTCDate() + ".(" + w + ")";
  }
  function iso(d) { return d.toISOString().slice(0, 10); }
  // 만 n세가 되기 전날 = n번째 생일 전날
  function dayBeforeBirthday(birth, years) {
    var y = birth.getUTCFullYear() + years, m = birth.getUTCMonth(), day = birth.getUTCDate();
    var bd = new Date(Date.UTC(y, m, day));
    if (bd.getUTCMonth() !== m) bd = new Date(Date.UTC(y, m + 1, 1)); // 2월 29일생
    return addDays(bd, -1);
  }
  // 정상 입학(태어난 해 + 7년 3월) 기준으로 초등학교 n학년이 끝나는 날(그다음 해 2월 말)
  function endOfGrade(birth, grade) {
    var y = birth.getUTCFullYear() + 7 + grade;
    return addDays(new Date(Date.UTC(y, 2, 1)), -1);
  }

  var CUT_SPOUSE_LOSS = parseDate("2026-09-18");
  var CUT_SPOUSE_PREBIRTH = parseDate("2026-09-18");
  var CUT_INFERTILITY = parseDate("2026-11-27");

  var calc = {
    // 배우자 출산전후휴가: 사용 가능 기간
    spouseBirth: function (o) {
      var due = parseDate(o.due), birth = parseDate(o.birth) || null;
      if (!due) return { error: "출산예정일을 입력하세요." };
      var days = o.multiple ? 25 : 20, start = addDays(due, -50), notes = [];
      if (start < CUT_SPOUSE_PREBIRTH) {
        notes.push("출산 전 사용은 2026.9.18.부터 적용되므로, 그 전 날짜에는 쓸 수 없습니다.");
        start = CUT_SPOUSE_PREBIRTH;
      }
      var base = birth || due, last = addDays(base, 120);
      return {
        rows: [
          ["휴가일수", days + "일 (유급, 모두 사용해야 함)"],
          ["쓸 수 있는 첫날", fmt(start) + " (출산예정일 50일 전)"],
          ["쓸 수 있는 마지막 무렵", fmt(last) + (birth ? " (출산일 + 120일)" : " (예정일에 출산한다고 가정, 출산일 + 120일)")],
          ["나눠 쓰기", "3회까지"],
          ["자동육아휴직 신청서", "배우자 출산휴가 시작일까지 제출 (별지 제15-3호)"]
        ],
        notes: notes.concat([
          "토요일·공휴일은 휴가일수 " + days + "일에 넣지 않습니다.",
          "'출산한 날부터 120일이 지나면' 쓸 수 없습니다. 마지막 날을 출산일 포함으로 세는지는 인사팀에 확인하세요."
        ])
      };
    },
    // 본인 출산전후휴가
    maternity: function (o) {
      var due = parseDate(o.due);
      if (!due) return { error: "출산예정일을 입력하세요." };
      var multi = !!o.multiple, total = multi ? 120 : 90, after = multi ? 60 : 45, paid = multi ? 75 : 60;
      var before = total - after, earliest = addDays(due, -before);
      var start = parseDate(o.start) || earliest, rows = [
        ["휴가일수", total + "일" + (multi ? " (둘 이상 임신)" : " (미숙아 출산 시 100일)")],
        ["출산 후 최소", after + "일"],
        ["출산 전 최대", before + "일 → 예정일 기준 가장 이른 시작일 " + fmt(earliest)],
        ["시작일(가정)", fmt(start)],
        ["유급 기간", "최초 " + paid + "일 → " + fmt(addDays(start, paid - 1)) + "까지"],
        ["휴가 끝 무렵", fmt(addDays(start, total - 1))],
        ["출산휴가·자동육아휴직 신청서", fmt(addDays(start, -15)) + "까지 제출 (시작일 15일 전, 별지 제15-2호)"]
      ], notes = ["30일 이상 이어지는 휴가라 토요일·공휴일도 일수에 포함됩니다.", "실제 출산일에 따라 출산 후 " + after + "일을 채우도록 끝나는 날이 달라질 수 있습니다."];
      if (start < earliest) notes.unshift("시작일이 너무 이릅니다. 출산 전에는 최대 " + before + "일까지 쓸 수 있습니다(분할 사유가 있으면 예외).");
      return { rows: rows, notes: notes };
    },
    // 유산·사산휴가 (본인 / 배우자)
    loss: function (o) {
      var d = parseDate(o.date);
      if (!d) return { error: "유산·사산한 날을 입력하세요." };
      if (o.who === "spouse") {
        var after = d >= CUT_SPOUSE_LOSS;
        return {
          rows: [
            ["휴가일수", after ? "5일 이내 (최초 3일 유급, 2일 무급)" : "3일 이내 (유급)"],
            ["적용 기준", after ? "유산·사산일이 2026.9.18. 이후" : "유산·사산일이 2026.9.17. 이전"],
            ["신청 기한", fmt(addDays(d, 20)) + " 무렵 (유산·사산한 날부터 20일 이내)"]
          ],
          notes: ["신청 기한의 마지막 날을 유산일 포함으로 세는지는 인사팀에 확인하세요."]
        };
      }
      var w = +o.weeks;
      if (!(w > 0)) return { error: "임신 주수를 입력하세요." };
      var days = w <= 15 ? 10 : w <= 21 ? 30 : w <= 27 ? 60 : 90;
      return {
        rows: [
          ["휴가 기간", "유산·사산한 날부터 " + days + "일까지"],
          ["끝나는 날", fmt(addDays(d, days - 1)) + " (유산·사산일을 1일째로 셀 때)"],
          ["급여", days === 90 ? "최초 60일까지 유급" : "유급"]
        ],
        notes: ["임신 15주와 16주 사이처럼 경계에 걸리면 인사팀에 확인하세요."]
      };
    },
    // 자녀 나이로 쓸 수 있는 제도
    childAge: function (o) {
      var b = parseDate(o.birth), today = parseDate(o.today) || new Date(Date.UTC(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()));
      if (!b) return { error: "자녀 생년월일을 입력하세요." };
      function until(d) { return today <= d ? "가능 (" + fmt(d) + "까지)" : "기간 지남 (" + fmt(d) + "까지였음)"; }
      function later(a, c) { return a > c ? a : c; }
      var rows = [
        ["육아휴직 (만 8세 이하 또는 초2 이하)", until(later(dayBeforeBirthday(b, 9), endOfGrade(b, 2)))],
        ["육아돌봄시간 (8세 이하 또는 초2 이하)", until(later(dayBeforeBirthday(b, 9), endOfGrade(b, 2)))],
        ["육아기 근로시간 단축 (만 12세 이하 또는 초6 이하)", until(later(dayBeforeBirthday(b, 13), endOfGrade(b, 6)))],
        ["가족돌봄휴가 유급 대상 (미성년 자녀)", until(dayBeforeBirthday(b, 19))],
        ["가족수당 (20세 미만)", until(dayBeforeBirthday(b, 20))]
      ];
      if (o.mother) rows.splice(0, 0, ["수유시간 (생후 1년 미만, 여성직원)", until(dayBeforeBirthday(b, 1))]);
      return {
        rows: rows,
        notes: ["초등학교 학년은 정상 입학(태어난 해 + 7년 3월)을 가정했습니다. 조기·유예 입학이면 실제 학년으로 판단하세요.", "'8세 이하'(육아돌봄시간)는 만 나이로 계산했습니다. 담당부서 확인 전입니다."]
      };
    },
    // 가족돌봄휴가 유급 일수
    familyCare: function (o) {
      var n = Math.max(0, Math.floor(+o.children || 0));
      if (!n) return { error: "어린이집등에 다니거나 미성년인(또는 장애인인) 자녀 수를 입력하세요." };
      var paid = n + 1 + (o.disabledOrSingle ? 1 : 0);
      return {
        rows: [["연간 가족돌봄휴가", "10일 이내"], ["그중 유급 (자녀 돌봄)", Math.min(paid, 10) + "일" + (paid > 10 ? " (연간 한도 10일)" : "")], ["사용 단위", "유급은 시간 단위 가능, 무급은 일 단위"]],
        notes: ["유급은 자녀를 돌보기 위한 경우에만 해당합니다. 다른 가족 돌봄은 무급입니다."]
      };
    },
    // 가족수당 (배우자 + 자녀)
    allowance: function (o) {
      var n = Math.max(0, Math.floor(+o.children || 0)), sum = o.spouse ? 40000 : 0, parts = [];
      if (o.spouse) parts.push(["배우자", "40,000원"]);
      for (var i = 1; i <= n; i++) {
        var a = i === 1 ? 20000 : i === 2 ? 40000 : 110000;
        sum += a;
        parts.push([i + "번째 자녀", a.toLocaleString("ko-KR") + "원"]);
      }
      parts.push(["월 합계", sum.toLocaleString("ko-KR") + "원"]);
      return { rows: parts, notes: ["부모 등 다른 부양가족이 있으면 4인 한도 계산이 달라질 수 있습니다.", "부부가 모두 직원이면 한 명만 받습니다."] };
    }
  };

  var api = { normalize: normalize, content: content, expand: expand, CardIndex: CardIndex, decide: decide, ArticleIndex: ArticleIndex, snippet: snippet, calc: calc, thresholds: T, parseDate: parseDate, iso: iso };
  root.NaegyuEngine = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
