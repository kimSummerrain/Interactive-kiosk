const MENU_ID_TO_INDEX = {
  ame_hot: 1,
  ame_ice: 2,
  latte_hot: 3,
  latte_ice: 4,
  choco_hot: 5,
  choco_ice: 6,
  straw_smoothie: 7,
  blue_smoothie: 8,
  mango_smoothie: 9,
  yogurt_smoothie: 10,
  chamomile_hot: 11,
  chamomile_ice: 12,
  lemon_hot: 13,
  lemon_ice: 14,
};


function resetCart10() {
  for (const k in cart10) delete cart10[k];
  renderCart10();
}

function resetCart50() {
  for (const k in cart50) delete cart50[k];
  renderCart50();
}

function showScreen(screenId) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  const el = document.getElementById(screenId);
  (el || document.getElementById("screen-order"))?.classList.add("active");
}

function setSelected(id) {
  const takeout = document.getElementById("btnTakeout");
  const eathere = document.getElementById("btnEathere");
  if (takeout) takeout.classList.remove("selected");
  if (eathere) eathere.classList.remove("selected");

  const target = document.getElementById(id);
  if (target) target.classList.add("selected");
}

function clearSelection() {
  const takeout = document.getElementById("btnTakeout");
  const eathere = document.getElementById("btnEathere");
  if (takeout) takeout.classList.remove("selected");
  if (eathere) eathere.classList.remove("selected");
}

function resetFacePreview() {
  const fileInput = document.getElementById("fileInput");
  const preview = document.getElementById("preview");
  const previewImg = document.getElementById("previewImg");
  if (fileInput) fileInput.value = "";
  if (preview) preview.hidden = true;
  if (previewImg) previewImg.src = "";
}

let loadingTimer = null;
function clearLoadingTimer() {
  if (loadingTimer) {
    clearTimeout(loadingTimer);
    loadingTimer = null;
  }
}

// =========================
// 50대 메뉴 데이터(임시)
// =========================
const MENU_50 = {
  coffee: [
    { id: "ame_hot",   name: "아메리카노 (Hot)", price: 2000 },
    { id: "ame_ice",   name: "아메리카노 (Ice)", price: 2000 },
    { id: "latte_hot", name: "라떼 (Hot)", price: 2500 },
    { id: "latte_ice", name: "라떼 (Ice)", price: 2500 },
    { id: "capu_hot",  name: "카푸치노 (Hot)", price: 2500 },
    { id: "van_hot",   name: "바닐라라떼 (Hot)", price: 3000 },
    { id: "hazel_hot", name: "헤이즐넛라떼 (Hot)", price: 3000 },
    { id: "caramel_hot", name: "카라멜마끼야또 (Hot)", price: 3500 },
    { id: "mocha_hot", name: "카페모카 (Hot)", price: 3500 },
    { id: "grain_hot", name: "곡물라떼 (Hot)", price: 3200 },
    { id: "choco_hot", name: "초코라떼 (Hot)", price: 3200 },
    { id: "choco_ice", name: "초코라떼 (Ice)", price: 3200 },
  ],

  smoothie: [
    { id: "straw_smoothie",  name: "딸기스무디", price: 3800 },
    { id: "mango_smoothie",  name: "망고스무디", price: 3800 },
    { id: "blue_smoothie",   name: "블루베리스무디", price: 4000 },
    { id: "yogurt_smoothie", name: "요거트스무디", price: 4200 },
  ],

  tea: [
    { id: "lemon_hot",      name: "레몬티 (Hot)", price: 3200 },
    { id: "lemon_ice",      name: "레몬티 (Ice)", price: 3200 },
    { id: "chamomile_hot",  name: "캐모마일티 (Hot)", price: 3200 },
    { id: "chamomile_ice",  name: "캐모마일티 (Ice)", price: 3200 },
    { id: "grapefruit",     name: "자몽허니블랙티", price: 3800 },
    { id: "earlgrey",       name: "얼그레이", price: 3000 },
  ],
};

// =========================
// 50대: 메뉴 인덱스(아이디로 빠르게 찾기)
// =========================
const MENU_INDEX_50 = (() => {
  const map = new Map();
  Object.values(MENU_50).flat().forEach(item => map.set(item.id, item));
  return map;
})();

