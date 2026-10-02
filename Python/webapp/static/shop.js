"use strict";

const SHOP = window.SHOP;

const grid = document.getElementById("grid");
const creditsEl = document.getElementById("credits");
const saleBanner = document.getElementById("sale-banner");
const backdrop = document.getElementById("backdrop");
const modalTitle = document.getElementById("modal-title");
const modalPrice = document.getElementById("modal-price");
const buyForm = document.getElementById("buy-form");
const modalError = document.getElementById("modal-error");
const cancelBtn = document.getElementById("cancel-btn");
const confirmBtn = document.getElementById("confirm-btn");
const toast = document.getElementById("toast");

let activeItem = null;
let toastTimer = null;

function fmt(seconds) {
  seconds = Math.max(0, Math.round(seconds));
  const parts = [];
  const units = [[86400, "d"], [3600, "h"], [60, "m"], [1, "s"]];
  for (const [size, suffix] of units) {
    const count = Math.floor(seconds / size);
    if (count > 0 || (parts.length && size === 1)) {
      if (count > 0) parts.push(count + suffix);
      seconds %= size;
    }
  }
  return parts.join(" ") || "0s";
}

function itemCost(item, duration) {
  const count = duration || 1;
  return Math.trunc(item.cost * count);
}

function showToast(message, isError) {
  toast.textContent = message;
  toast.classList.toggle("error", !!isError);
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function render() {
  if (!SHOP) {
    grid.innerHTML = '<p class="error">Server unavailable.</p>';
    return;
  }
  creditsEl.textContent = SHOP.credits_display;
  if (SHOP.sale.active) {
    saleBanner.hidden = false;
    saleBanner.textContent = "🏷️ Sale is on! Everything is half off.";
  }

  for (const group of SHOP.groups) {
    const section = document.createElement("section");
    section.className = "category";
    const heading = document.createElement("h2");
    heading.textContent = group.category;
    section.appendChild(heading);

    const cards = document.createElement("div");
    cards.className = "cards";
    for (const item of group.items) {
      const card = document.createElement("div");
      card.className = "card";

      const name = document.createElement("div");
      name.className = "name";
      name.textContent = item.name;

      const price = document.createElement("div");
      price.className = "price";
      if (item.cost !== item.base_cost) {
        const old = document.createElement("s");
        old.textContent = fmt(item.base_cost);
        price.appendChild(old);
      }
      const priceText = document.createElement("span");
      priceText.textContent = fmt(item.cost) + (item.form.some(f => f.kind === "duration") ? " / minute" : "");
      price.appendChild(priceText);

      const buy = document.createElement("button");
      buy.className = "primary";
      buy.textContent = "Buy";
      buy.addEventListener("click", () => openModal(item));

      card.append(name, price, buy);
      cards.appendChild(card);
    }
    section.appendChild(cards);
    grid.appendChild(section);
  }
}

function fieldElement(field, durations, members) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const label = document.createElement("label");
  label.textContent = field.label + (field.required ? "" : " (optional)");
  wrap.appendChild(label);

  let input;
  if (field.kind === "user") {
    input = document.createElement("select");
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select a user…";
    input.appendChild(placeholder);
    for (const member of members) {
      const opt = document.createElement("option");
      opt.value = String(member.id);
      opt.textContent = member.name;
      input.appendChild(opt);
    }
  } else if (field.kind === "duration") {
    input = document.createElement("select");
    for (const duration of durations) {
      const opt = document.createElement("option");
      opt.value = String(duration);
      opt.textContent = duration + " minute(s)";
      input.appendChild(opt);
    }
    input.value = "1";
  } else {
    input = document.createElement("input");
    input.type = "text";
    if (field.max_length) input.maxLength = field.max_length;
    if (field.placeholder) input.placeholder = field.placeholder;
    if (field.kind === "colour") input.placeholder = field.placeholder || "#ff8800";
  }
  input.dataset.kind = field.kind;
  if (field.required) input.required = true;
  wrap.appendChild(input);
  return wrap;
}

function updatePrice() {
  const durationInput = buyForm.querySelector('[data-kind="duration"]');
  const duration = durationInput ? Number(durationInput.value) : 0;
  const cost = itemCost(activeItem, duration);
  modalPrice.textContent = fmt(cost);
}

function openModal(item) {
  activeItem = item;
  modalTitle.textContent = item.name;
  modalError.hidden = true;
  buyForm.innerHTML = "";
  for (const field of item.form) {
    buyForm.appendChild(fieldElement(field, SHOP.durations, SHOP.members));
  }
  updatePrice();
  backdrop.classList.remove("hidden");
}

function closeModal() {
  backdrop.classList.add("hidden");
  activeItem = null;
}

function collectParams() {
  const params = {};
  for (const input of buyForm.querySelectorAll("[data-kind]")) {
    const kind = input.dataset.kind;
    const value = input.value;
    if (kind === "text" && !value.trim()) continue;
    if (value === "") continue;
    if (kind === "user" || kind === "duration") {
      params[kind] = Number(value);
    } else {
      params[kind] = value;
    }
  }
  return params;
}

async function confirmPurchase() {
  if (!activeItem) return;
  confirmBtn.disabled = true;
  modalError.hidden = true;
  try {
    const response = await fetch("/api/shop/purchase", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_id: activeItem.id, params: collectParams() }),
    });
    const data = await response.json();
    if (!response.ok) {
      modalError.textContent = data.error || "Purchase failed.";
      modalError.hidden = false;
      return;
    }
    closeModal();
    creditsEl.textContent = data.credits_display;
    SHOP.credits = data.credits;
    SHOP.credits_display = data.credits_display;
    showToast("Purchased! " + fmt(data.cost) + " spent.", false);
  } catch (err) {
    modalError.textContent = "Network error, please try again.";
    modalError.hidden = false;
  } finally {
    confirmBtn.disabled = false;
  }
}

buyForm.oninput = updatePrice;
buyForm.onchange = updatePrice;

cancelBtn.addEventListener("click", closeModal);
confirmBtn.addEventListener("click", confirmPurchase);
backdrop.addEventListener("click", (event) => {
  if (event.target === backdrop) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !backdrop.classList.contains("hidden")) closeModal();
});

render();
