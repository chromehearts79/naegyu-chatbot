/* 내규챗봇 엔진: 문답 카드 검색, 되묻기 판단, 조문 검색, 계산기.
 * 브라우저에서는 NaegyuEngine 전역으로, node 에서는 require 로 쓴다. 외부 의존성 없음. */
(function (root) {
  "use strict";

  // ── 글자 정리와 일상어 → 규정어 보강 ──────────────────────────────
  // 일상어를 지우지 않고 규정어를 덧붙인다. 원래 표현도 계속 검색에 쓰인다.
  // [일상어, 덧붙일 규정어, (있으면) 함께 있어야 하는 말]
  // 나라·해외 도시 이름. '빈'(빈 칸), '인도'(물품 인도), '선전'처럼 일반 낱말과 같은 이름은 넣지 않는다
  var OVERSEAS_PLACES = ("미국 일본 중국 대만 홍콩 마카오 베트남 태국 필리핀 인도네시아 말레이시아 싱가포르 캄보디아 라오스 미얀마 몽골 네팔 " +
    "스리랑카 방글라데시 우즈베키스탄 카자흐스탄 러시아 영국 프랑스 독일 이탈리아 스페인 포르투갈 네덜란드 벨기에 스위스 오스트리아 체코 폴란드 헝가리 " +
    "스웨덴 노르웨이 덴마크 핀란드 그리스 튀르키예 터키 이스라엘 아랍에미리트 사우디 카타르 이집트 케냐 남아공 캐나다 멕시코 브라질 아르헨티나 칠레 페루 " +
    "호주 뉴질랜드 괌 사이판 하와이 뉴욕 워싱턴 로스앤젤레스 샌프란시스코 시카고 보스턴 시애틀 도쿄 오사카 후쿠오카 삿포로 베이징 상하이 광저우 " +
    "하노이 호찌민 다낭 방콕 마닐라 자카르타 발리 쿠알라룸푸르 런던 파리 프랑크푸르트 베를린 뮌헨 제네바 취리히 로마 밀라노 마드리드 바르셀로나 암스테르담 " +
    "브뤼셀 모스크바 두바이 시드니 멜버른 토론토 밴쿠버").split(" ").join("|");
  var SYNONYMS = [
    [/와이프|아내|부인|집사람|와입|신랑|남편/, "배우자"],
    [/아빠|남자|남성|남직원/, "배우자 남성직원"],
    [/엄마|여자|여성|여직원/, "여성직원"],
    [/부부|둘\s?다|같이|함께|남편도|아내도|와이프도/, "부모 모두", /아이|자녀|애기|아기|아들|딸|육아|돌봄|등원|하원|방학|어린이집|유치원|(^|\s)애($|\s|가|를|는|랑|도|의)/],
    [/쉬어도|쉬고|쉴\s?수|쉬어야|빠져도|빠질/, "휴가"],
    [/예정/, "출산예정일", /임신|임산|출산|태아|아기|뱃속|배 속|산모/],
    [/애기|아기|(^|\s)아가|신생아|갓난/, "자녀 유아"],
    [/아이|애들|자식|아들|딸|첫째|둘째|셋째|막내|(^|\s)애($|\s|가|를|는|랑|도|의)/, "자녀"],
    [/육휴/, "육아휴직"],
    [/산휴|산전후|출산\s?휴가/, "출산전후휴가"],
    [/배출|배우자\s?출산/, "배우자 출산전후휴가"],
    [/시험관|체외\s?수정|ivf|인공\s?수정|난임|배아\s?이식/, "난임치료 난임"],
    [/유축|모유|젖|수유/, "수유시간"],
    [/생리/, "보건휴가"],
    [/야근|초과\s?근무|연장\s?근[무로]|잔업|밤\s?늦게/, "시간외 근로 야간 초과근무"],
    [/주말|토요일|일요일|공휴일/, "휴일 토요일 공휴일"],
    [/월급|급여|봉급|임금/, "보수 유급 급여"],
    [/연차/, "연가"],
    [/단축\s?근무|덜\s?일|근무\s?시간\s?줄/, "근로시간 단축"],
    [/등원|하원|등교|하교/, "육아돌봄시간 출근 퇴근"],
    [/어린이집|유치원/, "어린이집등"],
    [/학교/, "어린이집등", /아이|자녀|애기|아기|아들|딸|육아|돌봄|등원|하원|방학|어린이집|유치원|(^|\s)애($|\s|가|를|는|랑|도|의)/],
    [/방학|휴원|휴교|휴업/, "방학 휴원 휴교"],
    [/노산|마흔|40살/, "40세"],
    [/쌍둥이|세쌍둥이|다둥이|다태아/, "둘 이상 다태아"],
    [/조산|위험\s?임신/, "위험 유산 조산"],
    [/고위험/, "위험 유산 조산", /임신|임산|출산|태아|아기|뱃속|배 속|산모/],
    [/입덧|임신\s?초기/, "임신 중"],
    [/힘들/, "임신 중", /임신|임산|출산|태아|아기|뱃속|배 속|산모/],
    [/막달/, "37주 이후"],
    [/계류|자연\s?유산|유산/, "유산 사산"],
    [/잃었/, "유산 사산", /임신|임산|출산|태아|아기|뱃속|배 속|산모/],
    [/낙태|중절/, "인공임신중절"],
    [/학부모|입학식|졸업식/, "공식 행사 상담"],
    [/상담|행사/, "공식 행사 상담", /아이|자녀|애기|아기|아들|딸|육아|돌봄|등원|하원|방학|어린이집|유치원|(^|\s)애($|\s|가|를|는|랑|도|의)/],
    [/예방\s?접종|병원|진료|아파|아프|독감|감기|수술/, "병원 진료 질병"],
    [/간병|간호|병간호/, "간호 돌봄 요양"],
    [/포인트|복지\s?카드/, "복지포인트"],
    [/수당/, "가족수당", /가족|부양|자녀|아이|배우자|부모/],
    [/경력|호봉|근속/, "근속년수 근속기간", /육아|출산|자녀|아이|임신/],
    [/평가|고과/, "평가"],
    [/해외|외국|출국|여행|미국/, "국외 출국"],
    [/축하금|장려금|지원금|선물/, "축하금", /아이|자녀|애기|아기|아들|딸|육아|돌봄|등원|하원|방학|어린이집|유치원|(^|\s)애($|\s|가|를|는|랑|도|의)/],
    [/보육|베이비\s?시터|돌보미/, "어린이집 보육"],
    [/산부인과|임신\s?검진|임산부\s?검진|정기\s?검진|산전\s?검사|정기\s?진료/, "정기건강진단 임산부"],
    // 복무(휴가) 분야
    [/반반차/, "반일연가 시간 단위"],
    [/반차|반일/, "반일연가"],
    [/몸이\s?안\s?좋|몸살|병결|입원|다쳐|다쳤|아파서\s?출근|아파서\s?쉬/, "병가 부상 진단서"],
    // 아파서 '오늘·하루' 쉬는 것은 병가, '1년·오래' 쉬는 것은 휴직
    [/오늘|내일|하루|당일|아침에/, "병가 하루", /몸이|아파|아프|몸살|열이|감기|독감|병원/],
    [/예비군|민방위/, "공가 병역 훈련 소집"],
    [/동원|훈련|소집/, "공가 병역 훈련 소집", /예비군|민방위|병역|군대|입영|공가/],
    [/헌혈/, "헌혈 공가"],
    [/건강\s?검진|종합\s?검진|재검/, "건강검진 공가"],
    [/투표|선거|배심/, "투표 공민권"],
    [/결혼|웨딩|신혼/, "결혼 경조사"],
    [/별세|장례|부고|조문|상을\s?당|모상|부친상|모친상|조모상|조부상|외조모|외조부|빙부|빙모/, "사망 경조사"],
    [/돌아가/, "사망 경조사", /부모|아버|어머|엄마|아빠|할머|할아|장인|장모|시어|시아|가족|형|누나|언니|오빠|동생|배우자|남편|아내|와이프|자녀|아들|딸/],
    [/장인|장모|시어머니|시아버지|시부모|처가댁|처갓집|시댁/, "사망 경조사 배우자의 부모"],
    [/할머니|할아버지|외할|조부모/, "조부모 외조부모"],
    [/(^|\s)(형|누나|언니|오빠|동생)($|\s|이|가|님|은|는|의|도|네|한테|랑)/, "형제자매"],
    [/태풍|홍수|폭우|폭설|지진|산불|화재|불이\s?났|침수|수해/, "재해 천재지변"],
    [/출근\s?못|출근\s?불가|길이\s?막|운행\s?중단|교통\s?통제|도로\s?통제/, "출근 불가능 교통차단 천재지변"],
    [/못\s?가|파업/, "출근 불가능 교통차단 천재지변", /출근|회사|사무실/],
    [/방송대|방통대|방송통신/, "방송통신대학교 수업휴가"],
    [/장기\s?근속|장기\s?재직|근속\s?휴가|\d+년\s?근속|근속\s?\d+년/, "장기재직휴가 근속"],
    [/연차\s?수당/, "연차수당 미사용 보상"],
    [/돈으로|정산|보상/, "연차수당 미사용 보상", /연가|연차|휴가|반차|병가|쉬/],
    [/결재|승인권자|전결|누가\s?승인/, "전결권자 결재 허가"],
    [/지각|조퇴|외출|일찍\s?퇴근|일찍\s?가/, "지각 조퇴 외출"],
    [/근무\s?시간|점심/, "근무시간"],
    [/몇\s?시/, "근무시간", /출근|퇴근|근무|일하|일해/],
    [/설날|설\s?연휴|추석|명절|연휴|대체\s?공휴일|임시\s?공휴일/, "공휴일 유급휴일"],
    [/이월|넘기|쌓아|저축/, "연가 저축", /연가|연차|휴가|반차|병가|쉬/],
    [/몰아서|길게|연속|2주|한\s?달|여름\s?휴가/, "연속 연가 10일"],
    [/안식|리프레시|재충전/, "리프레시 안식휴가"],
    [/촉진|사용\s?계획|쓰라고/, "사용 촉진"],
    [/당일|급하게|갑자기/, "긴급 당일 정오", /연가|연차|휴가|반차|병가|쉬/],
    [/결근|무단/, "결근"],
    [/출장비|여비|일비|숙박비|식비|교통비/, "여비 출장"],
    [/시외|지방|타\s?지역|근무지\s?외/, "근무지외 국내 여비", /출장|여비|비용|요금|운임|교통비|정산|숙박|일비/],
    [/시내|관내|근무지\s?내|같은\s?시|가까운/, "근무지내 출장비", /출장|여비|비용|요금|운임|교통비|정산|숙박|일비/],
    [/지하철|전철|버스|대중교통/, "운임 전철 교통비", /출장|여비|비용|요금|운임|교통비|정산|숙박|일비/],
    [/ktx|srt|기차|고속열차|열차/, "철도 고속열차 운임"],
    [/관용차|업무용\s?차|회사\s?차|공용차/, "업무용 차량"],
    [/부산|대구|광주|대전|울산|인천/, "광역시", /출장|여비|비용|요금|운임|교통비|정산|숙박|일비/],
    [/서울/, "서울특별시"],
    [/제주/, "제주특별자치도 광역시"],
    [/피해/, "피해 재해구호휴가", /재해|재난|태풍|홍수|폭우|폭설|지진|산불|화재|침수|수해/],
    [/다\s?쓰|다\s?썼|초과해|넘겨|넘게\s?쉬/, "초과 결근", /연가|연차|휴가|반차|병가|쉬/],
    [/출퇴근|출근\s?시간|퇴근\s?시간|늦게\s?출근|일찍\s?퇴근|시차/, "출근 퇴근 시각"],
    [/비행기|항공|좌석|비즈니스/, "항공운임 국외출장"],
    [/신청서|양식|서식/, "신청서 서식"],
    [/제왕\s?절개|분만|낳/, "출산"],
    // 평가단 시험에서 놓친 일상어
    [/챗\s?지피티|챗\s?gpt|chat\s?gpt|지피티|gpt|생성형|인공지능|에이아이|코파일럿|제미나이|클로드|뤼튼|(^|\s)ai($|\s)/, "생성형 인공지능 ai 활용"],
    [/근무\s?평정|근평|고과|인사\s?고과|평정/, "평가 근무성적 평가결과"],
    [/폭언|막말|욕설|갑질|따돌림|왕따|괴롭/, "직장 내 괴롭힘 신고 고충상담"],
    [/혜택|특전|우대|좋은\s?점/, "부상 포상 가점", /표창|상장|포상|수상/],
    [/날짜\s?(쓰|적|표기|형식)/, "날짜 표기 연월일 온점", /공문|문서|기안|작성/],
    [/투잡|부업|알바|겸업/, "겸직"],
    // 시험 질문 오답 분석(2026-10-26)에서 찾은 일상어. 시험 질문 문장이 아니라 직원이 흔히 쓰는 표현 묶음으로 적는다
    [/떨어져\s?(일|근무|앉|지내)|자리\s?(를\s?)?(옮기|바꾸|떨어)|분리\s?(해|시켜|조치)|안\s?마주치/, "괴롭힘 피해자 행위자 분리 근무 장소 변경"],
    [/몇\s?처|몇\s?팀|조직도|조직\s?구성|부서가\s?(몇|전부|모두)|팀이\s?몇|몇\s?개\s?부서/, "조직도 처 실 지사 팀"],
    [/몇\s?년|옮기|바뀌|순환|교체|다른\s?업무/, "회계직원 보직순환", /회계|출납|결산/],
    [/결혼식|결혼해|결혼하|장가|시집|웨딩/, "결혼 휴가 경조사휴가", /휴가|쉬|며칠|나와|날/],
    [new RegExp(OVERSEAS_PLACES), "국외 출장 여비 지역 등급", /출장|숙박|일비|식비|여비|항공/],
    [/발령|주재|해외\s?근무|해외\s?지사|파견\s?근무/, "주재원 주택 임차 지원", /집세|월세|집|숙소|주택|거처|전세/],
    [/복사|사본|출력|인쇄/, "정보공개 수수료 사본 비용", /얼마|비용|돈|수수료|장당|한\s?장/],
    [/헤어진|전\s?(남친|여친|애인|남자\s?친구|여자\s?친구)|따라다니|따라오|따라와|미행|스토킹|기다리고\s?있/, "스토킹 피해자 보호조치"],
    [/내년|다음\s?해|이어서|넘기|남은|못\s?쓴|남으면/, "예산 이월", /예산/],
    [/만들|제정|새로|개정|고치/, "내규 제정 개정 절차 확정", /(지침|세칙|내규).*(승인|확정|결재|절차|누가)|(승인|확정|결재|절차|누가).*(지침|세칙|내규)/],
    [/해외|국외|외국/, "국외출장 결과보고서", /보고|결과서/],
    [/출처|모르는|이상한|수상한|의심|피싱|스팸|해킹|악성/, "해킹메일 신고", /메일/],
    [/회계\s?법인|감사인|외부\s?감사/, "회계감사인선임위원회", /고르|선정|뽑|선임|위원/],
    [/누가\s?들어|위원은\s?누구|누구로\s?구성|구성원/, "구성", /위원회/],
    [/공익\s?침해/, "공익신고"],
    [/아꼈|아낀|절감|줄였/, "예산성과금", /보상|포상|성과금|얼마|상금|받/],
    [/예정가보다|예정\s?가격보다|낙찰|싸게\s?계약|차액/, "낙찰차액 예산성과금", /절감|성과금|포상|대상/],
    [/주\s?\d+\s?시간|시간제|단시간|파트\s?타임/, "단시간근무자 휴가", /연차|연가|휴가/],
    [/관용차|업무용\s?차|회사\s?차|공용\s?차/, "업무용차량 사용 운행일지", /쓰고|이용|사용|운행|반납|타고|나서/],
    [/해외|외국|미국|출국|따라\s?가/, "휴직 중 해외 출국", /휴직/],
    [/없애|지우|삭제|버리|폐기|파쇄/, "개인정보 파기", /개인정보|고객\s?정보/],
    [/보안\s?사고|유출\s?사고|랜섬/, "보안사고 발견 보고", /목격|발견|알게|누구|어디|알려|보고/],
    [/야한|음담|몸에\s?손|만지|추행/, "성희롱 고충상담창구 상담", /누구|어디|얘기|말해|상담|알려|신고/],
    [/결론|끝나고|끝난\s?뒤|종결|나서도/, "괴롭힘 사후 모니터링 재발", /괴롭힘|갑질/],
    [/정직|감봉|견책|강등/, "표창 대상 제외", /표창|포상|추천/],
    [/서명|사인|수령/, "수령확인서 자필서명", /상품권/],
    [/사전\s?컨설팅|컨설팅대로/, "적극행정 면책", /징계|책임|문제/],
    [/역할|하는\s?일|맡/, "관리부서 이행부서 감사부서 역할", /내부\s?통제/],
    [/누구(한테|에게|랑)|어디(에|로|다)/, "상담 신고 창구", /얘기|말해|말하|신고|상담|알려|보고|물어/],
    [/징계(까지는|는)?\s?(바라지|원하지)|처벌은?\s?원하지|조용히\s?해결|원만히|사과만/, "분리만 원하면 합의 당사자 간 해결"],
    [/고충/, "고충처리위원회 처리 결과 10일", /며칠|기한|언제|결과|답/]
  ];

  var SPOUSE_CUE = /배우자|와이프|아내|부인|집사람|와입|남편|신랑|아빠|남자|남성/;

  function normalize(s) {
    return String(s || "").normalize("NFC").toLowerCase().replace(/[^0-9a-z가-힣\s]/g, " ").replace(/\s+/g, " ").trim();
  }

  // 질문의 말끝과 군말. 뜻이 없는데 글자 수가 많아 점수를 끌고 다니므로 뺀다.
  var STOP_TOKENS = new Set(("어떻게 어떡해 어케 되나요 돼요 되요 될까요 되는지 되는 해요 하나요 할까요 하는지 있나요 있어요 있어 있음 있는 있는지 있을까요 " +
    "인가요 뭐예요 뭔가요 무엇 뭐 얼마 얼마나 몇 알려주세요 알려줘 궁금해요 궁금 싶어요 싶어 싶은데 가능한가요 가능 할 쓸 받을 수 " +
    "주세요 좀 혹시 제가 저는 저도 저 나 내가 나도 그 이 거 것 건가요 하면 되면 그냥 이거 어디 언제 왜 누가 맞나요 맞아요 해야 돼 되나 " +
    "하는데 인데 는데 있는데 같은데 요 네 음 대해 관련 경우 때 " +
    "오늘 내일 모레 지금 곧 이번주 다음주 이번달 다음달 지난주 지난달 올해 내년 작년 " +
    "싶 있 없 되 받 하 가 타 썼 됐 쓰 줄 드 쉴 가려 가야 하셔서 해서 했 됨 함 임 너무 정말 진짜 많이 " +
    "전 후 전에 후에 동안 이후 이전 개월 쉬어야 써야 해야 " +
    "할때 할 때 써도 해도 돼도 가도 받아도 되는지 몇번 몇개 몇년 법 방법 이야 이에요 예요 에요 쓰는 하는 되는").split(" "));
  // 말끝 → 조사 순서로 한 번씩 뗀다. 조사는 남는 글자가 2자 이상일 때만 뗀다("휴가"의 '가'는 그대로).
  var ENDINGS = /(했어요|했는데|해요|해야|하나요|합니다|이에요|예요|에요|인가요|나요|까요|어요|아요|돼요|되요|게요|는데|인데|이라서|이라|라서|이요|요|하고|하면|해서|이야|이냐|냐|지요|죠|래요|대요|려고)$/;
  var PARTICLES = /(에서|에게|한테|으로|이랑|부터는|이나|은|는|을|를|도|에|랑|로|나)$/;

  // '가', '이'는 낱말 끝 글자인 경우가 많아(휴가, 평가, 어린이) 따로 지킨다.
  var KEEP_GA_I = /(휴가|평가|단가|참가|국가|대가|추가|어린이)$/;

  // 붙여 쓴 '○○출장'은 '○○ 출장'으로 뗀다. 안 떼면 "시외출장"·"해외출장"의 가운데 '외출'이 지각·조퇴·외출에 걸린다.
  var SPLIT_HEADS = /(\S)(출장)/g;

  // 붙여 쓴 물음말("연차몇일이야", "써도돼요", "작성할때")을 앞 낱말과 떼어 놓는다. 떼어 낸 말은 군말로 빠진다.
  var QWORDS = /([가-힣])(몇\s?일|며칠|몇\s?번|몇\s?개|몇\s?년|얼마|언제|어디|어떻게|어떡|누구|누가|무엇|뭐|되나|돼|되요|할\s?때|인가|일까|해도|하면|해야)/g;
  var QTAIL = /([가-힣])(이야|이에요|예요|법|방법)(?=\s|$)/g;
  // 질문 속 날짜(2023.3.2, 2026년, 3월 2일)는 검색을 흐린다. 날짜 계산은 계산기 칸에서 한다.
  var DATES = /\d{2,4}\s?[.\-\/년]\s?\d{1,2}\s?[.\-\/월]\s?\d{1,2}\s?일?|\d{4}\s?년|\d{1,2}\s?월\s?\d{1,2}\s?일/g;
  // 국내 지명(시·도, 시·군). 출장 질문에서 지명은 목적지일 뿐 주제가 아니다. 답 카드 어디에도 낱말로 나오지 않는 지명이
  // 검색에 남으면 '모르는 주제'로 보고 답을 막거나('세종시'), 다른 낱말 글자에 걸린다('수원' ⊂ '연수원').
  var PLACE_NAMES = ("서울 부산 대구 인천 광주 대전 울산 세종 제주 경기 강원 충북 충남 전북 전남 경북 경남 충청북 충청남 전라북 전라남 경상북 경상남 " +
    "수원 성남 부천 안산 안양 평택 의정부 시흥 파주 김포 하남 안성 의왕 군포 남양주 과천 여주 포천 동두천 가평 양평 연천 " +
    "춘천 원주 강릉 속초 삼척 태백 홍천 횡성 평창 정선 철원 화천 양구 양양 " +
    "청주 충주 제천 옥천 괴산 진천 증평 천안 아산 서산 논산 당진 보령 계룡 태안 서천 금산 청양 " +
    "군산 익산 정읍 남원 김제 무주 임실 순창 고창 부안 목포 여수 순천 나주 광양 담양 곡성 구례 고흥 장흥 강진 해남 무안 함평 완도 " +
    "포항 경주 김천 안동 영주 영천 문경 경산 의성 청송 영덕 청도 칠곡 예천 봉화 울진 울릉 " +
    "창원 진주 통영 사천 김해 밀양 거제 의령 함안 창녕 남해 하동 산청 함양 합천 서귀포").split(" ");
  // 지명과 글자가 같은 일반 낱말(예산 = 예산군, 상주 = 상주 인원, 전주 = 지난주 …)은 뒤에 '시·군'이 붙을 때만 지명으로 본다
  var PLACE_SUFFIXED = ("예산 상주 양주 진도 영광 전주 부여 음성 고령 보은 신안 장수 완주 거창 인제 양산 오산 이천 용인 구미 " +
    "장성 고성 보성 광명 공주 동해 구리 성주 영동 단양 홍성 화순 영암 영월 군위 고양 화성").split(" ");
  var PLACE_NEEDS_SUFFIX = new Set(PLACE_SUFFIXED);
  // 앞에 한글이 붙어 있으면 지명이 아니다(연수원 ⊄ 수원). 뒤에 붙은 행정 단위와 조사도 함께 뺀다.
  var PLACE_RE = new RegExp("(^|[^가-힣])(" + PLACE_NAMES.concat(PLACE_SUFFIXED).sort(function (a, b) { return b.length - a.length; }).join("|") +
    ")(특별자치시|특별자치도|특별시|광역시|시|군|도)?(으로|에서|에게|까지|부터|로|에|의|은|는|이|가|와|과|랑)?", "g");
  // 출장 이야기일 때만 지명을 맥락으로 본다. 그 밖에는("세종시 이주 지원금") 지금처럼 '준비된 답에서 찾지 못함'으로 정직하게 답한다
  var TRAVEL = /출장|여비|숙박|일비|식비|운임|교통비|ktx|기차|열차|버스|비행기|항공|관용차|자가용|파견|부임/i;
  // 'N박M일' 일정: 종합 안내 카드("1박 2일 출장")를 찾는 데 쓰이므로 검색에는 남기고, '모르는 낱말' 판정에서만 뺀다
  var STAY_TOKEN = /^\d+박(\d+일)?$/;
  // 창구를 묻는 질문("누구한테 얘기해요", "어디에 신고해요")과 창구 카드 제목(상담·신고·창구·접수)
  var ASK_WHERE = /(누구|어디)\s?(한테|에게|에|로|다|랑)?\s?(얘기|말해|말하|신고|상담|알려|보고|물어|연락)/;
  var CHANNEL_TITLE = /상담|신고|창구|접수/;

  function content(s) {
    s = normalize(String(s || "").replace(DATES, " ")).replace(/몇\s?일/g, "며칠").replace(QWORDS, "$1 $2").replace(QTAIL, "$1 $2")
      .replace(/([가-힣])(려고)(하|해)/g, "$1$2 $3");
    return s.replace(SPLIT_HEADS, "$1 $2").split(" ").map(function (t) {
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
    var n = normalize(s).replace(SPLIT_HEADS, "$1 $2"), extra = [];
    // 세 번째 칸이 있으면 그 말도 함께 있을 때만 덧붙인다("이월"은 연가 이야기일 때만 연가 저축).
    for (var i = 0; i < SYNONYMS.length; i++) {
      var e = SYNONYMS[i];
      if (e[0].test(n) && (!e[2] || e[2].test(n))) extra.push(e[1]);
    }
    return extra.join(" ");
  }

  // 낱말 하나가 불러오는 규정어(문맥 조건은 질문 전체로 본다)
  function synonymsFor(word, whole) {
    var n = normalize(whole), w = normalize(word), extra = [];
    for (var i = 0; i < SYNONYMS.length; i++) {
      var e = SYNONYMS[i];
      if (e[0].test(w) && (!e[2] || e[2].test(n))) extra.push(e[1]);
    }
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
    // 글자 조각 → 그 조각이 있는 문서 번호. 질문과 한 조각도 겹치지 않는 문서는 0점이라 건너뛴다(카드가 많아도 빠르게).
    var postings = new Map();
    docs.forEach(function (d, i) {
      d.vec = vectorize(d.counts, idf);
      d.mass = 0;
      d.counts.forEach(function (_, g) {
        d.mass += idf.get(g);
        var p = postings.get(g);
        if (p) p.push(i); else postings.set(g, [i]);
      });
    });
    this.docs = docs;
    this.postings = postings;

    // 카드 전체 글(제목·요약·질문·핵심어·답변·근거·규정명)의 글자 조각. 질문 단어가 카드 어딘가에 다 들어 있는지 본다.
    // 조각마다 '몇 군데에 나오나'를 센다. 시험에서 질문 하나를 뺄 때 그 질문에만 있던 조각을 지우려고.
    var cardGrams = new Map(), cardPostings = new Map(), docsOf = new Map();
    docs.forEach(function (d) { var l = docsOf.get(d.card); if (l) l.push(d); else docsOf.set(d.card, [d]); });
    cards.forEach(function (c) {
      var parts = [c.title, c.summary, ruleOfCard(c)].concat(c.questions, c.keywords || [], c.answer || [],
        (c.facts || []).map(function (f) { return f.label + " " + f.value; }));
      var g = new Map();
      parts.forEach(function (t) { bigrams(content(t || "")).forEach(function (_, k) { g.set(k, (g.get(k) || 0) + 1); }); });
      cardGrams.set(c.id, g);
      g.forEach(function (_, k) { var p = cardPostings.get(k); if (p) p.push(c.id); else cardPostings.set(k, [c.id]); });
    });
    this.cardGrams = cardGrams;
    this.cardPostings = cardPostings;
    this.docsOf = docsOf;
    // 카드 단위 희귀도: 한 카드의 질문 여러 개에 반복되는 낱말이 흔한 낱말로 잘못 깎이지 않게 카드를 한 덩어리로 센다.
    this.cardIdf = idfOf(cardGrams);
    var titleGrams = new Set();
    cards.forEach(function (c) { bigrams(content(c.title)).forEach(function (_, k) { titleGrams.add(k); }); });
    this.titleGrams = titleGrams;
    // 카드 이름(괄호 앞, 3글자 이상)이 질문에 그대로 있으면 그 카드를 조금 올린다("가족수당", "징계 감경", "결혼 휴가")
    var titleHeads = new Map();
    cards.forEach(function (c) {
      var head = normalize(String(c.title).split(/[(（]/)[0]).replace(/\s+/g, "");
      if (head.length >= 3) (titleHeads.get(head) || titleHeads.set(head, new Set()).get(head)).add(c.id);
    });
    this.titleHeads = titleHeads;
    // 카드 글에 낱말로 나오는 지명(서울·부산·제주·김포 …)은 지사·노선·가산처럼 주제일 수 있어 검색에 그대로 쓴다
    var known = new Set();
    cards.forEach(function (c) {
      [c.title, c.summary].concat(c.questions, c.keywords || [], c.answer || [], (c.facts || []).map(function (f) { return f.label + " " + f.value + " " + (f.quote || ""); }))
        .join(" ").replace(PLACE_RE, function (m, pre, name) { known.add(name); return m; });
    });
    this.knownPlaces = known;

    // 규정 이름의 특징 낱말(예: 법인카드, 행동강령, 이해충돌). 질문에 나오면 그 규정 카드를 조금 올린다.
    var ruleOf = new Map(), nameTokens = new Map();
    cards.forEach(function (c) { ruleOf.set(c.id, ruleOfCard(c)); });
    this.ruleOf = ruleOf;
    var names = Array.from(new Set(ruleOf.values())).filter(Boolean);
    names.forEach(function (n) {
      ruleNameTokens(n).forEach(function (t) { nameTokens.set(t, (nameTokens.get(t) || new Set()).add(n)); });
    });
    this.ruleTokens = [];
    var self = this;
    nameTokens.forEach(function (rs, t) { if (rs.size <= 2) self.ruleTokens.push({ token: t, rules: rs }); });
  }

  var RULE_SUFFIX = /(운영세칙|운영지침|운영규정|세부지침|처리세칙|사용지침|관리세칙|관리규정|세칙|지침|규정)$/;
  var RULE_GENERIC = new Set("관리 및 사용 처리 운영 업무 설치 등 이행 추진 제도 구매 신고 보호 신고자 내 직원 임직원 위원회".split(" "));
  function ruleNameTokens(name) {
    return normalize(name).split(" ").map(function (t) { return t.replace(RULE_SUFFIX, ""); })
      .filter(function (t) { return t.length >= 2 && !RULE_GENERIC.has(t); });
  }
  // 카드의 규정: rule 필드, 없으면 가장 많이 인용한 규정
  function ruleOfCard(c) {
    if (c.rule) return c.rule;
    var count = {};
    (c.facts || []).forEach(function (f) { var m = /^(.+?) (제\d|별표|부칙)/.exec(f.cite); if (m) count[m[1]] = (count[m[1]] || 0) + 1; });
    return Object.keys(count).sort(function (a, b) { return count[b] - count[a]; })[0] || "";
  }

  // 질문 글자 묶음. 직원이 쓴 말은 무게 1, 덧붙인 규정어는 무게 0.5.
  CardIndex.prototype.query = function (text) {
    var own = bigrams(content(text)), syn = bigrams(normalize(synonymsOf(text))), w = new Map(), synOnly = new Set(), self = this;
    // 한 글자 낱말("못", "쓴", "돈")은 뜻이 흐린 경우가 많아 무게를 낮춘다.
    own.forEach(function (_, g) { w.set(g, g.length === 1 ? T.ONE : 1); });
    syn.forEach(function (_, g) { if (!w.has(g)) { w.set(g, 0.5); synOnly.add(g); } });
    // 포괄도의 분모는 직원이 쓴 말만. 덧붙인 규정어는 맞으면 더해 주고, 안 맞아도 깎지 않는다.
    var total = 0;
    own.forEach(function (_, g) { total += w.get(g) * (self.idf.get(g) || self.unseenIdf); });
    var counts = new Map(own);
    syn.forEach(function (c, g) { counts.set(g, (counts.get(g) || 0) + c); });
    // 분야 적합도: 직원이 쓴 글자 중 카드에 나오는 글자의 비중. 알아들은 규정어는 '아는 말'로 더한다.
    var seen = 0, all = 0;
    own.forEach(function (_, g) { var v = self.idf.get(g); all += v || self.unseenIdf; if (v) seen += v; });
    syn.forEach(function (_, g) { var v = self.idf.get(g) || 0; seen += 0.5 * v; all += 0.5 * v; });
    return { weights: w, synOnly: synOnly, total: total || 1, vec: vectorize(counts, this.idf), domain: all ? seen / all : 0, spouse: SPOUSE_CUE.test(normalize(text)) };
  };

  // 포괄도: 질문 글자 중 has(조각)이 참인 것의 무게 합 / 질문 전체 무게. 덧붙인 규정어로 채운 몫은 전체의 SYN 까지만.
  function coverage(q, idf, unseen, has) {
    var own = 0, syn = 0, total = 0;
    q.weights.forEach(function (wt, g) {
      var v = wt * (idf.get(g) || unseen);
      if (!q.synOnly.has(g)) total += v;
      if (!has(g)) return;
      if (q.synOnly.has(g)) syn += v; else own += v;
    });
    return total ? Math.min(1, (own + Math.min(syn, T.SYN * total)) / total) : 0;
  }
  function idfOf(groups) {
    var df = new Map(), n = 0, out = new Map();
    groups.forEach(function (g) { n++; g.forEach(function (_, k) { df.set(k, (df.get(k) || 0) + 1); }); });
    df.forEach(function (c, k) { out.set(k, Math.log((n + 1) / (c + 0.5))); });
    return { idf: out, unseen: Math.log((n + 1) / 2) };
  }

  // 문서 점수 = 포괄도(질문 글자가 문서에 얼마나 들어 있나) 0.5 + 정밀도(문서 글자가 질문에 얼마나 들어 있나) 0.25
  //           + 코사인 유사도 0.25. 정밀도는 짧은 질문이 여러 카드에 똑같이 걸릴 때 더 딱 맞는 쪽을 고른다.
  // skip(doc) 이 참인 문서는 빼고 점수를 낸다. 시험에서 질문 자신을 빼는 데 쓴다.
  // 검색 전에, 출장 질문이면 카드에 없는 지명('세종시', '춘천')을 뺀다. 지명은 계산기 칸이 원래 질문에서 읽는다.
  // 빼고 남는 말이 없으면(지명만 물음) 원래 질문 그대로.
  CardIndex.prototype.clean = function (query) {
    var t = String(query || ""), known = this.knownPlaces, s = t;
    if (TRAVEL.test(s)) s = s.replace(PLACE_RE, function (m, pre, name, suf) {
      if (known.has(name) || (PLACE_NEEDS_SUFFIX.has(name) && !/^(시|군|특별자치시|광역시)$/.test(suf || ""))) return m;
      return pre + " ";
    });
    return content(s) ? s : t;
  };
  CardIndex.prototype.score = function (query, skip) {
    query = this.clean(query);
    var q = this.query(query), best = new Map(), idf = this.idf, unseen = this.unseenIdf, docs = this.docs, postings = this.postings;
    var cand = new Set();
    q.weights.forEach(function (_, g) { (postings.get(g) || []).forEach(function (i) { cand.add(i); }); });
    var self = this, flat = normalize(query).replace(/\s+/g, ""), boosted = new Set();
    // 규정 이름 낱말이 통째로, 또는 4글자 이상 이어진 부분이 질문에 있으면("추천위원회" ⊂ "임원추천위원회") 그 규정을 올린다.
    this.ruleTokens.forEach(function (rt) {
      var t = rt.token, hit = flat.indexOf(t) >= 0;
      for (var k = 0; !hit && t.length > 4 && k + 4 <= t.length; k++) hit = flat.indexOf(t.slice(k, k + 4)) >= 0;
      if (hit) rt.rules.forEach(function (r) { boosted.add(r); });
    });
    q.rules = boosted;
    var named = new Set(), askWhere = ASK_WHERE.test(normalize(query));
    this.titleHeads.forEach(function (ids, head) { if (flat.indexOf(head) >= 0) ids.forEach(function (id) { named.add(id); }); });
    cand.forEach(function (i) {
      var d = docs[i];
      if (skip && skip(d)) return;
      var back = 0;
      q.weights.forEach(function (wt, g) { if (d.counts.has(g)) back += idf.get(g) || 0; });
      var cov = coverage(q, idf, unseen, function (g) { return d.counts.has(g); });
      var s = (0.5 * cov + 0.25 * (d.mass ? Math.min(1, back / d.mass) : 0) + 0.25 * cosine(q.vec, d.vec)) * d.weight;
      if (s > (best.get(d.card) || 0)) best.set(d.card, s);
    });
    // 카드 점수 = 가장 잘 맞는 문서 점수 × WDOC + 카드 전체 글의 포괄도 × WCARD
    var cardCand = new Set(best.keys()), cardGrams = this.cardGrams, ci = this.cardIdf;
    q.weights.forEach(function (_, g) { (self.cardPostings.get(g) || []).forEach(function (id) { cardCand.add(id); }); });
    cardCand.forEach(function (id) {
      var grams = cardGrams.get(id), gone = skip ? self.docsOf.get(id).filter(skip) : [];
      var cov = coverage(q, ci.idf, ci.unseen, function (g) {
        var n = grams.get(g) || 0;
        gone.forEach(function (d) { if (d.counts.has(g)) n--; });
        return n > 0;
      });
      best.set(id, T.WDOC * (best.get(id) || 0) + T.WCARD * cov);
    });
    // 누구의 일인지 단서: 배우자 카드는 배우자 단서가 없으면, 본인 카드는 배우자 단서가 있으면 깎는다.
    // 질문에 규정 이름이 나오면 그 규정 카드를 1.15배.
    var byId = this.byId, tg = this.titleGrams;
    var nTopical = content(query).split(" ").filter(function (t) {
      if (t.length < 2) return false;
      var g = bigrams(t), n = 0; g.forEach(function (_, k) { if (tg.has(k)) n++; }); return n > 0 && n * 2 >= g.size;
    }).length;
    best.forEach(function (s, id) {
      var cue = byId.get(id).cue;
      if ((cue === "spouse" && !q.spouse) || (cue === "self" && q.spouse)) s *= 0.8;
      // 임원·주재원·단시간 근로자처럼 특정 대상용 카드는, 질문에 그 대상이 없으면 일반 직원용 카드보다 뒤로
      // 여러 규정 종합 카드는 조건이 여러 개인 긴 질문용이다. 짧은 질문에서는 단일 카드보다 조금 뒤로.
      if (byId.get(id).rule === "여러 규정 종합" && nTopical < 4) s *= T.COMBO;
      // 개요 카드는 규정 전체 글을 담아 웬만한 질문에 다 걸리므로, 규정 이름을 대며 물은 게 아니면 조금 깎는다
      if (byId.get(id).overview && !(boosted.size && boosted.has(self.ruleOf.get(id)))) s *= T.OVERVIEW;
      var qual = QUALIFIER.exec(byId.get(id).title);
      if (qual && flat.indexOf(qual[0].replace(/\s/g, "")) < 0) s *= T.QUAL;
      if (boosted.size && boosted.has(self.ruleOf.get(id))) s *= 1.15;
      if (named.has(id)) s *= T.TITLE;
      if (askWhere && CHANNEL_TITLE.test(byId.get(id).title)) s *= T.CHANNEL;
      // '내규에 없음' 안내 카드는 관련 제도를 두루 적어 웬만한 질문에 걸린다. 질문이 다른 카드 이름(가족수당 등)을 직접 대면 그 카드를 앞에
      else if (named.size && byId.get(id).kind === "outside") s *= T.OUTSIDE;
      best.set(id, s);
    });
    this.lastQuery = q;
    var out = [];
    best.forEach(function (s, id) {
      var c = byId.get(id), item = { id: id, score: s };
      if (c.rule === "여러 규정 종합") item.rel = c.related || [];  // 종합 카드가 묶은 단일 카드(서로 경쟁 후보로 보지 않는다)
      out.push(item);
    });
    out.sort(function (a, b) { return b.score - a.score; });
    // 상위 후보마다 질문의 핵심 낱말 중 카드 어디에도 없는 것(miss)을 적는다.
    // "챗지피티 써도 돼?"에 원고료 카드가 1등을 해도 '챗지피티'가 빠져 있으면 바로 답하지 않게 하려는 것.
    var toks = content(query).split(" ").filter(function (t) { return t.length >= 2 && !MISS_IGNORE.has(t) && !VERBY.test(t) && !STAY_TOKEN.test(t); });
    var cidf = this.cardIdf, wOf = function (t) { var w = 0; bigrams(t).forEach(function (_, k) { w += cidf.idf.get(k) || cidf.unseen; }); return w; };
    var wAll = toks.reduce(function (a, t) { return a + wOf(t); }, 0) || 1;
    var unknown = function (t) { var g = bigrams(t), n = 0; g.forEach(function (_, k) { if (!cidf.idf.has(k)) n++; }); return n * 2 >= g.size; };
    out.slice(0, 10).forEach(function (r) {
      var grams = cardGrams.get(r.id);
      var has = function (g) { var n = 0; g.forEach(function (_, k) { if (grams.has(k)) n++; }); return n > 0 && n * 2 >= g.size; };
      r.miss = toks.filter(function (t) {
        if (has(bigrams(t))) return false;
        var sx = synonymsFor(t, query);
        return !(sx && has(bigrams(normalize(sx))));
      });
      // 빠진 낱말이 질문에서 차지하는 무게(드문 낱말일수록 무겁다)
      r.missShare = r.miss.reduce(function (a, t) { return a + wOf(t); }, 0) / wAll;
      // 카드 1천여 장 어디에도 없는 3글자 이상 명사(예: '응시료')가 빠졌으면 무게와 관계없이 '빠짐'으로 본다
      if (r.miss.some(function (t) { return t.length >= 3 && unknown(t); })) r.missShare = Math.max(r.missShare, 1);
      // 빠진 낱말 중 카드 제목에 쓰이는 '주제어'(정직, 서명, 분실 …). 다른 후보가 이 말을 갖고 있으면 1위만으로는 질문을 다 덮지 못한다
      var tg = self.titleGrams;
      r.tmiss = r.miss.filter(function (t) { var g = bigrams(t), n = 0; g.forEach(function (_, k) { if (tg.has(k)) n++; }); return n > 0 && n * 2 >= g.size; });
    });
    return out;
  };
  // 여러 가지를 한 번에 묻는 질문("복직하면 승진 소요기간·연차·성과급은?")을 나눠 답하기 위한 계획.
  // 1위 카드가 덮지 못한 핵심 낱말이 질문의 SPLIT 이상이면, 그 낱말을 가장 잘 덮는 다른 후보를 차례로 고른다(최대 3장).
  CardIndex.prototype.plan = function (query, ranked) {
    query = this.clean(query);
    // 나누는 기준은 '주제어'만: 카드 제목에 나오는 낱말(얼마야·나오면 같은 군말은 빠진다)
    var tg = this.titleGrams;
    var topical = function (t) { var g = bigrams(t), n = 0; g.forEach(function (_, k) { if (tg.has(k)) n++; }); return n * 2 >= g.size && n > 0; };
    var toks = content(query).split(" ").filter(function (t) { return t.length >= 2 && !MISS_IGNORE.has(t) && topical(t); });
    if (toks.length < 3 || !ranked.length) return [];
    var cardGrams = this.cardGrams, cidf = this.cardIdf;
    var wOf = function (t) { var w = 0; bigrams(t).forEach(function (_, k) { w += cidf.idf.get(k) || cidf.unseen; }); return w; };
    var covers = function (id) {
      var grams = cardGrams.get(id);
      return toks.filter(function (t) {
        var g = bigrams(t), n = 0; g.forEach(function (_, k) { if (grams.has(k)) n++; });
        if (n > 0 && n * 2 >= g.size) return true;
        var sx = synonymsFor(t, query); if (!sx) return false;
        var sg = bigrams(normalize(sx)), m = 0; sg.forEach(function (_, k) { if (grams.has(k)) m++; });
        return m * 2 >= sg.size;
      });
    };
    var total = toks.reduce(function (a, t) { return a + wOf(t); }, 0) || 1;
    var pool = ranked.slice(0, 12).filter(function (r) { return r.score >= Math.max(T.LO, ranked[0].score * 0.6); });
    var picked = [], left = new Set(toks);
    for (var round = 0; round < 3 && pool.length; round++) {
      var best = null;
      pool.forEach(function (r) {
        if (picked.some(function (p) { return p.id === r.id; })) return;
        var cov = covers(r.id).filter(function (t) { return left.has(t); });
        var gain = cov.reduce(function (a, t) { return a + wOf(t); }, 0) / total;
        // 처음은 1위 카드, 그다음은 남은 낱말을 가장 많이 덮는 카드(점수가 높으면 조금 더 쳐준다)
        var val = round === 0 ? (r === pool[0] ? 1 : -1) : gain + 0.1 * r.score;
        if (cov.length && (!best || val > best.val)) best = { id: r.id, cov: cov, gain: gain, val: val };
      });
      if (!best || (round > 0 && best.gain < T.SPLIT)) break;
      picked.push({ id: best.id, words: best.cov });
      best.cov.forEach(function (t) { left.delete(t); });
    }
    return picked.length >= 2 ? picked : [];
  };

  var QUALIFIER = /임원|주재원|해외사무소|파견|단시간|시간선택제|전임직|전문직|금융상담|상담직원|기간제|청년인턴|비상임|감사인|노동이사|외부위원/;
  // 질문에 흔히 붙지만 카드에 없어도 되는 말
  // "옮겨도", "똑같", "후랑"처럼 동사·형용사 활용형이나 조사가 붙은 말은 '빠진 핵심어'로 치지 않는다
  var VERBY = /(어|아|여|겨|워|와|고|면|서|도|게|지|는|던|됨|함|같|싶|해|돼|되|랑|며|니|까|요|죠|임|음)$/;
  var MISS_IGNORE = new Set("회사 직원 규정 내규 우리 금융원 기관 규정상 관련 문의 질문 혹시 제가 저희 지금 요즘 경우 상황 문제 사람 내용 처리".split(" "));

  var T = { HI: 0.45, LO: 0.24, GAP: 0.12, NEAR: 0.80, DOMAIN: 0.30, WDOC: 0.4, WCARD: 0.6, ONE: 0.3, SYN: 0.5, LEAD: 0.45, MISS: 0.5, QUAL: 0.85, OVERVIEW: 0.9, SPLIT: 0.2, COMBO: 0.85, TITLE: 1.1, COVER: 0.5, OUTSIDE: 0.8, CHANNEL: 1.15 };

  // 점수로 답할지, 되물을지, 조문 검색으로 넘길지 정한다.
  // 질문 글자 대부분이 카드에 없는 말이면(분야 밖) 조문 검색으로 넘긴다.
  // "출산", "아기"처럼 한 단어뿐인 질문은 점수가 높아도 되묻는다.
  // 종합 카드와 그 카드가 묶은 단일 카드는 같은 답의 다른 모양이라 서로 경쟁하지 않는 것으로 본다
  function family(a, b) { return !!((a.rel && a.rel.indexOf(b.id) >= 0) || (b.rel && b.rel.indexOf(a.id) >= 0)); }
  function decide(ranked, queryText, q) {
    var top = ranked[0], second = ranked.slice(1).filter(function (r) { return !family(top, r); })[0] || { score: 0 };
    if (!top || top.score < T.LO) return { mode: "fallback" };
    if (q && q.domain < T.DOMAIN) return { mode: "fallback", offDomain: true, ids: ranked.slice(0, 2).map(function (r) { return r.id; }) };
    var c = queryText === undefined ? null : content(queryText);
    if (c !== null && c.indexOf(" ") < 0 && c.replace(/\s/g, "").length <= 4 && top.score - second.score < 0.2) {
      var cands = ranked.filter(function (r) { return r.score >= T.LO; }).slice(0, 4);
      if (cands.length > 1) return { mode: "ask", ids: cands.map(function (r) { return r.id; }), vague: true };
    }
    var near = ranked.filter(function (r) { return r === top || (r.score >= Math.max(T.LO, top.score * T.NEAR) && !family(top, r)); }).slice(0, 4);
    var miss = (top.missShare || 0) >= T.MISS ? top.miss : [];
    // 1위 카드에 없는 주제어를 가까운 다른 후보가 갖고 있으면("정직 1년 지났는데 표창" → 표창 절차 카드엔 '정직'이 없고 표창 제외 카드엔 있음)
    // 바로 답하지 않고 1위를 펼친 채 그 후보들을 함께 보여 준다
    if (!miss.length && (top.tmiss || []).length) {
      var cover = ranked.slice(1, 10).filter(function (r) {
        return r.miss && r.score >= top.score * T.COVER && !family(top, r) && top.tmiss.some(function (t) { return r.miss.indexOf(t) < 0; });
      }).slice(0, 2);
      if (cover.length) {
        // 1위, 빠진 주제어를 가진 후보, 그다음 1위와 점수가 비슷한 후보 순(4개까지)
        var ids = [top.id];
        cover.concat(near).forEach(function (r) { if (ids.indexOf(r.id) < 0) ids.push(r.id); });
        return { mode: "ask", ids: ids.slice(0, 4), lead: top.score >= T.LEAD, gap: top.tmiss };
      }
    }
    if (!miss.length && top.score >= T.HI && (top.score - second.score >= T.GAP || near.length === 1)) {
      return { mode: "answer", id: top.id, score: top.score, alts: ranked.slice(1, 4).filter(function (r) { return r.score >= T.LO; }).map(function (r) { return r.id; }) };
    }
    // 질문의 핵심 낱말이 1위 카드에 없으면: 후보를 넓게 보여 주고 1위 답을 미리 펼치지 않는다
    if (miss.length) {
      // 1위는 그대로 두고, 그다음 자리에 빠진 낱말을 가진 카드(10위 안)를 넣는다("못 쓴 예산을 내년에" → '예산'이 있는 예산 이월 카드)
      var covering = ranked.slice(1, 10).filter(function (r) { return r.miss && r.score >= T.LO && miss.some(function (t) { return r.miss.indexOf(t) < 0; }); }).slice(0, 2);
      var wide = [top].concat(covering, ranked.filter(function (r) { return r !== top && r.score >= T.LO && covering.indexOf(r) < 0; })).slice(0, 4);
      if (wide.length > 1) return { mode: "ask", ids: wide.map(function (r) { return r.id; }), lead: false, missing: miss };
      return { mode: "answer", id: top.id, score: top.score, soft: true, alts: [], missing: miss };
    }
    if (near.length === 1) return { mode: "answer", id: top.id, score: top.score, soft: true, alts: [] };
    return { mode: "ask", ids: near.map(function (r) { return r.id; }), lead: top.score >= T.LEAD };
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

  // 미리보기용 글자만: 별표의 표 태그(<td> 등)와 마크다운 표 칸막이(| --- |)를 빼고 띄어쓰기를 하나로
  function plainText(text) {
    return String(text || "").replace(/<[^>]+>/g, " ").replace(/\|?\s*:?-{3,}:?\s*(?=\|)/g, " ").replace(/\|/g, " ").replace(/\s+/g, " ").trim();
  }

  // 검색어 글자가 가장 많이 몰린 구간을 미리보기로 잘라낸다.
  function snippet(text, query, width) {
    width = width || 140;
    var q = bigrams(normalize(query)), flat = plainText(text), best = 0, bestAt = 0;
    for (var i = 0; i < flat.length; i += 10) {
      var win = flat.slice(i, i + width), s = 0;
      q.forEach(function (_, g) { if (win.indexOf(g) >= 0) s++; });
      if (s > best) { best = s; bestAt = i; }
    }
    var out = flat.slice(bestAt, bestAt + width);
    return (bestAt > 0 ? "…" : "") + out + (bestAt + width < flat.length ? "…" : "");
  }

  // ── 내규나침반: 낱말이 어느 내규 어디에 나오는지 ─────────────────────
  // 글자 그대로 찾기는 Ctrl+F 와 같아 하나도 빠뜨리지 않는다(띄어쓰기·표 태그·가운뎃점 차이만 무시).
  // 원문에 없는 말이면 규정어 짝(SYNONYMS)과 그 말을 묻는 답 카드가 가리키는 조문으로 비슷한 곳을 찾는다(참고용).
  var DOTS = /[·‧ㆍ∙･・]/g;
  function flatText(s) { return String(s || "").normalize("NFC").replace(/<[^>]+>/g, "").replace(/\s+/g, "").replace(DOTS, "·"); }
  function countIn(hay, needle) { var n = 0, i = hay.indexOf(needle); while (i >= 0) { n++; i = hay.indexOf(needle, i + needle.length); } return n; }
  // 낱말 글자 사이에 띄어쓰기가 끼어도 맞는 정규식(원문 표시용). 긴 낱말을 먼저 맞춘다("반일연가"를 "연가"보다 먼저).
  function wordRe(words) {
    var src = words.map(flatText).filter(Boolean).sort(function (a, b) { return b.length - a.length; }).map(function (w) {
      return w.split("").map(function (ch) { return ch === "·" ? "[·‧ㆍ∙･・]" : ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("\\s*");
    });
    return new RegExp(src.join("|") || "(?!)", "g");
  }
  // 미리보기: 처음 나오는 낱말과 그 앞뒤 width 글자
  function excerpt(text, words, width) {
    width = width || 40;
    var t = plainText(text), m = wordRe(words).exec(t);
    if (!m) return { pre: "", hit: "", post: t.slice(0, width * 2) + (t.length > width * 2 ? "…" : "") };
    var a = Math.max(0, m.index - width), b = m.index + m[0].length;
    return { pre: (a > 0 ? "…" : "") + t.slice(a, m.index), hit: m[0], post: t.slice(b, b + width) + (b + width < t.length ? "…" : "") };
  }

  function Compass(rules, index, cards) {
    var docs = [];
    rules.forEach(function (r) {
      r.articles.forEach(function (a) { docs.push({ rule: r.name, no: a.no, title: a.title, kind: "article", flat: flatText(a.text) }); });
      (r.annexes || []).forEach(function (x) { docs.push({ rule: r.name, no: x.title, title: "", kind: "annex", flat: flatText(x.title + " " + (x.text || "")) }); });
    });
    // 줄여 부르는 말: "법인카드(이하 “카드”라 한다)" → 그 내규 안에서는 '카드'도 같은 말
    var defs = [];
    docs.forEach(function (d) {
      var re = /\(이하[“"‘']([^”"’']{2,15})[”"’'](?:이?라|로)한다\)/g, m;
      while ((m = re.exec(d.flat))) defs.push({ rule: d.rule, at: d.no, alias: m[1], before: d.flat.slice(Math.max(0, m.index - 30), m.index) });
    });
    this.docs = docs;
    this.defs = defs;
    this.rules = rules;
    this.index = index;
    this.cards = new Map((cards || []).map(function (c) { return [c.id, c]; }));
  }

  // 카드 인용("복무세칙 제15조제2항", "여비지급세칙 별표 제1호")이 가리키는 조문·별표
  Compass.prototype.docOf = function (cite) {
    var m = /^(.+?) (제\d+조(?:의\d+)?)/.exec(cite), docs = this.docs;
    if (m) return docs.filter(function (d) { return d.kind === "article" && d.rule === m[1] && d.no === m[2]; })[0] || null;
    m = /^(.+?) (별표.*)$/.exec(cite);
    if (!m || m[2].indexOf("조") >= 0) return null;
    var head = flatText(m[2]);
    return docs.filter(function (d) { return d.kind === "annex" && d.rule === m[1] && flatText(d.no).indexOf(head) === 0; })[0] || null;
  };

  // 같은 내규끼리 묶는다(순서는 부르는 쪽에서 정한다)
  function byRule(list) {
    var groups = new Map();
    list.forEach(function (x) {
      var g = groups.get(x.rule);
      if (!g) groups.set(x.rule, g = { rule: x.rule, hits: [] });
      g.hits.push(x.hit);
    });
    var out = Array.from(groups.values());
    out.forEach(function (g) { g.n = g.hits.length; });
    return out;
  }

  Compass.prototype.find = function (query) {
    var q = String(query || "").normalize("NFC").replace(DOTS, "·").replace(/\s+/g, " ").trim();
    var whole = flatText(q), parts = q.split(" ").map(flatText).filter(function (w) { return w.length >= 2; });
    var res = { query: q, mode: "phrase", words: [], named: [], exact: [], order: [], aliases: [], similar: [], simWords: [], outside: [], related: [] };
    if (whole.length < 2) { res.short = true; return res; }
    // 두 낱말 이상이면 모두 나오는 곳("직원 징계"), 한 낱말이면 그 낱말이 나오는 곳
    var words = parts.length >= 2 ? parts : [whole], self = this;
    if (parts.length >= 2) res.mode = "all";
    res.words = words;
    var has = function (d) { return words.every(function (w) { return d.flat.indexOf(w) >= 0; }); };
    res.named = this.rules.filter(function (r) { return words.every(function (w) { return flatText(r.name).indexOf(w) >= 0; }); })
      .map(function (r) { return { rule: r.name, articles: r.articles.length }; });
    var hits = this.docs.filter(has);
    res.exact = byRule(hits.map(function (d) {
      return { rule: d.rule, hit: { no: d.no, title: d.title, kind: d.kind, count: words.reduce(function (s, w) { return s + countIn(d.flat, w); }, 0) } };
    }));
    // 그 내규가 낱말을 줄여 부르면, 줄인 말이 나오는 조문도 그 내규 안에서 찾는다
    if (res.mode === "phrase") {
      var seen = {};
      this.defs.forEach(function (df) {
        var key = df.rule + "|" + df.alias;
        // 줄인 말의 글자가 모두 원래 말에 있어야 한다("법인카드"→"카드"). "직원(이하 “행동강령책임관”)"은 줄임말이 아니라 다른 말
        if (seen[key] || df.alias === whole || df.before.slice(-whole.length) !== whole ||
          !df.alias.split("").every(function (ch) { return whole.indexOf(ch) >= 0; })) return;
        seen[key] = 1;
        var inExact = new Set(hits.filter(function (d) { return d.rule === df.rule; }).map(function (d) { return d.no; }));
        var ah = self.docs.filter(function (d) { return d.rule === df.rule && !inExact.has(d.no) && d.flat.indexOf(df.alias) >= 0; })
          .map(function (d) { return { no: d.no, title: d.title, kind: d.kind, count: countIn(d.flat, df.alias) }; });
        if (ah.length) res.aliases.push({ rule: df.rule, alias: df.alias, at: df.at, hits: ah });
      });
    }
    // 목록 순서(order): 나오는 곳이 많은 내규부터(줄인 말로 나오는 곳 포함), 같으면 내규 목록 순.
    // 이름에 낱말이 든 내규는 named 로 따로 알리므로 순서에서 앞세우지 않는다("출장" → 여비지급세칙 17곳이 공무국외출장세부지침 11곳보다 앞)
    var total = {}, at0 = {};
    this.rules.forEach(function (r, i) { at0[r.name] = i; });
    res.exact.forEach(function (g) { total[g.rule] = g.n; });
    res.aliases.forEach(function (a) { total[a.rule] = (total[a.rule] || 0) + a.hits.length; });
    res.order = Object.keys(total).sort(function (a, b) { return total[b] - total[a] || at0[a] - at0[b]; });
    res.exact.sort(function (a, b) { return res.order.indexOf(a.rule) - res.order.indexOf(b.rule); });
    if (hits.length) return res;

    // 글자 그대로 없을 때: ① 원문에서 쓰는 말로 바꿔 찾기 ② 그 말을 묻는 답 카드가 가리키는 조문
    // rank: 내규 묶음 순서. 그 낱말을 묻는 답 카드의 근거(0~3)가 바꿔 찾은 말로만 나온 곳(100~)보다 앞
    var sim = [], at = new Map(), rankOf = new Map();
    function add(d, why, w, quote, rank) {
      rankOf.set(d.rule, Math.min(rankOf.has(d.rule) ? rankOf.get(d.rule) : rank, rank));
      var x = at.get(d);
      if (!x) { at.set(d, x = { no: d.no, title: d.title, kind: d.kind, why: why, words: [], quotes: [] }); sim.push({ rule: d.rule, hit: x }); }
      if (w && x.words.indexOf(w) < 0) x.words.push(w);
      if (quote && x.quotes.indexOf(quote) < 0) x.quotes.push(quote);
    }
    synonymsOf(q).split(" ").map(flatText).forEach(function (w) {
      if (w.length < 2 || w === whole || res.simWords.length >= 3 || res.simWords.some(function (s) { return s.word === w; })) return;
      var ds = self.docs.filter(function (d) { return d.flat.indexOf(w) >= 0; });
      // 조문 60곳 넘게 나오는 말('근로')은 너무 흔해 길잡이가 안 된다
      if (!ds.length || ds.length > 60) return;
      res.simWords.push({ from: q, word: w });
      var rank = 100 + res.simWords.length;
      ds.forEach(function (d) { add(d, "‘" + q + "’ → 원문에서 쓰는 말 ‘" + w + "’", w, null, rank); });
    });
    if (this.index) {
      // 그 낱말을 실제로 묻는 답 카드(제목·예상 질문에 글자 그대로 있음)만 쓴다. 점수만 비슷한 카드는 곁가지가 많다
      var asks = function (c) { return [c.title].concat(c.questions || []).some(function (x) { return flatText(x).indexOf(whole) >= 0; }); };
      var picked = 0;
      this.index.score(q).forEach(function (r) {
        var c = self.cards.get(r.id);
        if (!c || picked >= 4 || !asks(c)) return;
        picked++;
        // '내규에 없음' 카드는 찾은 낱말이 그 이름에 들어 있을 때만 알린다("반차" → "반반차·시간 단위 연가")
        if (c.kind === "outside") { if (flatText(c.title).indexOf(whole) >= 0) res.outside.push({ id: c.id, title: c.title }); return; }
        var n = 0;
        (c.facts || []).forEach(function (f) {
          var d = self.docOf(f.cite);
          if (!d || (n >= 3 && !at.has(d))) return;
          if (!at.has(d)) n++;
          add(d, "‘" + c.title + "’ 답의 근거", null, f.quote, picked);
          if (!at.get(d).card) at.get(d).card = c.id;
        });
      });
    }
    res.similar = byRule(sim).sort(function (a, b) { return rankOf.get(a.rule) - rankOf.get(b.rule) || b.n - a.n; });
    if (!sim.length) {
      this.art = this.art || new ArticleIndex(this.rules);
      res.related = this.art.search(q, 5).map(function (r) { return { rule: r.doc.rule, no: r.doc.no, title: r.doc.title, kind: r.doc.kind }; });
    }
    return res;
  };

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
  function addYears(d, n) {
    var t = new Date(Date.UTC(d.getUTCFullYear() + n, d.getUTCMonth(), d.getUTCDate()));
    return t.getUTCMonth() === d.getUTCMonth() ? t : new Date(Date.UTC(d.getUTCFullYear() + n, d.getUTCMonth() + 1, 1));
  }
  // 만으로 몇 년 몇 개월
  function yearsMonths(from, to) {
    var m = (to.getUTCFullYear() - from.getUTCFullYear()) * 12 + (to.getUTCMonth() - from.getUTCMonth());
    if (to.getUTCDate() < from.getUTCDate()) m--;
    return { y: Math.floor(m / 12), m: m % 12 };
  }
  // 정상 입학(태어난 해 + 7년 3월) 기준으로 초등학교 n학년이 끝나는 날(그다음 해 2월 말)
  function endOfGrade(birth, grade) {
    var y = birth.getUTCFullYear() + 7 + grade;
    return addDays(new Date(Date.UTC(y, 2, 1)), -1);
  }

  var CUT_SPOUSE_LOSS = parseDate("2026-09-18");
  var CUT_SPOUSE_PREBIRTH = parseDate("2026-09-18");
  var SPOUSE_RULE_FROM = parseDate("2026-08-12");  // 지금 복무세칙(배우자 출산휴가 20일·120일) 시행일
  var CUT_INFERTILITY = parseDate("2026-11-27");

  var calc = {
    // 배우자 출산전후휴가: 사용 가능 기간
    spouseBirth: function (o) {
      var due = parseDate(o.due), birth = parseDate(o.birth) || null;
      if (!due) return { error: "출산예정일을 입력하세요." };
      var base = birth || due;
      if (base < SPOUSE_RULE_FROM) return { error: "출산(예정)일이 지금 복무세칙 시행일(2026.8.12.)보다 앞섭니다. 그때 기준은 관련 부서에 문의하세요." };
      var days = o.multiple ? 25 : 20, start = addDays(due, -50), startWhy = " (출산예정일 50일 전)", notes = [];
      if (start < CUT_SPOUSE_PREBIRTH) {
        notes.push("출산 전 사용은 2026.9.18.부터 적용되므로, 그 전 날짜에는 쓸 수 없습니다.");
        // 예정일이 적용일 전이면 출산 전에는 쓸 수 없어 출산일부터 쓴다
        if (due > CUT_SPOUSE_PREBIRTH) { start = CUT_SPOUSE_PREBIRTH; startWhy = " (출산 전 사용 적용일)"; }
        else { start = base; startWhy = " (출산일부터)"; }
      }
      var last = addDays(base, 120);
      return {
        rows: [
          ["휴가일수", days + "일 (유급, 모두 사용해야 함)"],
          ["쓸 수 있는 첫날", fmt(start) + startWhy],
          ["쓸 수 있는 마지막 무렵", fmt(last) + (birth ? " (출산일 + 120일)" : " (예정일에 출산한다고 가정, 출산일 + 120일)")],
          ["나눠 쓰기", "3회까지"],
          ["자동육아휴직 신청서", "배우자 출산휴가 시작일까지 제출 (별지 제15-3호)"]
        ],
        notes: notes.concat([
          "토요일·공휴일은 휴가일수 " + days + "일에 넣지 않습니다.",
          "'출산한 날부터 120일이 지나면' 쓸 수 없습니다. 마지막 날을 출산일 포함으로 세는지는 관련 부서에 문의하세요."
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
      if (start > due) notes.unshift("시작일이 출산예정일보다 늦습니다. 시작일을 다시 확인하세요.");
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
          notes: ["신청 기한의 마지막 날을 유산일 포함으로 세는지는 관련 부서에 문의하세요."]
        };
      }
      var w = +o.weeks;
      if (!(w > 0)) return { error: "임신 주수를 입력하세요." };
      if (w > 45) return { error: "임신 주수를 확인하세요(45주 이하)." };
      var days = w <= 15 ? 10 : w <= 21 ? 30 : w <= 27 ? 60 : 90;
      return {
        rows: [
          ["휴가 기간", "유산·사산한 날부터 " + days + "일까지"],
          ["끝나는 날", fmt(addDays(d, days - 1)) + " (유산·사산일을 1일째로 셀 때)"],
          ["급여", days === 90 ? "최초 60일까지 유급" : "유급"]
        ],
        notes: ["임신 15주와 16주 사이처럼 경계에 걸리면 관련 부서에 문의하세요."]
      };
    },
    // 자녀 나이로 쓸 수 있는 제도
    childAge: function (o) {
      var b = parseDate(o.birth), today = parseDate(o.today) || new Date(Date.UTC(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()));
      if (!b) return { error: "자녀 생년월일을 입력하세요." };
      if (b > today) return { error: "자녀 생년월일이 기준일보다 늦습니다." };
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
    // 연가일수: 입사일과 기준일로 근속연수를 셈
    annualLeave: function (o) {
      var hire = parseDate(o.hire), today = parseDate(o.today);
      if (!hire || !today) return { error: "입사일과 기준일을 입력하세요." };
      if (today < hire) return { error: "기준일이 입사일보다 빠릅니다." };
      var span = yearsMonths(hire, today), rows = [["근속기간", span.y + "년 " + span.m + "개월"]], notes = [];
      if (span.y < 1) {
        var months = span.y * 12 + span.m;
        rows.push(["연가", "1개월 개근할 때마다 1일 → 지금까지 최대 " + Math.min(11, months) + "일"]);
        rows.push(["1년이 되는 날", fmt(addYears(hire, 1)) + " (그 뒤 1년간 80% 출근하면 15일)"]);
      } else {
        var add = span.y >= 3 ? Math.floor((span.y - 1) / 2) : 0, total = Math.min(25, 15 + add);
        rows.push(["연가일수", total + "일 (기본 15일 + 가산 " + Math.min(add, 10) + "일)"]);
        if (total < 25) {
          var next = span.y < 3 ? 3 : (span.y % 2 === 1 ? span.y + 2 : span.y + 1);
          rows.push(["다음에 1일 늘어나는 때", "근속 " + next + "년 (" + fmt(addYears(hire, next)) + ")"]);
        } else rows.push(["상한", "25일에 도달"]);
      }
      notes.push("1년간 출근율 80% 이상일 때 기준입니다. 휴직 기간이 있으면 그해 연가가 비례해서 줄어듭니다.");
      notes.push("연가를 언제 기준으로 부여하는지(입사일 또는 회계연도)는 관련 부서에 문의하세요.");
      return { rows: rows, notes: notes };
    },
    // 장기재직휴가: 근속 10년·20년이 되는 날
    longService: function (o) {
      var hire = parseDate(o.hire), today = parseDate(o.today);
      if (!hire || !today) return { error: "입사일과 기준일을 입력하세요." };
      if (today < hire) return { error: "기준일이 입사일보다 빠릅니다." };
      var y = yearsMonths(hire, today).y, d10 = addYears(hire, 10), d20 = addYears(hire, 20), rows = [["근속연수", y + "년"]];
      if (y < 10) rows.push(["장기재직휴가", "아직 대상 아님 → " + fmt(d10) + "부터 5일"]);
      else if (y < 20) {
        rows.push(["지금 쓸 수 있는 휴가", "5일 (1회, 1번 나눠 쓰기 가능)"]);
        rows.push(["5일을 써야 하는 기한", fmt(addDays(d20, -1)) + "까지 (근속 20년이 되면 남은 일수 소멸)"]);
        rows.push(["다음 휴가", fmt(d20) + "부터 7일"]);
      } else rows.push(["지금 쓸 수 있는 휴가", "7일 (1회, 1번 나눠 쓰기 가능)"]);
      return { rows: rows, notes: ["휴직·정직·직위해제 기간은 근속기간에서 빠질 수 있습니다(상벌세칙 제8조제2항). 계산기는 빠지는 기간이 없다고 가정했습니다.", "장기재직휴가 규정은 2026.1.1.부터 적용됩니다."] };
    },
    // 국내 출장 여비(근무지 외, 직원 기준): 일비·식비·숙박비 상한. 운임은 실비라 따로 더한다.
    tripExpense: function (o) {
      var days = Math.max(0, Math.floor(+o.days || 0)), nights = Math.max(0, Math.floor(+o.nights || 0));
      if (!days) return { error: "출장 일수를 입력하세요." };
      if (nights >= days) return { error: "숙박 일수는 출장 일수보다 적어야 합니다(" + days + "일 출장이면 " + (days - 1) + "박까지)." };
      var cap = { seoul: 100000, metro: 80000, other: 70000 }[o.region] || 70000;
      // 회의비·업무추진비 등 다른 예산으로 먹은 끼니는 1식 8,330원씩 뺀다(제20조제2항, 1일 3식 기준)
      var meals = Math.max(0, Math.floor(+o.meals || 0));
      if (meals > days * 3) return { error: "다른 예산으로 먹은 끼니가 " + days + "일 × 3끼(" + days * 3 + "끼)보다 많습니다." };
      var perDay = o.car ? 12500 : 25000, meal = days === 1 && nights === 0 ? 12500 : 25000;
      // 당일 출장은 식비가 이미 절반이라, 거기서 끼니를 빼는 방법이 세칙에 없다 → 계산하지 않고 관련 부서 문의 안내만
      var sameDayCut = meals && meal === 12500;
      var dayPay = perDay * days, mealFull = meal * days, mealPay = sameDayCut ? mealFull : Math.max(0, mealFull - 8330 * meals), lodge = cap * nights, won = function (n) { return n.toLocaleString("ko-KR") + "원"; };
      var notes = [];
      if (days > 15) notes.push("같은 곳에 15일 넘게 머무르면 일비가 10~30% 줄어듭니다(제22조). 계산기는 반영하지 않았습니다.");
      if (sameDayCut) notes.push("당일 출장(식비 절반)에서 다른 예산으로 먹은 끼니를 얼마나 빼는지는 세칙에 정한 방법이 없어 계산하지 않았습니다. 관련 부서에 문의하세요.");
      if (meals && !sameDayCut && meals % 3 === 0) notes.push("1끼 8,330원 × 3끼 = 24,990원이라, 하루 세 끼를 모두 빼도 하루 10원이 남습니다(세칙 금액 그대로 계산).");
      return {
        rows: [
          ["일비", won(perDay) + " × " + days + "일 = " + won(dayPay) + (o.car ? " (업무용 차량: 절반)" : "")],
          ["식비", won(meal) + " × " + days + "일 = " + won(mealFull) + (meal === 12500 ? " (당일 출장: 절반)" : "") +
            (sameDayCut ? " · 다른 예산 " + meals + "끼는 빼는 방법이 정해져 있지 않음(관련 부서 문의)" : meals ? " − 다른 예산 " + meals + "끼 × 8,330원 = " + won(mealPay) : "")],
          ["숙박비", nights ? "실비, 상한 " + won(cap) + " × " + nights + "박 = 최대 " + won(lodge) : "숙박 없음"],
          ["합계(운임 제외)", "최대 " + won(dayPay + mealPay + lodge) + (sameDayCut ? " (끼니 공제 전, 관련 부서 문의)" : "")],
          ["운임", "실비 (철도 일반실·고속열차 한도, 항공·선박 2등석)"]
        ],
        notes: notes.concat(["회의비·업무추진비 등 다른 예산으로 먹은 끼니는 1끼 8,330원씩 빼고 받습니다(1일 3끼 기준).", "운임과 숙박비는 다녀온 다음 날부터 2주 안에 증거서류로 정산합니다.", "출장지가 '근무지 외'인지는 공무원 여비 규정 기준이라 관련 부서에 문의하세요.", "조사업무 담당자의 제주·기획조사 출장 일비 가산은 반영하지 않았습니다."])
      };
    },
    // 연간 복지포인트(기본 + 근속 + 가족 + 우대). 출산포인트는 따로.
    welfarePoints: function (o) {
      var y = Math.max(0, Math.floor(+o.years || 0)), kids = Math.max(0, Math.floor(+o.children || 0));
      var tenure = Math.min(300, 20 * Math.min(y, 10) + 10 * Math.max(0, y - 10)), family = (o.spouse ? 100 : 0), extra = o.disabled ? 50 : 0;
      for (var i = 1; i <= kids; i++) family += i === 1 ? 50 : i === 2 ? 100 : 150;
      var total = o.newHire ? 400 : 400 + tenure + family + extra;
      return {
        rows: [["기본포인트", "400"], ["근속포인트", o.newHire ? "0 (신규채용 연도는 기본만)" : tenure + (tenure === 300 ? " (최고 300)" : "")],
               ["가족포인트", o.newHire ? "0" : String(family)], ["우대포인트(장애인)", o.newHire ? "0" : String(extra)],
               ["합계", total + "포인트 (1포인트 = 1천원 → " + (total * 1000).toLocaleString("ko-KR") + "원)"]],
        notes: ["근속연수와 가족은 전년도 12월 31일 기준입니다. 자녀는 20세 미만만 셉니다.", "출산포인트(전통시장포인트)는 따로 받습니다. 예산 상황에 따라 조정될 수 있습니다."]
      };
    },
    // 가족수당 (배우자 + 자녀)
    allowance: function (o) {
      var n = Math.max(0, Math.floor(+o.children || 0)), sum = o.spouse ? 40000 : 0, parts = [];
      if (o.spouse) parts.push(["배우자", "40,000원"]);
      if (n >= 1) { sum += 20000; parts.push(["첫째 자녀", "20,000원"]); }
      if (n >= 2) { sum += 40000; parts.push(["둘째 자녀", "40,000원"]); }
      if (n >= 3) { sum += 110000 * (n - 2); parts.push(["셋째부터 자녀 " + (n - 2) + "명", "110,000원 × " + (n - 2) + "명 = " + (110000 * (n - 2)).toLocaleString("ko-KR") + "원"]); }
      parts.push(["월 합계", sum.toLocaleString("ko-KR") + "원"]);
      return { rows: parts, notes: ["부모 등 다른 부양가족이 있으면 4인 한도 계산이 달라질 수 있습니다.", "부부가 모두 직원이면 한 명만 받습니다."] };
    }
  };

  // 질문 속 날짜(2023.3.2, 2023-03-02, 2023년 3월 2일)를 YYYY-MM-DD 로 뽑는다(계산기 칸 채우기용)
  // 앞뒤 말(ctx)도 함께 돌려줘, 계산기가 '입사일'·'출산예정일' 등 어느 칸의 날짜인지 가려 넣게 한다
  function datesIn(text) {
    var out = [], t = String(text || ""), re = /(\d{4})\s*[.\-\/년]\s*(\d{1,2})\s*[.\-\/월]\s*(\d{1,2})\s*일?/g, m;
    while ((m = re.exec(t))) {
      var mo = +m[2], d = +m[3];
      if (mo >= 1 && mo <= 12 && d >= 1 && d <= 31)
        out.push({ iso: m[1] + "-" + (mo < 10 ? "0" : "") + mo + "-" + (d < 10 ? "0" : "") + d,
                   ctx: t.slice(Math.max(0, m.index - 10), m.index) + " " + t.slice(m.index + m[0].length, m.index + m[0].length + 12) });
    }
    return out;
  }
  // 질문 속 일수·지역·인원 등(계산기 칸 채우기용). 분명히 읽히는 것만 돌려주고, 못 읽은 칸은 계산기가 비워 둔다.
  var KNUM = { "하나": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "넷": 4, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10 };
  var NUMW = "(\\d+|하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉|열)";
  var ORDINAL = { "첫": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5 };
  var OTHER_BUDGET = /회의비|업무추진비|회사\s*(돈|카드|비용|에서)|법인\s*카드|다른\s*예산|제공|대접|사\s*줬|사\s*주/;
  function num(w) { return /^\d+$/.test(w) ? +w : KNUM[w]; }
  function valuesIn(text) {
    var t = String(text || ""), v = {}, m;
    // 출장 일수·숙박 일수: "1박2일", "2박 3일", "당일", "3일 출장"
    if ((m = t.match(new RegExp(NUMW + "\\s*박\\s*" + NUMW + "\\s*일")))) { v.nights = num(m[1]); v.days = num(m[2]); }
    else if (/당일|하루\s*(출장|만|짜리)|숙박\s*(없|안\s*하)/.test(t)) { v.days = 1; v.nights = 0; }
    else if ((m = t.match(new RegExp(NUMW + "\\s*일\\s*(간|동안)?\\s*출장")))) v.days = num(m[1]);
    // 숙박 지역: 서울, 광역시·제주만 넣는다(경기 광주 제외). 그 밖의 지명은 구분이 애매해 비워 둔다
    if (/서울/.test(t)) v.region = "seoul";
    else if (/부산|대구|인천|광주|대전|울산|제주/.test(t) && !/경기\s*광주/.test(t)) v.region = "metro";
    // 세종특별자치시는 별표 제1호에 따로 없다: 지역 칸은 비워 두고 왜 비웠는지 알린다
    if (!v.region && /세종/.test(t)) v.regionNote = "세종특별자치시는 여비지급세칙 별표 제1호에 따로 적혀 있지 않습니다(서울특별시·광역시·그 밖의 지역, 제주는 광역시 기준). 숙박 지역을 어디로 볼지 관련 부서에 문의하세요.";
    // 회의비 등 다른 예산으로 먹은 끼니: 그런 말이 있을 때만("2끼", "점심·저녁")
    if (OTHER_BUDGET.test(t)) {
      if ((m = t.match(new RegExp(NUMW + "\\s*끼")))) v.meals = num(m[1]);
      else {
        var k = (t.match(/아침|점심|저녁/g) || []).filter(function (x, i, a) { return a.indexOf(x) === i; }).length;
        if (k) v.meals = k;
      }
    }
    // 자녀 수: "아이 둘", "자녀 2명", "애가 셋", "두 아이", "셋째". 나이("아이 7살")는 자녀 수가 아니다
    var re = new RegExp("(자녀|아이|애|아들|딸)\\s*(가|는|이|도)?\\s*" + NUMW + "\\s*(명)?(\\s*\\S)?");
    if ((m = t.match(re)) && !/[살세개학주년]/.test((m[5] || "").trim().charAt(0) || "")) v.children = num(m[3]);
    else if ((m = t.match(new RegExp(NUMW + "\\s*(명의\\s*)?(자녀|아이|애)")))) v.children = num(m[1]);
    else if ((m = t.match(/(첫|둘|셋|넷|다섯)째/))) v.children = ORDINAL[m[1]];
    // 근속연수: "근속 7년", "7년 차", "입사 7년"
    if ((m = t.match(/근속\s*(\d+)\s*년|(\d+)\s*년\s*(차|째)|입사\s*(\d+)\s*년/))) v.years = +(m[1] || m[2] || m[4]);
    if (/임신|유산|사산/.test(t) && (m = t.match(/(\d+)\s*주/))) v.weeks = +m[1];
    // 배우자 있음·없음(가족수당·복지포인트)
    if (/미혼|싱글|배우자\s*(가\s*)?없|이혼|사별/.test(t)) v.spouse = "n";
    else if (/배우자|아내|와이프|남편|부인|집사람|기혼|결혼했/.test(t)) v.spouse = "y";
    if (/쌍둥이|다태|둘\s*이상\s*(임신|출산)/.test(t)) v.multiple = true;
    if (/업무용\s*차|관용\s*차|공용\s*차|회사\s*차/.test(t)) v.car = true;
    if (/유산|사산/.test(t)) {
      if (/아내|와이프|배우자|부인|집사람/.test(t)) v.who = "spouse";
      else if (/제가|본인|내가/.test(t)) v.who = "self";
    }
    return v;
  }
  // 질문이 계산을 원하는지(주제어 + 금액·기간을 묻는 말). 계산기 없는 답이 나와도 '계산기 열기'를 붙이는 데 쓴다.
  // 여비·수당·포인트는 낱말 자체가 금액이라 묻는 말이 없어도 계산기를 붙인다(세 번째 칸 true)
  var CALC_ASK = /얼마|며칠|몇\s*일|몇\s*점|몇\s*포인트|계산|금액|기간|언제|깎|빼|나와|나오|받(아|나|을|는|으)/;
  var CALC_TOPIC = [
    ["tripExpense", /출장\s*(비|여비)|출장.{0,8}(여비|일비|식비|숙박|얼마)|여비|일비|숙박비/, true],
    ["allowance", /가족\s*수당/, true],
    ["welfarePoints", /복지\s*포인트|가족\s*포인트|근속\s*포인트/, true],
    ["longService", /장기\s*재직/],
    ["familyCare", /가족\s*돌봄\s*휴가/],
    ["annualLeave", /연가|연차/],
    ["spouseBirth", /배우자\s*출산|(아내|와이프|부인|집사람).{0,8}출산/],
    ["maternity", /출산\s*(전후\s*)?휴가/],
    ["loss", /유산|사산/]
  ];
  // 해외 출장이면 국내 여비 계산기를 붙이지 않는다(국외 여비는 지역 등급·항공운임이 달라 계산기가 없다)
  var OVERSEAS = new RegExp("국외|해외|외국|국제선|" + OVERSEAS_PLACES);
  function calcFor(text) {
    var t = String(text || ""), overseas = OVERSEAS.test(t);
    // "출장 가서 점심을 회사 돈으로 먹었어요"처럼 묻는 말이 없어도 끼니 공제를 말하면 출장 여비 계산기
    if (!overseas && /출장/.test(t) && OTHER_BUDGET.test(t) && /아침|점심|저녁|식사|밥|끼/.test(t)) return "tripExpense";
    var ask = CALC_ASK.test(t);
    for (var i = 0; i < CALC_TOPIC.length; i++) {
      if (overseas && CALC_TOPIC[i][0] === "tripExpense") continue;
      if ((ask || CALC_TOPIC[i][2]) && CALC_TOPIC[i][1].test(t)) return CALC_TOPIC[i][0];
    }
    return null;
  }
  // 이어 묻기("그럼 자가용으로 가면?")인지: 앞 질문의 주제를 이어 붙여 다시 찾는다
  var FOLLOW = /^(그럼|그러면|그런데|근데|그\s?경우|그때|그건|그거|이\s?경우|만약에?|혹시\s?그)/;
  function isFollowUp(text) {
    var t = normalize(text);
    // 접속어로 시작하거나, "일비는?"·"자가용이면?"처럼 짧은 말에 조사만 붙여 물을 때. "출산" 같은 한 단어 새 질문은 아니다.
    var shortTail = /(은|는|도|이면|라면|면)\s*요?$/.test(t) && content(text).split(" ").filter(Boolean).length <= 2 && t.length <= 14;
    return FOLLOW.test(t) || shortTail;
  }

  var api = { datesIn: datesIn, valuesIn: valuesIn, calcFor: calcFor, isFollowUp: isFollowUp, ruleOfCard: ruleOfCard, normalize: normalize, content: content, expand: expand, CardIndex: CardIndex, decide: decide, ArticleIndex: ArticleIndex, snippet: snippet, Compass: Compass, wordRe: wordRe, excerpt: excerpt, calc: calc, thresholds: T, parseDate: parseDate, iso: iso };
  root.NaegyuEngine = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
