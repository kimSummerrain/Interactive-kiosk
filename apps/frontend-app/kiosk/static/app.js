/* Load once with defer: all elements exist before events are attached. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = {
    mode: null,
    ageGroup: null,
    menus: [],
    category: "coffee",
    cart: new Map(),
    large: false,
    request: null,
    submitting: false,
    starting: false,
    orderPayload: null,
  };
  const money = (value) => `${value.toLocaleString("ko-KR")}원`;
  const assetRoot = new URL("/static/images/", location.href);
  const localImages = new Set([
    "ame_hot",
    "ame_ice",
    "latte_hot",
    "latte_ice",
    "choco_hot",
    "choco_ice",
    "straw_smoothie",
    "blue_smoothie",
    "mango_smoothie",
    "yogurt_smoothie",
    "chamomile_hot",
    "chamomile_ice",
    "lemon_hot",
    "lemon_ice",
  ]);

  function showScreen(id) {
    document.querySelectorAll(".screen").forEach((screen) => {
      screen.hidden = screen.id !== id;
      screen.classList.toggle("active", screen.id === id);
    });
    window.scrollTo(0, 0);
    $(id).querySelector("h1")?.focus({ preventScroll: true });
  }
  function errorAt(id, message = "") {
    $(id).textContent = message;
    $(id).hidden = !message;
  }
  function cancelRecommendation() {
    state.request?.abort();
    state.request = null;
    $("fileInput").value = "";
  }
  function home() {
    cancelRecommendation();
    state.cart.clear();
    state.menus = [];
    state.ageGroup = null;
    state.mode = null;
    state.orderPayload = null;
    errorAt("face-error");
    errorAt("payment-error");
    errorAt("start-error");
    showScreen("screen-order");
  }
  function requestHome() {
    if (state.submitting || state.starting) return;
    if (state.cart.size) $("reset-dialog").showModal();
    else home();
  }
  $("btnKeepOrder").addEventListener("click", () => $("reset-dialog").close());
  $("btnResetOrder").addEventListener("click", () => {
    $("reset-dialog").close();
    home();
  });
  async function startOrder(mode) {
    if (state.starting) return;
    state.starting = true;
    errorAt("start-error");
    const buttons = [$("btnTakeout"), $("btnEathere")];
    buttons.forEach((button) => {
      button.disabled = true;
    });
    try {
      const response = await fetch("/api/menus");
      const data = await response.json();
      if (!response.ok || !data.menus?.length)
        throw new Error(
          "메뉴를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
        );
      state.mode = mode;
      state.menus = data.menus.map((menu) => ({
        ...menu,
        id: menu.menu_id,
        category: categoryOf(menu),
      }));
      state.category = "coffee";
      state.ageGroup = null;
      state.large = false;
      state.cart.clear();
      state.orderPayload = null;
      $("order-mode").textContent =
        mode === "takeout" ? "포장 주문" : "매장 주문";
      updateLargeText();
      renderMenu();
      renderCart();
      showScreen("screen-menu");
    } catch {
      errorAt(
        "start-error",
        "메뉴를 불러오지 못했어요. 서버 연결을 확인하거나 직원에게 문의해 주세요.",
      );
    } finally {
      state.starting = false;
      buttons.forEach((button) => {
        button.disabled = false;
      });
    }
  }
  for (const [id, mode] of [
    ["btnTakeout", "takeout"],
    ["btnEathere", "eathere"],
  ]) {
    $(id).addEventListener("click", () => startOrder(mode));
  }
  document.querySelector(".brand").addEventListener("click", (event) => {
    event.preventDefault();
    requestHome();
  });
  document.querySelectorAll("[data-back]").forEach((button) =>
    button.addEventListener("click", () => {
      if (state.submitting) return;
      const target = button.dataset.back;
      if (target === "home") return requestHome();
      if (target === "menu") return showScreen("screen-menu");
      cancelRecommendation();
      errorAt("face-error");
      showScreen("screen-face");
    }),
  );
  $("btnPick").addEventListener("click", () => $("fileInput").click());
  $("btnRecommend").addEventListener("click", () => {
    errorAt("face-error");
    showScreen("screen-face");
  });
  $("btnGoHome").addEventListener("click", home);

  function categoryOf(menu) {
    if (["coffee", "smoothie", "tea"].includes(menu.category))
      return menu.category;
    const key = `${menu.menu_id || menu.id} ${menu.name}`.toLowerCase();
    if (/smoothie|스무디/.test(key)) return "smoothie";
    if (/tea|lemon|chamomile|earl|grapefruit|티$/.test(key)) return "tea";
    return "coffee";
  }
  $("fileInput").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    errorAt("face-error");
    if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024) {
      errorAt("face-error", "10MB 이하의 이미지 파일을 선택해 주세요.");
      event.target.value = "";
      return;
    }
    cancelRecommendation();
    const controller = new AbortController();
    state.request = controller;
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 90000);
    showScreen("screen-loading");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch("/api/recommend", {
        method: "POST",
        body: form,
        signal: controller.signal,
      });
      const data = await response.json();
      if (state.request !== controller) return;
      if (!response.ok || data.error)
        throw new Error(
          data.detail ||
            data.message ||
            "추천을 불러오지 못했어요. 사진을 다시 선택해 주세요.",
        );
      const ageGroup = data.age_group;
      if (!["10_40", "41_50"].includes(ageGroup) || !Array.isArray(data.menus))
        throw new Error("추천 정보를 확인할 수 없어요. 다시 시도해 주세요.");
      const seen = new Set();
      const menus = data.menus
        .filter((menu) => {
          if (!menu || typeof menu !== "object") return false;
          const id = String(menu.menu_id || menu.id || "");
          if (
            !id ||
            seen.has(id) ||
            typeof menu.name !== "string" ||
            menu.price == null ||
            !Number.isFinite(Number(menu.price)) ||
            Number(menu.price) < 0
          )
            return false;
          seen.add(id);
          return true;
        })
        .map((menu) => ({
          ...menu,
          id: String(menu.menu_id || menu.id),
          price: Number(menu.price),
          category: categoryOf(menu),
        }));
      if (!menus.length)
        throw new Error("추천할 메뉴가 없어요. 직원에게 문의해 주세요.");
      state.menus = menus;
      state.ageGroup = ageGroup;
      state.large = ageGroup === "41_50";
      for (const id of state.cart.keys())
        if (!menus.some((menu) => menu.id === id)) state.cart.delete(id);
      state.orderPayload = null;
      state.category = menus.some((menu) => menu.category === "coffee")
        ? "coffee"
        : menus[0].category;
      $("order-mode").textContent =
        state.mode === "takeout"
          ? "포장 주문 · 추천 메뉴"
          : "매장 주문 · 추천 메뉴";
      updateLargeText();
      renderMenu();
      renderCart();
      showScreen("screen-menu");
    } catch (error) {
      if (state.request !== controller) return;
      errorAt(
        "face-error",
        timedOut
          ? "추천 시간이 길어지고 있어요. 잠시 후 다시 시도해 주세요."
          : error instanceof SyntaxError || error instanceof TypeError
            ? "서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요."
            : error.message,
      );
      showScreen("screen-face");
    } finally {
      clearTimeout(timeout);
      if (state.request === controller) state.request = null;
    }
  });

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }
  function imageFor(menu) {
    if (localImages.has(menu.id))
      return new URL(`${menu.id}.png`, assetRoot).href;
    if (!menu.image) return null;
    try {
      const url = new URL(menu.image, location.href);
      return ["http:", "https:"].includes(url.protocol) &&
        url.origin === location.origin
        ? url.href
        : null;
    } catch {
      return null;
    }
  }
  function renderMenu() {
    document.querySelectorAll("[data-category]").forEach((tab) => {
      const active = tab.dataset.category === state.category;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", String(active));
    });
    const grid = $("menu-grid");
    grid.replaceChildren();
    const menus = state.menus.filter(
      (menu) => menu.category === state.category,
    );
    if (!menus.length)
      grid.append(
        element("p", "menu-empty", "이 카테고리에는 준비된 메뉴가 없어요."),
      );
    menus.forEach((menu) => {
      const button = element("button", "menuItem");
      button.type = "button";
      button.dataset.id = menu.id;
      button.setAttribute(
        "aria-label",
        `${menu.name}, ${money(menu.price)}, 담기`,
      );
      const thumb = element("span", "menuThumb");
      thumb.setAttribute("aria-hidden", "true");
      const fallback = element("span", "drink-fallback", "☕");
      thumb.append(fallback);
      const source = imageFor(menu);
      if (source) {
        const image = element("img");
        image.alt = "";
        image.loading = "lazy";
        image.addEventListener("load", () => {
          fallback.hidden = true;
        });
        image.addEventListener("error", () => {
          image.remove();
          fallback.hidden = false;
        });
        image.src = source;
        thumb.append(image);
      }
      button.append(
        thumb,
        element("span", "menuName", menu.name),
        element("span", "menuPrice", money(menu.price)),
      );
      grid.append(button);
    });
  }
  document.querySelectorAll("[data-category]").forEach((tab) =>
    tab.addEventListener("click", () => {
      state.category = tab.dataset.category;
      renderMenu();
    }),
  );
  function updateLargeText() {
    $("screen-menu").classList.toggle("large-text", state.large);
    $("btnLarge").setAttribute("aria-pressed", String(state.large));
  }
  $("btnLarge").addEventListener("click", () => {
    state.large = !state.large;
    updateLargeText();
  });
  $("menu-grid").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (!button) return;
    const menu = state.menus.find((item) => item.id === button.dataset.id);
    if (!menu) return;
    state.cart.set(menu.id, (state.cart.get(menu.id) || 0) + 1);
    if (state.cart.get(menu.id) > 99) state.cart.set(menu.id, 99);
    state.orderPayload = null;
    renderCart();
    $("announcement").textContent =
      `${menu.name} ${state.cart.get(menu.id)}개를 담았어요.`;
  });
  function cartSummary() {
    let total = 0,
      count = 0;
    state.cart.forEach((qty, id) => {
      total += state.menus.find((menu) => menu.id === id).price * qty;
      count += qty;
    });
    return { total, count };
  }
  function renderCart() {
    const cart = $("cart-items");
    cart.replaceChildren();
    if (!state.cart.size)
      cart.append(
        element(
          "p",
          "cart-empty",
          "아직 담은 메뉴가 없어요.\n좋아하는 한 잔을 골라 보세요.",
        ),
      );
    state.cart.forEach((qty, id) => {
      const menu = state.menus.find((item) => item.id === id);
      const row = element("div", "cartRow");
      row.append(element("div", "cartName", menu.name));
      const detail = element("div", "cart-detail");
      const controls = element("div", "qty");
      for (const [action, label] of [
        ["minus", "−"],
        ["plus", "+"],
      ]) {
        const button = element("button", "qtyBtn", label);
        button.type = "button";
        button.dataset.id = id;
        button.dataset.action = action;
        button.setAttribute(
          "aria-label",
          `${menu.name} 수량 ${action === "plus" ? "늘리기" : "줄이기"}`,
        );
        controls.append(button);
        if (action === "minus") controls.append(element("span", "qtyNum", qty));
      }
      detail.append(
        controls,
        element("span", "cart-price", money(menu.price * qty)),
      );
      row.append(detail);
      cart.append(row);
    });
    const { total, count } = cartSummary();
    $("cart-count").textContent = count;
    $("cart-total").textContent = money(total);
    $("btnPay").disabled = !count;
    $("btnClear").disabled = !count;
  }
  $("cart-items").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const { id, action } = button.dataset;
    const qty = (state.cart.get(id) || 0) + (action === "plus" ? 1 : -1);
    if (qty > 0) state.cart.set(id, Math.min(qty, 99));
    else state.cart.delete(id);
    state.orderPayload = null;
    const scrollTop = $("cart-items").scrollTop;
    renderCart();
    const replacement = Array.from(
      $("cart-items").querySelectorAll("button"),
    ).find((node) => node.dataset.id === id && node.dataset.action === action);
    (
      replacement ||
      $("cart-items").querySelector("button") ||
      document.querySelector(".tab.active")
    ).focus({ preventScroll: true });
    $("cart-items").scrollTop = scrollTop;
  });
  $("btnClear").addEventListener("click", () => {
    state.cart.clear();
    state.orderPayload = null;
    renderCart();
  });
  $("btnPay").addEventListener("click", () => {
    const { total, count } = cartSummary();
    if (!count) return;
    $("payment-summary").textContent =
      `${state.mode === "takeout" ? "포장" : "매장"} 주문 · ${count}개 · ${money(total)}`;
    errorAt("payment-error");
    showScreen("screen-paymethod");
  });
  function requestId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  async function submitOrder(paymentMethod) {
    if (state.submitting || !state.cart.size) return;
    state.submitting = true;
    errorAt("payment-error");
    const buttons = $("screen-paymethod").querySelectorAll("button");
    buttons.forEach((button) => {
      button.disabled = true;
    });
    $("payment-status").textContent = "주문을 접수하고 있어요…";
    // Keep the same payload/key after a lost response so retry cannot duplicate it.
    state.orderPayload ||= {
      request_id: requestId(),
      order_mode: state.mode,
      payment_method: paymentMethod,
      age_group: state.ageGroup,
      items: Array.from(state.cart, ([menu_id, qty]) => ({ menu_id, qty })),
    };
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.orderPayload),
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok || data.error || data.result !== "OK" || !data.order)
        throw new Error("Order not confirmed");
      $("order-number").textContent = data.order.order_number;
      state.cart.clear();
      state.orderPayload = null;
      showScreen("screen-complete");
    } catch {
      errorAt(
        "payment-error",
        "접수 응답을 받지 못했어요. 같은 결제 버튼을 눌러 다시 확인해 주세요. 동일한 주문은 중복 접수되지 않아요.",
      );
    } finally {
      clearTimeout(timeout);
      state.submitting = false;
      buttons.forEach((button) => {
        button.disabled = false;
      });
      $("payment-status").textContent = "";
    }
  }
  $("optCard").addEventListener("click", () => submitOrder("card"));
  $("optVoucher").addEventListener("click", () => submitOrder("voucher"));
})();