// 50대 cart 상태: { [menuId]: qty }
const cart50 = {};

// =========================
// 10~40대: 메뉴 인덱스(아이디로 빠르게 찾기)
// =========================
const MENU_INDEX_10TO40 = new Map();

// cart 상태: { [menuId]: qty }
const cart10 = {};

// 총액 계산
function calcTotal10() {
  let total = 0;
  for (const [id, qty] of Object.entries(cart10)) {
    const item = MENU_INDEX_10TO40.get(id);
    if (!item) continue;
    total += item.price * qty;
  }
  return total;
}
//cart->payload 변환 함수
function buildOrderPayload(cart, ageGroup) {
  return {
    age_group: ageGroup,
    items: Object.entries(cart).map(([menuId, qty]) => ({
      menu_id: menuId,
      qty: qty
    }))
  };
}

 
// 결제바 렌더링
function renderCart10() {
  const cartEl = document.getElementById("cart-10to40");
  const totalEl = document.getElementById("total-10to40");
  if (!cartEl || !totalEl) return;

  const entries = Object.entries(cart10);

  if (entries.length === 0) {
    cartEl.innerHTML = `<div style="font-weight:900;font-size:13px;color:#666;">메뉴를 선택해주세요</div>`;
  } else {
    cartEl.innerHTML = entries.map(([id, qty]) => {
      const item = MENU_INDEX_10TO40.get(id);
      if (!item) return "";
      return `
        <div class="cartRow" data-id="${id}">
          <div class="cartName">${item.name}</div>
          <div class="qty">
            <button class="qtyBtn" type="button" data-action="plus" data-id="${id}">+</button>
            <div class="qtyNum">${qty}</div>
            <button class="qtyBtn" type="button" data-action="minus" data-id="${id}">-</button>
          </div>
        </div>
      `;
    }).join("");
  }

  totalEl.textContent = `${calcTotal10().toLocaleString()} 원`;
}

// =========================
// 50대: 총액 계산
// =========================
function calcTotal50() {
  let total = 0;
  for (const [id, qty] of Object.entries(cart50)) {
    const item = MENU_INDEX_50.get(id);
    if (!item) continue;
    total += item.price * qty;
  }
  return total;
}

// =========================
// 50대: 결제바 렌더링
// =========================
function renderCart50() {
  const cartEl = document.getElementById("cart-50");
  if (!cartEl) return;

  const entries = Object.entries(cart50);

  if (entries.length === 0) {
    cartEl.innerHTML = `
      <div style="font-weight:900;font-size:13px;color:#666;">메뉴를 선택해주세요</div>
      <div class="paySumRow">
        <div class="paySumLabel">총 금액</div>
        <div class="paySumValue">0 원</div>
      </div>
    `;
    return;
  }

  const rowsHtml = entries.map(([id, qty]) => {
    const item = MENU_INDEX_50.get(id);
    if (!item) return "";
    return `
      <div class="cartRow" data-id="${id}">
        <div class="cartName">${item.name}</div>
        <div class="qty">
          <button class="qtyBtn" type="button" data-action="plus" data-id="${id}">+</button>
          <div class="qtyNum">${qty}</div>
          <button class="qtyBtn" type="button" data-action="minus" data-id="${id}">-</button>
        </div>
      </div>
    `;
  }).join("");

  cartEl.innerHTML = `
    ${rowsHtml}
    <div class="paySumRow">
      <div class="paySumLabel">총 금액</div>
      <div class="paySumValue">${calcTotal50().toLocaleString()} 원</div>
    </div>
  `;
}

// =========================
// 50대: 메뉴 클릭 시 cart에 추가(+1)
// =========================
function addToCart50(menuId) {
  if (!MENU_INDEX_50.has(menuId)) return;
  cart50[menuId] = (cart50[menuId] || 0) + 1;
  renderCart50();
}

// =========================
// 50대: 수량 변경(+/-)
// =========================
function changeQty50(menuId, delta) {
  if (!cart50[menuId]) return;
  cart50[menuId] += delta;
  if (cart50[menuId] <= 0) delete cart50[menuId];
  renderCart50();
}

