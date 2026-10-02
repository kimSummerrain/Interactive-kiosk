(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = {
    auth: null,
    epoch: 0,
    view: "orders",
    page: 1,
    total: 0,
    busy: false,
    detail: null,
  };
  const statuses = {
    pending: "접수",
    preparing: "준비 중",
    completed: "완료",
    cancelled: "취소",
  };
  const methods = { card: "카드", voucher: "상품권", counter: "카운터" };
  const money = (value) => `${value.toLocaleString("ko-KR")}원`;
  const formatTime = (value) =>
    new Date(value).toLocaleString("ko-KR", {
      timeZone: "Asia/Seoul",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  $("start-date").value = $("end-date").value = today;
  function error(id, message = "") {
    $(id).textContent = message;
    $(id).hidden = !message;
  }
  function node(tag, text, className) {
    const el = document.createElement(tag);
    if (text != null) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function logout() {
    state.auth = null;
    state.epoch++;
    state.busy = false;
    $("dashboard").hidden = true;
    $("login-screen").hidden = false;
    $("password").value = "";
    $("order-dialog").close();
    $("filter-form")
      .querySelectorAll("input,select,button")
      .forEach((control) => {
        control.disabled = false;
      });
    $("refresh").disabled = false;
    $("load-status").textContent = "";
    $("order-rows").replaceChildren();
    $("daily-rows").replaceChildren();
    $("menu-rows").replaceChildren();
  }
  async function api(path, options = {}) {
    const auth = state.auth;
    const response = await fetch(path, {
      ...options,
      headers: {
        Authorization: auth,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && auth === state.auth) logout();
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "요청을 처리하지 못했습니다. 입력 내용을 확인해 주세요.",
      );
    }
    return data;
  }
  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    error("login-error");
    $("login-button").disabled = true;
    try {
      const bytes = new TextEncoder().encode(
        `${$("username").value}:${$("password").value}`,
      );
      state.auth = `Basic ${btoa(String.fromCharCode(...bytes))}`;
      const data = await api("/api/admin/me");
      $("password").value = "";
      state.page = 1;
      $("admin-name").textContent = `${data.username} · 관리자`;
      $("login-screen").hidden = true;
      $("dashboard").hidden = false;
      await refresh();
    } catch (e) {
      state.auth = null;
      error("login-error", e.message || "서버에 연결하지 못했습니다.");
    } finally {
      $("login-button").disabled = false;
    }
  });
  $("logout").addEventListener("click", logout);
  function period() {
    return new URLSearchParams({
      start: $("start-date").value,
      end: $("end-date").value,
    });
  }
  function empty(tbody, columns, text) {
    const row = node("tr");
    const cell = node("td", text, "empty");
    cell.colSpan = columns;
    row.append(cell);
    tbody.append(row);
  }
  function renderSummary(data) {
    $("revenue").textContent = money(data.revenue);
    $("order-count").textContent = `${data.order_count}건`;
    $("paid-count").textContent = `결제 완료 ${data.paid_count}건`;
    $("pending-count").textContent = `${data.pending_count}건`;
    $("cancelled-count").textContent = `${data.cancelled_count}건`;
    const daily = $("daily-rows");
    daily.replaceChildren();
    for (const item of data.daily) {
      const row = node("tr");
      row.append(
        node("td", item.date),
        node("td", `${item.orders}건`),
        node("td", money(item.revenue)),
      );
      daily.append(row);
    }
    if (!data.daily.length)
      empty(daily, 3, "선택한 기간에 결제 완료 내역이 없습니다.");
    const top = $("menu-rows");
    top.replaceChildren();
    for (const item of data.top_menus) {
      const row = node("tr");
      row.append(
        node("td", item.name),
        node("td", `${item.quantity}개`),
        node("td", money(item.revenue)),
      );
      top.append(row);
    }
    if (!data.top_menus.length) empty(top, 3, "판매된 메뉴가 없습니다.");
  }
  function badge(text, kind) {
    return node("span", text, `badge ${kind}`);
  }
  function renderOrders(data) {
    state.total = data.total;
    const rows = $("order-rows");
    rows.replaceChildren();
    for (const order of data.orders) {
      const row = node("tr");
      const number = node("td");
      number.append(node("strong", `#${order.order_number}`));
      const items = order.items
        .map((item) => `${item.name} × ${item.qty}`)
        .join(", ");
      const payment = node("td");
      payment.append(
        badge(
          order.payment_status === "paid" ? "결제 완료" : "미결제",
          order.payment_status,
        ),
      );
      const status = node("td");
      status.append(badge(statuses[order.status], order.status));
      const action = node("td");
      const button = node("button", "보기", "secondary");
      button.type = "button";
      button.setAttribute("aria-label", `주문 ${order.order_number} 상세`);
      button.addEventListener("click", () => openDetail(order.id));
      action.append(button);
      row.append(
        number,
        node("td", formatTime(order.created_at)),
        node("td", items),
        node("td", order.order_mode === "takeout" ? "포장" : "매장"),
        node("td", money(order.total)),
        payment,
        status,
        action,
      );
      rows.append(row);
    }
    if (!data.orders.length)
      empty(rows, 8, "선택한 조건에 해당하는 주문이 없습니다.");
    $("list-count").textContent = `총 ${data.total}건`;
    $("page-number").textContent =
      `${state.page} / ${Math.max(1, Math.ceil(data.total / 20))}`;
    $("prev").disabled = state.page <= 1;
    $("next").disabled = state.page * 20 >= data.total;
  }
  async function refresh() {
    if (!state.auth || state.busy) return;
    if (!$("filter-form").reportValidity()) return;
    if ($("start-date").value > $("end-date").value) {
      error("dashboard-error", "시작일은 종료일 이전이어야 합니다.");
      return;
    }
    state.busy = true;
    const epoch = state.epoch;
    error("dashboard-error");
    $("load-status").textContent = "불러오는 중…";
    const controls = [
      ...$("filter-form").querySelectorAll("input,select,button"),
      $("refresh"),
      $("prev"),
      $("next"),
    ];
    controls.forEach((control) => {
      control.disabled = true;
    });
    try {
      const query = period();
      query.set("page", state.page);
      query.set("page_size", 20);
      if ($("status").value) query.set("status", $("status").value);
      const [orders, summary] = await Promise.all([
        api(`/api/admin/orders?${query}`),
        api(`/api/admin/sales?${period()}`),
      ]);
      if (epoch !== state.epoch) return;
      renderOrders(orders);
      renderSummary(summary);
    } catch (e) {
      if (epoch === state.epoch)
        error("dashboard-error", e.message || "서버에 연결하지 못했습니다.");
    } finally {
      if (epoch === state.epoch) {
        state.busy = false;
        $("load-status").textContent = "";
        controls.forEach((control) => {
          control.disabled = false;
        });
        $("prev").disabled = state.page <= 1;
        $("next").disabled = state.page * 20 >= state.total;
      }
    }
  }
  $("filter-form").addEventListener("submit", (event) => {
    event.preventDefault();
    state.page = 1;
    refresh();
  });
  $("refresh").addEventListener("click", refresh);
  $("prev").addEventListener("click", () => {
    if (state.busy) return;
    state.page--;
    refresh();
  });
  $("next").addEventListener("click", () => {
    if (state.busy) return;
    state.page++;
    refresh();
  });
  document.querySelectorAll("[data-view]").forEach((button) =>
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      const sales = state.view === "sales";
      $("orders-view").hidden = sales;
      $("sales-view").hidden = !sales;
      $("status-filter").hidden = sales;
      $("page-title").textContent = sales ? "판매내역" : "주문 관리";
      $("page-description").textContent = sales
        ? "기간별 매출과 메뉴별 판매량을 확인하세요."
        : "접수된 주문과 진행 상태를 확인하세요.";
      document.querySelectorAll("[data-view]").forEach((tab) => {
        tab.classList.toggle("active", tab === button);
        tab.setAttribute("aria-pressed", String(tab === button));
      });
    }),
  );
  function renderDetail(order) {
    state.detail = order;
    $("detail-title").textContent = `주문 #${order.order_number}`;
    $("detail-meta").textContent =
      `${formatTime(order.created_at)} · ${order.order_mode === "takeout" ? "포장" : "매장"} · ${methods[order.payment_method]}`;
    $("detail-total").textContent = money(order.total);
    $("detail-state").textContent =
      `${statuses[order.status]} · ${order.payment_status === "paid" ? "결제 완료" : "미결제"}`;
    const items = $("detail-items");
    items.replaceChildren();
    for (const item of order.items) {
      const row = node("div", null, "detail-item");
      row.append(
        node("div", `${item.name} × ${item.qty}`),
        node("span", money(item.price * item.qty)),
      );
      items.append(row);
    }
    const actions = $("detail-actions");
    actions.replaceChildren();
    function action(label, patch, kind = "primary") {
      const button = node("button", label, kind);
      button.type = "button";
      button.addEventListener("click", () => updateOrder(patch));
      actions.append(button);
    }
    if (order.payment_status === "unpaid" && order.status !== "cancelled")
      action("결제 확인", { payment_status: "paid" });
    if (order.status === "pending")
      action("준비 시작", { status: "preparing" }, "secondary");
    if (order.status === "preparing" && order.payment_status === "paid")
      action("주문 완료", { status: "completed" });
    if (
      ["pending", "preparing"].includes(order.status) &&
      order.payment_status === "unpaid"
    )
      action("주문 취소", { status: "cancelled" }, "secondary danger");
  }
  async function openDetail(id) {
    const epoch = state.epoch;
    error("dashboard-error");
    error("detail-error");
    try {
      const order = await api(`/api/admin/orders/${id}`);
      if (epoch !== state.epoch) return;
      renderDetail(order);
      if (!$("order-dialog").open) $("order-dialog").showModal();
    } catch (e) {
      if (epoch === state.epoch) error("dashboard-error", e.message);
    }
  }
  async function updateOrder(patch) {
    if (
      patch.payment_status &&
      !confirm("카운터에서 실제 결제가 완료되었나요?")
    )
      return;
    if (patch.status === "cancelled" && !confirm("이 주문을 취소할까요?"))
      return;
    const epoch = state.epoch;
    error("detail-error");
    $("detail-actions")
      .querySelectorAll("button")
      .forEach((button) => {
        button.disabled = true;
      });
    try {
      const order = await api(`/api/admin/orders/${state.detail.id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      if (epoch !== state.epoch) return;
      renderDetail(order);
      await refresh();
    } catch (e) {
      if (epoch === state.epoch) {
        error("detail-error", e.message);
        $("detail-actions")
          .querySelectorAll("button")
          .forEach((button) => {
            button.disabled = false;
          });
      }
    }
  }
  $("close-detail").addEventListener("click", () => $("order-dialog").close());
})();