// 메뉴를 cart에 추가(클릭하면 +1)
function addToCart10(menuId) {
  if (!MENU_INDEX_10TO40.has(menuId)) return;
  cart10[menuId] = (cart10[menuId] || 0) + 1;
  renderCart10();
}

// 수량 변경
function changeQty10(menuId, delta) {
  if (!cart10[menuId]) return;
  cart10[menuId] += delta;
  if (cart10[menuId] <= 0) delete cart10[menuId];
  renderCart10();
}

// =========================
// 50대: 메뉴 그리드 렌더링
// =========================
function render50Menu(categoryKey) {
  const grid = document.getElementById("grid-50menu");
  if (!grid) return;

  const items = MENU_50[categoryKey] || [];
  grid.innerHTML = items.map(item => `
    <button class="menuItem" type="button" data-id="${item.id}">
      <div class="menuThumb"></div>
      <div class="menuName">${item.name}</div>
      <div class="menuPrice">${item.price.toLocaleString()} 원</div>
    </button>
  `).join("");
}

// =========================
// 50대: 탭 active 처리
// =========================
function setActive50Tab(which) {
  const t1 = document.getElementById("tabCoffee50");
  const t2 = document.getElementById("tabSmoothie50");
  const t3 = document.getElementById("tabTea50");
  if (!t1 || !t2 || !t3) return;

  t1.classList.toggle("active", which === "coffee");
  t2.classList.toggle("active", which === "smoothie");
  t3.classList.toggle("active", which === "tea");
}

// =========================
// 50대: 탭 이벤트 연결
// =========================
function setup50Tabs() {
  const t1 = document.getElementById("tabCoffee50");
  const t2 = document.getElementById("tabSmoothie50");
  const t3 = document.getElementById("tabTea50");

  if (t1) t1.addEventListener("click", () => {
    setActive50Tab("coffee");
    applyMenusTo50(window.__menus50 || [], { resetCart: false, category: "coffee" });
  });

  if (t2) t2.addEventListener("click", () => {
    setActive50Tab("smoothie");
    applyMenusTo50(window.__menus50 || [], { resetCart: false, category: "smoothie" });
  });

  if (t3) t3.addEventListener("click", () => {
    setActive50Tab("tea");
    applyMenusTo50(window.__menus50 || [], { resetCart: false, category: "tea" });
  });

  // 기본값: 커피
  setActive50Tab("coffee");
  applyMenusTo50(window.__menus50 || [], { resetCart: false, category: "coffee" });
}

// =========================
// 50대: 메뉴 클릭 -> 장바구니 담기 (이벤트 위임)
// =========================
const grid50 = document.getElementById("grid-50menu");
if (grid50) {
  grid50.addEventListener("click", (e) => {
    const btn = e.target.closest(".menuItem");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (!id) return;
    addToCart50(id);
  });
}

// =========================
// 50대: 결제바 + / - 클릭 (이벤트 위임)
// =========================
const cartEl50 = document.getElementById("cart-50");
if (cartEl50) {
  cartEl50.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-action][data-id]");
    if (!b) return;
    const id = b.getAttribute("data-id");
    const action = b.getAttribute("data-action");
    if (!id || !action) return;

    if (action === "plus") changeQty50(id, +1);
    if (action === "minus") changeQty50(id, -1);
  });
}

// 50대 결제바 초기 렌더
renderCart50();

// =========================
// 10~40대: 탭 active 처리
// =========================
function setActive10to40Tab(which) {
  const tabCoffee = document.getElementById("tabCoffee10");
  const tabSmoothie = document.getElementById("tabSmoothie10");
  const tabTea = document.getElementById("tabTea10");

  if (!tabCoffee || !tabSmoothie || !tabTea) return;

  tabCoffee.classList.toggle("active", which === "coffee");
  tabSmoothie.classList.toggle("active", which === "smoothie");
  tabTea.classList.toggle("active", which === "tea");
}

// =========================
// 10~40대: 탭 이벤트 연결
// =========================
function setup10to40Tabs() {
  const tabCoffee = document.getElementById("tabCoffee10");
  const tabSmoothie = document.getElementById("tabSmoothie10");
  const tabTea = document.getElementById("tabTea10");

  if (tabCoffee) {
    tabCoffee.addEventListener("click", () => {
      setActive10to40Tab("coffee");
      applyMenusTo10to40(window.__menus10to40 || [], { resetCart: false, category: "coffee" });
    });
  }

  if (tabSmoothie) {
    tabSmoothie.addEventListener("click", () => {
      setActive10to40Tab("smoothie");
      applyMenusTo10to40(window.__menus10to40 || [], { resetCart: false, category: "smoothie" });
    });
  }

  if (tabTea) {
    tabTea.addEventListener("click", () => {
      setActive10to40Tab("tea");
      applyMenusTo10to40(window.__menus10to40 || [], { resetCart: false, category: "tea" });
    });
  }

  // ✅ 처음 진입 시 기본 = 커피
  setActive10to40Tab("coffee");
  applyMenusTo10to40(window.__menus10to40 || [], { resetCart: false, category: "coffee" });
}


function init() {
  // 주문 화면
  const btnTakeout = document.getElementById("btnTakeout");
  const btnEathere = document.getElementById("btnEathere");

  if (btnTakeout) {
    btnTakeout.addEventListener("click", () => {
      setSelected("btnTakeout");
      window.__orderMode = "takeout";
      resetFacePreview();
      clearLoadingTimer();
      showScreen("screen-face");
    });
  }

  if (btnEathere) {
    btnEathere.addEventListener("click", () => {
      setSelected("btnEathere");
      window.__orderMode = "eathere";
      resetFacePreview();
      clearLoadingTimer();
      showScreen("screen-face");
    });
  }

  // 얼굴 화면 뒤로가기
  const btnBack = document.getElementById("btnBack");
  if (btnBack) {
    btnBack.addEventListener("click", () => {
      clearLoadingTimer();
      clearSelection();
      window.__orderMode = null;
      resetFacePreview();
      showScreen("screen-order");
    });
  }

  // 파일 업로드
  const fileInput = document.getElementById("fileInput");
  const btnPick = document.getElementById("btnPick");
  const preview = document.getElementById("preview");
  const previewImg = document.getElementById("previewImg");

  if (btnPick && fileInput) btnPick.addEventListener("click", () => fileInput.click());

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;

      if (preview && previewImg) {
        const url = URL.createObjectURL(f);
        previewImg.src = url;
        preview.hidden = false;
      }

      showScreen("screen-loading");

      clearLoadingTimer();
      // loadingTimer = setTimeout(() => {
      //   showScreen("screen-result");
      // }, 5000);
      (async () => {
        try {
          const formData = new FormData();
          formData.append("file", f);
      
          const res = await fetch("/api/recommend", {
            method: "POST",
            body: formData
          });
      
          const data = await res.json();
      
          if (data.error) {
            console.log(data.error)

            alert(data.message || "얼굴 인식 실패");
            showScreen("screen-face");
            return;
          }
      
          handleRecommendFromBackend(data);
      
        } catch (e) {
          console.error(e);
          alert("서버 오류");
          showScreen("screen-face");
        }
      })();
      
    });
  }


  // 로딩 뒤로가기
  const btnBackFromLoading = document.getElementById("btnBackFromLoading");
  if (btnBackFromLoading) {
    btnBackFromLoading.addEventListener("click", () => {
      clearLoadingTimer();
      showScreen("screen-face");
    });
  }

  // 결과 뒤로가기
  const btnBackFromResult = document.getElementById("btnBackFromResult");
  if (btnBackFromResult) {
    btnBackFromResult.addEventListener("click", () => {
      clearLoadingTimer();
      clearSelection();
      resetFacePreview();
      showScreen("screen-order");
    });
  }

  // 결과: 10~40대 / 50대 이상
  const btnGo10to40 = document.getElementById("btnGo10to40");
  if (btnGo10to40) {
    btnGo10to40.addEventListener("click", () => {
      clearLoadingTimer();
      showScreen("screen-10to40");
    });
  }

  const btnGo50plus = document.getElementById("btnGo50plus");
  if (btnGo50plus) {
    btnGo50plus.addEventListener("click", () => {
      clearLoadingTimer();
      showScreen("screen-warmcold-menu"); // ⭐ 바로 메뉴 화면
    });
  }
  // 10~40대 화면 뒤로가기
  const btnBackFrom10to40 = document.getElementById("btnBackFrom10to40");
  if (btnBackFrom10to40) {
    btnBackFrom10to40.addEventListener("click", () => {
      resetCart10();            
      showScreen("screen-result");
    });
  }
  document.addEventListener("click", async (e) => {
    const voucher = e.target.closest("#optVoucher");
    const card = e.target.closest("#optCard");
    if (!voucher && !card) return;
  
    console.log("💰 payment clicked", window.__ageGroup);
  
    if (window.__ageGroup === "10_40") {
      await sendOrderToBackend(cart10, "10_40");
    } 
    else if (window.__ageGroup === "41_50") {
      await sendOrderToBackend(cart50, "41_50");
    } 
    else {
      console.error("❌ unknown age group", window.__ageGroup);
      alert("연령대 정보 오류");
      return;
    }
  
    showScreen("screen-complete");
  });

  // 10~40대: 결제하기 -> 결제수단 선택
  const payBtn = document.querySelector("#screen-10to40 .payBtn");
  if (payBtn) payBtn.addEventListener("click", () => showScreen("screen-paymethod"));

  // 결제수단 선택 뒤로가기
  const btnBackFromPaymethod = document.getElementById("btnBackFromPaymethod");
  if (btnBackFromPaymethod) btnBackFromPaymethod.addEventListener("click", () => showScreen("screen-10to40"));

  // 주문 완료: 처음으로
  const btnGoHome = document.getElementById("btnGoHome");
  if (btnGoHome) {
    btnGoHome.addEventListener("click", () => {
      clearLoadingTimer();
      clearSelection();
      resetFacePreview();
      resetCart10();  // ✅
      resetCart50();  // ✅
      showScreen("screen-order");
    });
  }


  // 따뜻/차가운 메뉴 화면 뒤로가기 -> 50대 선택 화면
  const btnBackFromWarmColdMenu = document.getElementById("btnBackFromWarmColdMenu");
  if (btnBackFromWarmColdMenu) {
    btnBackFromWarmColdMenu.addEventListener("click", () => {
      resetCart50();            // ✅ 추가
      showScreen("screen-result");
    });
  }

  setup50Tabs();

  // 결제하기 -> 결제수단 선택 화면(기존 screen-paymethod 재사용)
  const btnPayFromWarmColdMenu = document.getElementById("btnPayFromWarmColdMenu");
  if (btnPayFromWarmColdMenu) {
    btnPayFromWarmColdMenu.addEventListener("click", () => showScreen("screen-paymethod"));
  }
  // =========================
  // 10~40대: 메뉴 클릭 -> 장바구니 담기 (이벤트 위임)
  // =========================
 

  // =========================
  // 10~40대: 결제바 + / - 클릭 (이벤트 위임)
  // =========================
  const cartEl10 = document.getElementById("cart-10to40");
  if (cartEl10) {
    cartEl10.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-action][data-id]");
      if (!b) return;
      const id = b.getAttribute("data-id");
      const action = b.getAttribute("data-action");
      if (!id || !action) return;

      if (action === "plus") changeQty10(id, +1);
      if (action === "minus") changeQty10(id, -1);
    });
  }

  // 처음 들어왔을 때 결제바 초기 렌더
  renderCart10();

  setup10to40Tabs();

  console.log("✅ init done");
}


if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

function handleRecommendFromBackend(data) {
  const ageGroup = data._debug.age_group;
  const menus = data.menus;
  window.__ageGroup = ageGroup;

  if (!menus || menus.length === 0) {
    alert("추천 메뉴가 없습니다");
    showScreen("screen-order");
    return;
  }

  if (ageGroup === "10_40") {
    applyMenusTo10to40(menus, { resetCart: true, category: "coffee" });
    showScreen("screen-10to40");
  } else {
    applyMenusTo50(menus, { resetCart: true, category: "coffee" });
    showScreen("screen-warmcold-menu");
  }
}

async function sendOrderToBackend(cart, ageGroup) {
  const payload = {
    age_group: ageGroup,
    items: Object.entries(cart).map(([menuId, qty]) => ({
      menu_id: menuId,
      qty: qty
    }))
  };

  await fetch("/api/order/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

function bindMenuClick10() {
  const grid = document.getElementById("grid-10to40");
  if (!grid) return;

  grid.onclick = (e) => {
    const btn = e.target.closest(".menuItem");
    if (!btn) return;

    const id = btn.dataset.id;
    if (!id) return;

    addToCart10(id);
  };
}

function bindMenuClick50() {
  const grid = document.getElementById("grid-50menu");
  if (!grid) return;

  grid.onclick = (e) => {
    const btn = e.target.closest(".menuItem");
    if (!btn) return;

    const id = btn.dataset.id;
    if (!id) return;

    addToCart50(id);
  };
}

function applyMenusTo50(menus, options = {}) {
  if (!Array.isArray(menus)) return;
  const { resetCart = false, category = "coffee" } = options;

  MENU_INDEX_50.clear();
  if (resetCart) {
    Object.keys(cart50).forEach(k => delete cart50[k]);
  }

  const grid = document.getElementById("grid-50menu");
  if (!grid) return;

  const normalizedMenus = menus.map(m => {
    const id = m.menu_id || m.id;
    if (!id) return null;

    const resolvedCategory = m.category || guessCategoryById(id, m.name);

    const normalized = {
      ...m,
      menu_id: id,
      category: resolvedCategory,
      image: m.image || ""
    };

    MENU_INDEX_50.set(id, normalized);
    return normalized;
  }).filter(Boolean);

  const filteredMenus = normalizedMenus.filter(m => !category || m.category === category);

  grid.innerHTML = filteredMenus.map(m => {
    const thumbStyle = m.image ? ` style=\"background-image:url('${m.image}')\" ` : "";
    return `
      <button class="menuItem" type="button" data-id="${m.menu_id}">
        <div class="menuThumb"${thumbStyle}></div>
        <div class="menuName">${m.name}</div>
        <div class="menuPrice">${m.price.toLocaleString()} 원</div>
      </button>
    `;
  }).join("");

  window.__menus50 = normalizedMenus;
  window.__menus50ActiveCategory = category;

  bindMenuClick50();
  renderCart50();
}

function applyMenusTo10to40(menus, options = {}) {
  if (!Array.isArray(menus)) return;
  const { resetCart = false, category = "coffee" } = options;

  MENU_INDEX_10TO40.clear();
  if (resetCart) {
    Object.keys(cart10).forEach(k => delete cart10[k]);
  }

  const grid = document.getElementById("grid-10to40");
  if (!grid) return;

  const normalizedMenus = menus.map(m => {
    const id = m.menu_id || m.id;
    if (!id) return null;

    const resolvedCategory = m.category || guessCategoryById(id, m.name);

    const normalized = {
      ...m,
      menu_id: id,
      category: resolvedCategory,
      image: m.image || ""
    };

    MENU_INDEX_10TO40.set(id, normalized);
    return normalized;
  }).filter(Boolean);

  const filteredMenus = normalizedMenus.filter(m => !category || m.category === category);

  grid.innerHTML = filteredMenus.map(m => {
    const thumbStyle = m.image ? ` style="background-image:url('${m.image}')" ` : "";
    return `
      <button class="menuItem" type="button" data-id="${m.menu_id}">
        <div class="menuThumb"${thumbStyle}></div>
        <div class="menuName">${m.name}</div>
        <div class="menuPrice">${m.price.toLocaleString()} 원</div>
      </button>
    `;
  }).join("");
  window.__menus10to40 = normalizedMenus;
  window.__menus10to40ActiveCategory = category;
  bindMenuClick10(); // ⭐ 반드시 여기

  renderCart10();
}

function guessCategoryById(menuId, name = "") {
  const key = (menuId || name || "").toLowerCase();

  if (key.includes("smoothie") || key.includes("smu")) return "smoothie";
  if (key.includes("tea") || key.includes("earl") || key.includes("grey") || key.includes("lemon") || key.includes("chamomile") || key.includes("grapefruit")) return "tea";

  return "coffee";
}
